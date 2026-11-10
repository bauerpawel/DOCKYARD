"""Report catalog quality and pin :latest images to a verified multi-arch digest.

The pin step asks the image registry for the manifest of the current tag and
accepts only a manifest list or an OCI index. A single-platform manifest is
left unchanged so a machine-specific digest is never written. Tags and
repository names are not invented and are not switched to another project.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

import yaml

INDEX_TYPES = {
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.oci.image.index.v1+json",
}
SINGLE_TYPES = {
    "application/vnd.docker.distribution.manifest.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
}
ACCEPT = ", ".join(sorted(INDEX_TYPES | SINGLE_TYPES))
IMAGE_LINE = re.compile(r"(?m)^(?P<indent>[ \t]*)image:\s*(?P<quote>['\"]?)(?P<ref>[^'\"\s#]+)(?P=quote)[ \t]*$")


class CatalogAuditError(RuntimeError):
    pass


def parse_image(reference: str) -> tuple[str, str, str] | None:
    """Return registry, repository, and tag. None when the reference is not an image name."""
    reference = reference.strip()
    if not reference or reference.startswith("$") or "://" in reference:
        return None
    name = reference.split("@", 1)[0]
    if ":" in name.split("/")[-1]:
        repository, tag = name.rsplit(":", 1)
    else:
        repository, tag = name, "latest"
    host = repository.split("/", 1)[0]
    if "." in host or ":" in host or host == "localhost":
        registry, repository = repository.split("/", 1)
    else:
        registry = "docker.io"
        if "/" not in repository:
            repository = "library/" + repository
    if not repository or not tag:
        return None
    return registry, repository, tag


def has_digest(reference: str) -> bool:
    return "@sha256:" in reference


def is_latest(reference: str) -> bool:
    name = reference.split("@", 1)[0]
    return name.endswith(":latest") and not has_digest(reference) and parse_image(reference) is not None


def _load_apps(apps_dir: Path) -> list[tuple[Path, dict]]:
    loaded = []
    for path in sorted(apps_dir.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            loaded.append((path, data))
    return loaded


def _normalize_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"\([^)]*\)", "", title)
    return re.sub(r"[^a-z0-9]+", "", title)


def audit_catalog(repo_root: Path) -> dict:
    """Summarize :latest pins, the Other category, near-duplicate titles, and obsolete Compose versions."""
    apps = _load_apps(repo_root / "apps")
    container_images = []
    latest = []
    other = []
    groups: dict[str, list] = defaultdict(list)
    for path, data in apps:
        image = data.get("image")
        if data.get("type") == "container" and isinstance(image, str) and image:
            container_images.append(image)
            if is_latest(image):
                latest.append({"slug": data.get("slug"), "image": image, "file": str(path.relative_to(repo_root))})
        if data.get("category") == "Other":
            other.append(data.get("slug"))
        groups[_normalize_title(str(data.get("name") or ""))].append({
            "slug": data.get("slug"),
            "name": data.get("name"),
            "type": data.get("type"),
            "image": image,
            "repository": (data.get("repository") or {}).get("url") if isinstance(data.get("repository"), dict) else None,
        })
    near = []
    for items in groups.values():
        if len(items) < 2:
            continue
        identities = {(item["type"], item["image"], item["repository"]) for item in items}
        near.append({"kept": len(identities) > 1 or len(items) > 1, "apps": items})
    versions = []
    stacks = repo_root / "stacks"
    if stacks.is_dir():
        for path in sorted(stacks.rglob("*.yml")):
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if re.match(r"^version:\s*['\"]?\d", line):
                    versions.append(f"{path.relative_to(repo_root)}:{number}")
    return {
        "container_images": len(container_images),
        "container_latest_without_digest": latest,
        "other_slugs": other,
        "near_duplicate_titles": near,
        "compose_version_keys": versions,
    }


def _registry_host(registry: str) -> str:
    return "registry-1.docker.io" if registry == "docker.io" else registry


def _request(url: str, headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": "dockyard-catalog-audit", **headers})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, {key.lower(): value for key, value in response.headers.items()}, response.read(2_000_000)
    except urllib.error.HTTPError as error:
        return error.code, {key.lower(): value for key, value in error.headers.items()}, error.read(200_000)


def _bearer(headers: dict[str, str], repository: str) -> str | None:
    challenge = headers.get("www-authenticate", "")
    if not challenge.lower().startswith("bearer"):
        return None
    parts = dict(re.findall(r'(\w+)="([^"]*)"', challenge))
    realm = parts.get("realm")
    if not realm:
        return None
    query = []
    if parts.get("service"):
        query.append("service=" + urllib.parse.quote(parts["service"], safe=""))
    scope = parts.get("scope") or f"repository:{repository}:pull"
    query.append("scope=" + urllib.parse.quote(scope, safe=""))
    status, _, body = _request(realm + ("&" if "?" in realm else "?") + "&".join(query), {})
    if status != 200:
        return None
    payload = json.loads(body.decode("utf-8", "replace") or "{}")
    token = payload.get("token") or payload.get("access_token")
    return token if isinstance(token, str) and token else None


def resolve_manifest(reference: str, fetch=_request) -> tuple[str | None, str]:
    """Return (digest, reason). digest is the manifest-list digest, or None when it must not be pinned."""
    parsed = parse_image(reference)
    if parsed is None:
        return None, "not an image reference"
    if not is_latest(reference):
        return None, "already pinned or not the latest tag"
    registry, repository, tag = parsed
    url = f"https://{_registry_host(registry)}/v2/{repository}/manifests/{tag}"
    headers = {"Accept": ACCEPT}
    status, response_headers, _body = fetch(url, headers)
    response_headers = {key.lower(): value for key, value in response_headers.items()}
    if status == 401:
        if fetch is not _request:
            return None, "registry required authentication"
        token = _bearer(response_headers, repository)
        if not token:
            return None, "registry authentication failed"
        status, response_headers, _body = fetch(url, {"Accept": ACCEPT, "Authorization": "Bearer " + token})
        response_headers = {key.lower(): value for key, value in response_headers.items()}
    if status == 429:
        raise CatalogAuditError("registry rate limit while resolving " + reference)
    if status != 200:
        return None, f"registry returned HTTP {status}"
    media = response_headers.get("content-type", "").split(";", 1)[0].strip().lower()
    digest = response_headers.get("docker-content-digest", "").strip().lower()
    if media in SINGLE_TYPES:
        return None, "single-platform manifest; left unpinned so other architectures keep working"
    if media not in INDEX_TYPES:
        return None, "manifest type " + (media or "missing") + " is not a multi-arch index"
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
        return None, "registry did not return a sha256 manifest digest"
    name = reference.split("@", 1)[0]
    return f"{name}@{digest}", "pinned to the multi-arch index for the current tag"


def rewrite_latest_image(text: str, old: str, new: str) -> str:
    """Replace image lines that are exactly old. Other lines stay byte-for-byte."""
    replaced = 0

    def substitute(match: re.Match) -> str:
        nonlocal replaced
        if match.group("ref") != old:
            return match.group(0)
        replaced += 1
        quote = match.group("quote")
        return f"{match.group('indent')}image: {quote}{new}{quote}"

    updated = IMAGE_LINE.sub(substitute, text)
    if replaced == 0:
        raise CatalogAuditError(f"did not find an image line for {old}")
    return updated


def pin_latest_images(repo_root: Path, *, limit: int | None = None) -> dict:
    """Pin verifiable :latest references in app definitions and local Compose files. Returns a report."""
    report = audit_catalog(repo_root)
    targets: list[tuple[Path, str]] = []
    for item in report["container_latest_without_digest"]:
        targets.append((repo_root / item["file"], item["image"]))
    stacks = repo_root / "stacks"
    if stacks.is_dir():
        for path in sorted(stacks.rglob("*.yml")):
            for match in re.finditer(r"(?m)^[ \t]*image:\s*(['\"]?)([^'\"\s#]+)\1[ \t]*$", path.read_text(encoding="utf-8")):
                if is_latest(match.group(2)):
                    targets.append((path, match.group(2)))
    seen: set[tuple[str, str]] = set()
    pinned = []
    skipped = []
    checked = 0
    for path, image in targets:
        key = (str(path), image)
        if key in seen:
            continue
        seen.add(key)
        if limit is not None and checked >= limit:
            skipped.append({"file": str(path.relative_to(repo_root)), "image": image, "reason": "stopped at the requested limit"})
            continue
        checked += 1
        try:
            rewritten, reason = resolve_manifest(image)
        except CatalogAuditError as error:
            skipped.append({"file": str(path.relative_to(repo_root)), "image": image, "reason": str(error)})
            break
        except (OSError, urllib.error.URLError, json.JSONDecodeError, TimeoutError) as error:
            skipped.append({"file": str(path.relative_to(repo_root)), "image": image, "reason": str(error)})
            continue
        if rewritten is None:
            skipped.append({"file": str(path.relative_to(repo_root)), "image": image, "reason": reason})
            continue
        text = path.read_text(encoding="utf-8")
        path.write_text(rewrite_latest_image(text, image, rewritten), encoding="utf-8")
        pinned.append({"file": str(path.relative_to(repo_root)), "image": image, "pinned": rewritten})
    return {"pinned": pinned, "skipped": skipped, "checked": checked}
