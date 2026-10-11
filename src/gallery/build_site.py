"""Renders the static browsing site (docs/) from the same App data used for templates.json."""

from __future__ import annotations

import json
import re
import shutil
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse
from xml.sax.saxutils import escape

from jinja2 import Environment, FileSystemLoader

from .config import repository_url
from .dockerhub import resolve_description, resolve_docker_hub_url
from .models import App
from .security import is_image_url, is_web_url

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


def load_translations(repo_root: Path, app_count: int) -> dict:
    """Site strings per language, English first. "{count}" in a string becomes the number of apps."""
    raw = (repo_root / SITE_SRC / "i18n.json").read_text(encoding="utf-8")
    return json.loads(raw.replace("{count}", str(app_count)))


def site_url(repo_root: Path) -> str | None:
    """The site's public address. It is known only when site_src/CNAME names the domain."""
    cname = repo_root / SITE_SRC / "CNAME"
    domain = cname.read_text(encoding="utf-8").strip() if cname.is_file() else ""
    return f"https://{domain}" if re.fullmatch(r"[A-Za-z0-9.-]+", domain) else None


def _structured_data(description: str, codes: list[str], feed_url: str, repo_url: str, public_url: str | None, app_count: int) -> dict:
    site = {
        "@type": "WebSite",
        "name": "Dockyard",
        "alternateName": "Dockyard Portainer App Templates",
        "description": description,
        "inLanguage": codes,
        "license": "https://opensource.org/licenses/MIT",
        "author": {"@type": "Person", "name": "Paweł Bauer", "url": "https://bauer.net.pl"},
    }
    if public_url:
        site["url"] = f"{public_url}/"
    feed = {
        "@type": "DataFeed",
        "name": "Dockyard Portainer app templates",
        "description": f"Portainer v3 app template feed with {app_count} Docker apps.",
        "url": feed_url,
        "encodingFormat": "application/json",
        "license": "https://opensource.org/licenses/MIT",
        "isBasedOn": repo_url,
    }
    return {"@context": "https://schema.org", "@graph": [site, feed]}


def _write_crawler_files(out_dir: Path, public_url: str | None, languages: list[dict]) -> None:
    """robots.txt always; sitemap.xml with every language version once the public address is known."""
    robots = ["User-agent: *", "Allow: /"]
    if public_url:
        robots += ["", f"Sitemap: {public_url}/sitemap.xml"]
        urls = [f"{public_url}/{language['query']}" for language in languages]
        alternates = [("x-default", urls[0]), *((language["code"], url) for language, url in zip(languages, urls))]
        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">']
        for url in urls:
            lines += ["  <url>", f"    <loc>{escape(url)}</loc>"]
            lines += [f'    <xhtml:link rel="alternate" hreflang="{code}" href="{escape(other)}"/>' for code, other in alternates]
            lines.append("  </url>")
        lines.append("</urlset>")
        (out_dir / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    (out_dir / "robots.txt").write_text("\n".join(robots) + "\n", encoding="utf-8", newline="\n")


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


def build_site(repo_root: Path, apps: list[App], cache: dict, repo_url: str | None = None, *, output_dir: Path | None = None) -> None:
    repo_url = repository_url(repo_root, repo_url)
    app_views = sorted((_app_view(app, cache) for app in apps), key=lambda a: a["name"].lower())
    category_counts = Counter(a["category"] for a in app_views)
    categories = sorted(category_counts.items())
    translations = load_translations(repo_root, len(app_views))
    default = next(iter(translations))
    languages = [
        {"code": code, "name": strings["language_name"], "query": "" if code == default else f"?lang={code}",
         "href": "./" if code == default else f"?lang={code}"}
        for code, strings in translations.items()
    ]
    public_url = site_url(repo_root)
    feed_url = templates_feed_url(repo_url)
    repo = urlparse(repo_url)

    env = Environment(
        loader=FileSystemLoader(str(repo_root / SITE_SRC / "templates")),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["web_url"] = lambda value: value if is_web_url(value) else ""
    env.filters["image_url"] = lambda value: value if is_image_url(value) else ""
    # The translation table keeps its language order and stays readable in the page source.
    env.policies["json.dumps_kwargs"] = {"sort_keys": False, "ensure_ascii": False}
    template = env.get_template("index.html.j2")
    html = template.render(
        apps=app_views,
        categories=categories,
        templates_feed_url=feed_url,
        repo_url=repo_url,
        repo_label=f"{repo.netloc}{repo.path}".rstrip("/"),
        repo_on_github=repo.netloc == "github.com",
        t=translations[default],
        i18n=translations,
        languages=languages,
        site_url=public_url,
        structured_data=_structured_data(
            translations[default]["meta_description"], list(translations), feed_url, repo_url, public_url, len(app_views)),
    )

    out_dir = output_dir if output_dir is not None else repo_root / OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "index.html").write_text(html, encoding="utf-8", newline="\n")
    _write_crawler_files(out_dir, public_url, languages)

    static_src = repo_root / SITE_SRC / "static"
    static_dst = out_dir / "static"
    shutil.copytree(static_src, static_dst, dirs_exist_ok=True)
    for name in ("CNAME", ".nojekyll"):
        source = repo_root / SITE_SRC / name
        if source.is_file():
            shutil.copyfile(source, out_dir / name)
