"""Renders the static browsing site (docs/) from the same App data used for templates.json."""

from __future__ import annotations

import shutil
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader

from .build_templates import DEFAULT_REPO_URL
from .dockerhub import resolve_description, resolve_docker_hub_url
from .models import App

SITE_SRC = "site_src"
OUTPUT_DIR = "docs"


def templates_feed_url(repo_url: str) -> str:
    """Turn a GitHub repo URL into its jsDelivr CDN URL for templates.json on main.

    jsDelivr fronts raw GitHub content with a cached CDN, so the feed loads
    faster and more reliably worldwide than raw.githubusercontent.com.
    """
    parsed = urlparse(repo_url)
    if parsed.netloc != "github.com":
        return f"{repo_url.rstrip('/')}/templates.json"
    owner_repo = parsed.path.strip("/").removesuffix(".git")
    return f"https://cdn.jsdelivr.net/gh/{owner_repo}@main/templates.json"


def _resolve_website(app: App) -> str | None:
    """Manual website always wins; otherwise fall back to the stack's source repo."""
    if app.website:
        return app.website
    if app.repository and app.repository.get("url"):
        return app.repository["url"]
    return None


def _app_view(app: App, cache: dict) -> dict:
    return {
        "name": app.name,
        "slug": app.slug,
        "category": app.category,
        "type": app.type,
        "description": resolve_description(app, cache) or "No description available yet.",
        "logo": app.logo,
        "website": _resolve_website(app),
        "docker_hub_url": resolve_docker_hub_url(app, cache),
    }


def build_site(repo_root: Path, apps: list[App], cache: dict, repo_url: str = DEFAULT_REPO_URL) -> None:
    app_views = sorted((_app_view(app, cache) for app in apps), key=lambda a: a["name"].lower())
    category_counts = Counter(a["category"] for a in app_views)
    categories = sorted(category_counts.items())

    env = Environment(
        loader=FileSystemLoader(str(repo_root / SITE_SRC / "templates")),
        autoescape=True,
    )
    template = env.get_template("index.html.j2")
    html = template.render(
        apps=app_views,
        categories=categories,
        templates_feed_url=templates_feed_url(repo_url),
        repo_url=repo_url,
    )

    out_dir = repo_root / OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8")

    static_src = repo_root / SITE_SRC / "static"
    static_dst = out_dir / "static"
    shutil.copytree(static_src, static_dst, dirs_exist_ok=True)
