"""Validates templates.json against the vendored Portainer v3 JSON Schema."""

from __future__ import annotations

import json
from pathlib import Path

import jsonschema

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
