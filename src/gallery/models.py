"""Data model for a single app definition (apps/<slug>.yaml)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

VALID_TYPES = ("container", "compose")

_ENV_FIELDS = {"name", "label", "description", "default", "preset", "select"}
_VOLUME_FIELDS = {"container", "bind", "readonly"}


class AppValidationError(ValueError):
    """Raised when an app YAML file fails validation."""


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
        errors = []

        def require(field_name: str) -> object:
            value = data.get(field_name)
            if value in (None, ""):
                errors.append(f"missing required field '{field_name}'")
            return value

        name = require("name")
        slug = require("slug")
        category = require("category")
        app_type = require("type")
        logo = require("logo")
        image = data.get("image")
        compose = data.get("compose")
        repository = data.get("repository")

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
            elif has_local and not (repo_root / compose).is_file():
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
