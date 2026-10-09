"""Data model for a single app definition (apps/<slug>.yaml)."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import json
from pathlib import Path

from jsonschema import Draft7Validator

from .security import is_image_url, is_relative_path, is_valid_slug, is_web_url

VALID_TYPES = ("container", "compose")

_ENV_FIELDS = {"name", "label", "description", "default", "preset", "select"}
_VOLUME_FIELDS = {"container", "bind", "readonly"}


class AppValidationError(ValueError):
    """Raised when an app YAML file fails validation."""


@lru_cache(maxsize=1)
def _app_validator() -> Draft7Validator:
    path = Path(__file__).resolve().parents[2] / "schema/app_schema.json"
    return Draft7Validator(json.loads(path.read_text(encoding="utf-8")))


@dataclass
class EnvVar:
    name: str
    label: str | None = None
    description: str | None = None
    default: str | None = None
    preset: bool | None = None
    select: list[dict] | None = None


@dataclass
class Volume:
    container: str
    bind: str | None = None
    readonly: bool | None = None


@dataclass
class App:
    name: str
    slug: str
    category: str
    type: str
    logo: str
    source_file: Path
    image: str | None = None
    compose: str | None = None
    repository: dict | None = None
    description: str | None = None
    website: str | None = None
    network: str | None = None
    command: str | None = None
    privileged: bool | None = None
    ports: list[str] = field(default_factory=list)
    volumes: list[Volume] = field(default_factory=list)
    env: list[EnvVar] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict, source_file: Path, repo_root: Path) -> "App":
        if not isinstance(data, dict):
            raise AppValidationError(f"{source_file}: app definition must be a mapping")
        errors = []
        for error in _app_validator().iter_errors(data):
            path = "".join(
                f"[{part}]" if isinstance(part, int) else f".{part}" for part in error.path
            ).lstrip(".")
            errors.append(f"'{path or 'definition'}': {error.message}")

        def require(field_name: str) -> object:
            value = data.get(field_name)
            if value is None or value == "":
                errors.append(f"missing required field '{field_name}'")
            elif not isinstance(value, str):
                errors.append(f"'{field_name}' must be a string")
            return value

        name = require("name")
        slug = require("slug")
        category = require("category")
        app_type = require("type")
        logo = require("logo")
        image = data.get("image")
        compose = data.get("compose")
        repository = data.get("repository")

        if slug is not None and not is_valid_slug(slug):
            errors.append("'slug' must contain lowercase letters and numbers separated by hyphens")
        if logo not in (None, "") and not is_image_url(logo):
            errors.append("'logo' must be an absolute HTTP(S) URL without credentials or a base64 raster image")
        website = data.get("website")
        if website not in (None, "") and not is_web_url(website):
            errors.append("'website' must be an absolute HTTP(S) URL without credentials")
        if repository is not None and not isinstance(repository, dict):
            errors.append("'repository' must be a mapping")
            repository = None
        if repository:
            if not is_web_url(repository.get("url")):
                errors.append("'repository.url' must be an absolute HTTP(S) URL without credentials")
            if not is_relative_path(repository.get("stackfile")):
                errors.append("'repository.stackfile' must be a relative path without '..'")

        if app_type not in (None, *VALID_TYPES):
            errors.append(f"'type' must be one of {VALID_TYPES}, got {app_type!r}")

        has_external = bool(repository and repository.get("url") and repository.get("stackfile"))

        if app_type == "container":
            if not image:
                errors.append("type=container requires 'image'")
            if compose:
                errors.append("type=container must not set 'compose'")
            if repository:
                errors.append("type=container must not set 'repository'")
        elif app_type == "compose":
            has_local = bool(compose)
            if not has_local and not has_external:
                errors.append(
                    "type=compose requires either 'compose' (local stackfile path) "
                    "or 'repository' (external url+stackfile)"
                )
            elif has_local and has_external:
                errors.append("type=compose must set only one of 'compose' or 'repository'")
            elif has_local:
                if not is_relative_path(compose):
                    errors.append("'compose' must be a relative path within the repository")
                else:
                    target = (repo_root / compose).resolve()
                    if not target.is_relative_to(repo_root.resolve()):
                        errors.append("'compose' must stay within the repository")
                    elif not target.is_file():
                        errors.append(f"'compose' path does not exist: {compose}")
            if not image and not data.get("description"):
                errors.append(
                    "type=compose requires 'image' (for Docker Hub lookup) "
                    "when no manual 'description' is set"
                )

        if errors:
            joined = "; ".join(errors)
            raise AppValidationError(f"{source_file}: {joined}")

        env = [
            EnvVar(**{k: v for k, v in e.items() if k in _ENV_FIELDS})
            for e in data.get("env", []) or []
        ]
        volumes = [
            Volume(**{k: v for k, v in vol.items() if k in _VOLUME_FIELDS})
            for vol in data.get("volumes", []) or []
        ]

        return cls(
            name=name,
            slug=slug,
            category=category,
            type=app_type,
            image=image,
            logo=logo,
            source_file=source_file,
            compose=compose,
            repository=repository if has_external else None,
            description=data.get("description"),
            website=data.get("website"),
            network=data.get("network"),
            command=data.get("command"),
            privileged=data.get("privileged"),
            ports=list(data.get("ports", []) or []),
            volumes=volumes,
            env=env,
        )
