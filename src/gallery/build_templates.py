"""Builds the Portainer v3 templates.json from loaded App objects."""

from __future__ import annotations

from dataclasses import asdict

from .dockerhub import resolve_description
from .models import App

DEFAULT_REPO_URL = "https://github.com/OWNER/REPO"


class TemplateBuildError(ValueError):
    """Raised when an app can't be turned into a valid template entry."""


def _env_entries(app: App) -> list[dict]:
    entries = []
    for env in app.env:
        entry = {k: v for k, v in asdict(env).items() if v is not None}
        entries.append(entry)
    return entries


def _volume_entries(app: App) -> list[dict]:
    entries = []
    for vol in app.volumes:
        entry = {k: v for k, v in asdict(vol).items() if v is not None}
        entries.append(entry)
    return entries


def build_template_entry(app: App, index: int, cache: dict, repo_url: str) -> dict:
    description = resolve_description(app, cache)
    if not description:
        raise TemplateBuildError(
            f"{app.source_file}: no description available for '{app.slug}' - "
            "set a manual 'description' or run `gallery fetch-metadata` first"
        )

    entry: dict = {
        "id": index,
        "type": 1 if app.type == "container" else 3,
        "title": app.name,
        "description": description,
        "categories": [app.category],
        "platform": "linux",
        "logo": app.logo,
        "name": app.slug,
    }

    if app.type == "container":
        entry["image"] = app.image
    elif app.repository:
        entry["repository"] = dict(app.repository)
    else:
        entry["repository"] = {"url": repo_url, "stackfile": app.compose}

    if app.ports:
        entry["ports"] = app.ports
    volumes = _volume_entries(app)
    if volumes:
        entry["volumes"] = volumes
    env = _env_entries(app)
    if env:
        entry["env"] = env

    return entry


def build_templates(apps: list[App], cache: dict, repo_url: str = DEFAULT_REPO_URL) -> dict:
    templates = [
        build_template_entry(app, index, cache, repo_url)
        for index, app in enumerate(apps, start=1)
    ]
    return {"version": "3", "templates": templates}
