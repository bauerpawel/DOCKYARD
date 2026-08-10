"""Docker Hub metadata enrichment, with a local JSON cache.

`fetch-metadata` is the only command that talks to the network; `build` only
ever reads the cache, so it stays fast and works offline.
"""

from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from .models import App

API_URL = "https://hub.docker.com/v2/repositories/{namespace}/{repo}/"
CACHE_PATH = "cache/dockerhub.json"
REQUEST_TIMEOUT = 10
REQUEST_DELAY = 0.15  # seconds between Docker Hub calls, to stay under anonymous rate limits

_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")


def _strip_markdown_links(text: str) -> str:
    """Replace Markdown `[text](url)` links with their link text.

    Descriptions (manual or scraped from Docker Hub) are shown as plain text,
    so raw Markdown link syntax would otherwise leak into the UI verbatim.
    """
    return _MARKDOWN_LINK_RE.sub(r"\1", text)


def _clean_description(text: str) -> str:
    """Strip Markdown links and collapse embedded whitespace/newlines.

    Some imported descriptions carry literal CR/LF and multi-space runs
    (Windows-authored multi-line text pasted into a single-paragraph card
    description). Collapsing to single spaces both reads correctly and keeps
    generated files free of embedded \\r, which git's line-ending
    normalization can't safely reason about.
    """
    return re.sub(r"\s+", " ", _strip_markdown_links(text)).strip()


def is_docker_hub_image(image: str) -> bool:
    """Whether an image reference points at Docker Hub rather than another registry.

    A leading registry host (e.g. `ghcr.io/ns/repo`, `localhost:5000/ns/repo`) is
    identified the same way the `docker` CLI does: it contains a '.' or ':', or is
    literally 'localhost'. A ref with no '/' at all (e.g. `postgres:13`) is always
    an official Docker Hub image, so it must be checked before splitting on ':'
    (which would otherwise mistake the tag separator for a registry port).
    """
    parts = image.split("/")
    if len(parts) == 1:
        return True
    first_segment = parts[0]
    return "." not in first_segment and ":" not in first_segment and first_segment != "localhost"


def parse_image(image: str) -> tuple[str, str]:
    """Split a Docker Hub image reference into (namespace, repo), dropping any tag."""
    ref = image.split(":", 1)[0]
    parts = ref.split("/")
    if len(parts) == 1:
        return "library", parts[0]
    return parts[0], parts[1]


def cache_key(image: str) -> str:
    namespace, repo = parse_image(image)
    return f"{namespace}/{repo}"


def load_cache(repo_root: Path) -> dict:
    path = repo_root / CACHE_PATH
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_cache(repo_root: Path, cache: dict) -> None:
    path = repo_root / CACHE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(cache, f, indent=2, sort_keys=True)
        f.write("\n")


def fetch_repo_info(namespace: str, repo: str) -> dict:
    url = API_URL.format(namespace=namespace, repo=repo)
    response = requests.get(url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    data = response.json()
    return {
        "description": data.get("description") or None,
        "star_count": data.get("star_count"),
        "pull_count": data.get("pull_count"),
        "docker_hub_url": f"https://hub.docker.com/r/{namespace}/{repo}",
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }


def fetch_metadata(repo_root: Path, apps: list[App]) -> dict:
    """Refresh the cache for every app's image. Returns the updated cache.

    Network errors for a single image are reported and skipped, so one bad
    image doesn't abort metadata refresh for the rest.
    """
    cache = load_cache(repo_root)
    for app in apps:
        if not app.image:
            continue
        if not is_docker_hub_image(app.image):
            print(f"  skipping {app.image} (not a Docker Hub image)")
            continue
        namespace, repo = parse_image(app.image)
        key = f"{namespace}/{repo}"
        try:
            cache[key] = fetch_repo_info(namespace, repo)
            print(f"  fetched {key}")
        except requests.RequestException as exc:
            print(f"  WARNING: failed to fetch {key}: {exc}")
        time.sleep(REQUEST_DELAY)
    save_cache(repo_root, cache)
    return cache


def resolve_description(app: App, cache: dict) -> str | None:
    """Manual description always wins; otherwise fall back to the cached one."""
    if app.description:
        return _clean_description(app.description)
    if not app.image or not is_docker_hub_image(app.image):
        return None
    entry = cache.get(cache_key(app.image))
    if entry and entry.get("description"):
        return _clean_description(entry["description"])
    return None


def resolve_docker_hub_url(app: App, cache: dict) -> str | None:
    if not app.image or not is_docker_hub_image(app.image):
        return None
    entry = cache.get(cache_key(app.image))
    if entry:
        return entry.get("docker_hub_url")
    namespace, repo = parse_image(app.image)
    return f"https://hub.docker.com/r/{namespace}/{repo}"
