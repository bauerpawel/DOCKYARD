import json
from pathlib import Path

import jsonschema
import pytest

from gallery.validate import validate_templates

REPO_ROOT = Path(__file__).resolve().parents[1]

VALID_TEMPLATES = {
    "version": "3",
    "templates": [
        {
            "id": 1,
            "type": 1,
            "title": "Fake App",
            "description": "A fake app",
            "categories": ["Utilities"],
            "platform": "linux",
            "logo": "https://example.com/logo.png",
            "image": "library/fake:latest",
        }
    ],
}


def setup_repo(tmp_path: Path, templates: dict) -> Path:
    schema_src = REPO_ROOT / "schema" / "templates_schema.json"
    schema_dst = tmp_path / "schema"
    schema_dst.mkdir()
    (schema_dst / "templates_schema.json").write_text(
        schema_src.read_text(encoding="utf-8"), encoding="utf-8"
    )
    (tmp_path / "templates.json").write_text(json.dumps(templates), encoding="utf-8")
    return tmp_path


def test_valid_templates_passes(tmp_path):
    setup_repo(tmp_path, VALID_TEMPLATES)
    validate_templates(tmp_path)  # should not raise


def test_missing_required_field_fails(tmp_path):
    broken = json.loads(json.dumps(VALID_TEMPLATES))
    del broken["templates"][0]["description"]
    setup_repo(tmp_path, broken)

    with pytest.raises(jsonschema.exceptions.ValidationError):
        validate_templates(tmp_path)


def test_container_type_without_image_fails(tmp_path):
    broken = json.loads(json.dumps(VALID_TEMPLATES))
    del broken["templates"][0]["image"]
    setup_repo(tmp_path, broken)

    with pytest.raises(jsonschema.exceptions.ValidationError):
        validate_templates(tmp_path)


def test_real_generated_templates_json_is_valid():
    """The templates.json actually committed at the repo root must stay valid."""
    validate_templates(REPO_ROOT)
