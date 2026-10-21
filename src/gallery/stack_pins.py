"""Pins third-party stackfiles to a reviewed commit and SHA-256 digest.

`templates.json` must stay a plain Portainer v3 feed, so pins live next to it in
`stacks.lock.json`. The MCP server serves a third-party stackfile only from the
pinned commit and only when its bytes match the recorded digest, so an upstream
change cannot alter a deploy plan until a maintainer reviews it and pins again.

`pin-stacks` is the only command here that talks to the network; `validate`
only checks that every third-party stackfile in the feed has a pin.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests

LOCK_PATH = "stacks.lock.json"
LOCK_VERSION = 1
COMMIT_URL = "https://api.github.com/repos/{owner}/{repo}/commits/{ref}"
RAW_URL = "https://raw.githubusercontent.com/{owner}/{repo}/{commit}/{path}"
STACK_MAX_BYTES = 524288  # same cap as DOCKYARD_STACK_MAX_BYTES in mcp/index.php
REQUEST_TIMEOUT = 10

_REPO_PATH_RE = re.compile(r"^([^/]+)/([^/]+?)(?:\.git)?(?:/tree/([^/]+))?$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")


def parse_github_repository(url: str) -> tuple[str, str, str | None] | None:
    """(owner, repo, ref) for an https GitHub repository URL, parsed like dockyard_stack_url."""
    parts = urlsplit(url.strip())
    if parts.scheme != "https" or parts.username or parts.password:
        return None
    if (parts.hostname or "") not in ("github.com", "www.github.com"):
        return None
    match = _REPO_PATH_RE.match(parts.path.strip("/"))
    if match is None:
        return None
    return match.group(1), match.group(2), match.group(3)


def repository_key(owner: str, repo: str) -> str:
    """Lock key for a repository; GitHub owner and repository names are case-insensitive."""
    return f"{owner}/{repo}".lower()


def is_own_repository(url: str, own_url: str | None) -> bool:
    """Mirror of dockyard_is_local_repository: the MCP server reads these stacks from its own copy."""
    if not own_url:
        return False
    own = parse_github_repository(own_url)
    other = parse_github_repository(url)
    if own is None or other is None:
        return False
    # Owner and repository compare exactly, as in PHP; only the default ref is normalized.
    own_ref = "main" if own[2] in (None, "HEAD", "main") else own[2]
    other_ref = "main" if other[2] in (None, "HEAD", "main") else other[2]
    return own[:2] == other[:2] and own_ref == other_ref


def third_party_stackfiles(entries: Iterable[tuple[str, str]], own_url: str | None) -> dict[str, dict]:
    """Group (repository URL, stackfile) pairs by repository, skipping this catalog's own stacks."""
    wanted: dict[str, dict] = {}
    for url, stackfile in entries:
        if is_own_repository(url, own_url):
            continue
        parsed = parse_github_repository(url)
        if parsed is None:
            raise ValueError(f"{url}: stack repository must be an https://github.com/OWNER/REPO URL")
        owner, repo, ref = parsed
        key = repository_key(owner, repo)
        group = wanted.setdefault(key, {"owner": owner, "repo": repo, "ref": ref, "stackfiles": set()})
        if group["ref"] != ref:
            raise ValueError(f"{key}: templates ask for different refs ({group['ref'] or 'HEAD'} and {ref or 'HEAD'})")
        group["stackfiles"].add(stackfile.replace("\\", "/"))
    return wanted


def load_lock(repo_root: Path) -> dict:
    path = repo_root / LOCK_PATH
    if not path.exists():
        return {"version": LOCK_VERSION, "repositories": {}}
    with path.open("r", encoding="utf-8") as f:
        lock = json.load(f)
    if not isinstance(lock, dict) or not isinstance(lock.get("repositories"), dict):
        raise ValueError(f"{path}: expected an object with a 'repositories' map")
    return lock


def save_lock(repo_root: Path, lock: dict) -> None:
    with (repo_root / LOCK_PATH).open("w", encoding="utf-8", newline="\n") as f:
        json.dump(lock, f, indent=2, sort_keys=True)
        f.write("\n")


