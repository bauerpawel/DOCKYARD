"""Validates templates.json against the vendored Portainer v3 JSON Schema."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from .stack_pins import load_lock, missing_pins, third_party_stackfiles

SCHEMA_PATH = "schema/templates_schema.json"
TEMPLATES_PATH = "templates.json"


def load_schema(repo_root: Path) -> dict:
    with (repo_root / SCHEMA_PATH).open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_templates(repo_root: Path) -> None:
    templates_file = repo_root / TEMPLATES_PATH
    with templates_file.open("r", encoding="utf-8") as f:
        instance = json.load(f)

    schema = load_schema(repo_root)
    jsonschema.validate(instance=instance, schema=schema)


def validate_stack_pins(repo_root: Path) -> None:
    """Every third-party stackfile in templates.json needs a pin, or the MCP server refuses it."""
    with (repo_root / TEMPLATES_PATH).open("r", encoding="utf-8") as f:
        templates = json.load(f).get("templates", [])
    config = repo_root / "repository.json"
    own_url = json.loads(config.read_text(encoding="utf-8")).get("url") if config.exists() else None
    entries = [
        (template["repository"]["url"], template["repository"]["stackfile"])
        for template in templates
        if isinstance(template.get("repository"), dict)
    ]
    missing = missing_pins(load_lock(repo_root), third_party_stackfiles(entries, own_url))
    if missing:
        raise ValueError(
            "stackfiles without a pin in stacks.lock.json (review them, then run "
            "`python -m gallery pin-stacks`):\n  " + "\n  ".join(missing)
        )
