"""Loads app definitions from apps/*.yaml into App objects."""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import App, AppValidationError


def load_apps(repo_root: Path) -> list[App]:
    apps_dir = repo_root / "apps"
    if not apps_dir.is_dir():
        raise AppValidationError(f"{apps_dir}: app directory does not exist")
    files = sorted(apps_dir.glob("*.yaml")) + sorted(apps_dir.glob("*.yml"))
    if not files:
        raise AppValidationError(f"{apps_dir}: no app definitions found")

    apps: list[App] = []
    errors: list[str] = []

    for path in files:
        try:
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            apps.append(App.from_dict(data, source_file=path, repo_root=repo_root))
        except yaml.YAMLError as exc:
            mark = getattr(exc, "problem_mark", None)
            location = f":{mark.line + 1}:{mark.column + 1}" if mark else ""
            errors.append(f"{path}{location}: invalid YAML: {exc}")
        except OSError as exc:
            errors.append(f"{path}: cannot read definition: {exc}")
        except AppValidationError as exc:
            errors.append(str(exc))

    seen_slugs: dict[str, Path] = {}
    for app in apps:
        if app.slug in seen_slugs:
            errors.append(
                f"duplicate slug '{app.slug}' in {app.source_file} and {seen_slugs[app.slug]}"
            )
        else:
            seen_slugs[app.slug] = app.source_file

    if errors:
        raise AppValidationError("\n".join(errors))

    return sorted(apps, key=lambda a: a.slug)