def missing_pins(lock: dict, wanted: dict[str, dict]) -> list[str]:
    """Every wanted stackfile without a well-formed pin, as 'owner/repo: path'."""
    missing = []
    repositories = lock.get("repositories", {})
    for key, group in sorted(wanted.items()):
        pinned = repositories.get(key)
        commit_ok = isinstance(pinned, dict) and _COMMIT_RE.match(str(pinned.get("commit", ""))) is not None
        files = pinned.get("stackfiles", {}) if isinstance(pinned, dict) else {}
        for stackfile in sorted(group["stackfiles"]):
            if not commit_ok or not isinstance(files, dict) or _DIGEST_RE.match(str(files.get(stackfile, ""))) is None:
                missing.append(f"{key}: {stackfile}")
    return missing


def resolve_commit(session, owner: str, repo: str, ref: str) -> str:
    url = COMMIT_URL.format(owner=quote(owner, safe=""), repo=quote(repo, safe=""), ref=quote(ref, safe=""))
    response = session.get(url, headers={"Accept": "application/vnd.github.sha"}, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    commit = response.text.strip()
    if _COMMIT_RE.match(commit) is None:
        raise ValueError(f"{owner}/{repo}@{ref}: GitHub did not return a commit SHA")
    return commit


def fetch_stackfile(session, owner: str, repo: str, commit: str, stackfile: str) -> bytes:
    url = RAW_URL.format(owner=quote(owner, safe=""), repo=quote(repo, safe=""), commit=commit, path=quote(stackfile))
    response = session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
    try:
        response.raise_for_status()
        body = b""
        for chunk in response.iter_content(65536):
            body += chunk
            if len(body) > STACK_MAX_BYTES:
                raise ValueError(f"{url}: stackfile is larger than {STACK_MAX_BYTES} bytes")
    finally:
        response.close()
    if not body:
        raise ValueError(f"{url}: stackfile is empty")
    return body


def pin_stacks(repo_root: Path, wanted: dict[str, dict], update: bool = False, session=None) -> dict:
    """Pin every wanted stackfile and drop pins nothing refers to any more.

    Without `update`, existing pins stay on their reviewed commit and only new
    stackfiles are pinned (at that same commit). With `update`, every repository
    moves to the current head of its ref. A repository whose commit cannot be
    resolved keeps its old pins, and a stackfile that cannot be fetched stays
    unpinned; the lock is saved anyway and the failures are raised afterwards.
    """
    session = session or requests.Session()
    old = load_lock(repo_root).get("repositories", {})
    repositories: dict[str, dict] = {}
    failures: list[str] = []
    for key, group in sorted(wanted.items()):
        previous = old.get(key) if isinstance(old.get(key), dict) else None
        if previous is not None and _COMMIT_RE.match(str(previous.get("commit", ""))) is None:
            previous = None
        try:
            if previous is None or update:
                commit = resolve_commit(session, group["owner"], group["repo"], group["ref"] or "HEAD")
            else:
                commit = previous["commit"]
        except (requests.RequestException, ValueError) as exc:
            failures.append(f"{key}: {exc}")
            if previous is not None:
                repositories[key] = previous
            continue
        known = previous.get("stackfiles", {}) if previous and previous.get("commit") == commit else {}
        stackfiles = {}
        for stackfile in sorted(group["stackfiles"]):
            if stackfile in known:
                stackfiles[stackfile] = known[stackfile]
                continue
            try:
                body = fetch_stackfile(session, group["owner"], group["repo"], commit, stackfile)
            except (requests.RequestException, ValueError) as exc:
                failures.append(f"{key}: {stackfile}: {exc}")
                continue
            stackfiles[stackfile] = hashlib.sha256(body).hexdigest()
            print(f"  pinned {key}@{commit[:12]} {stackfile}")
        repositories[key] = {"commit": commit, "stackfiles": stackfiles}
    save_lock(repo_root, {"version": LOCK_VERSION, "repositories": repositories})
    if failures:
        raise RuntimeError("could not pin:\n  " + "\n  ".join(failures))
    return repositories
