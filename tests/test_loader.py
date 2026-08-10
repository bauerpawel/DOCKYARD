from pathlib import Path

import pytest

from gallery.loader import load_apps
from gallery.models import AppValidationError

VALID_CONTAINER = """\
name: Test App
slug: test-app
category: Utilities
type: container
image: library/test:latest
description: A test app
logo: https://example.com/logo.png
website: https://example.com
ports: ["80/tcp"]
volumes: []
env: []
"""


def write_app(apps_dir: Path, filename: str, content: str) -> None:
    apps_dir.mkdir(parents=True, exist_ok=True)
    (apps_dir / filename).write_text(content, encoding="utf-8")


def test_load_valid_container_app(tmp_path):
    write_app(tmp_path / "apps", "test-app.yaml", VALID_CONTAINER)

    apps = load_apps(tmp_path)

    assert len(apps) == 1
    app = apps[0]
    assert app.slug == "test-app"
    assert app.type == "container"
    assert app.image == "library/test:latest"
    assert app.ports == ["80/tcp"]


def test_container_without_image_raises(tmp_path):
    content = VALID_CONTAINER.replace('image: library/test:latest', 'image: ""')
    write_app(tmp_path / "apps", "test-app.yaml", content)

    with pytest.raises(AppValidationError, match="requires 'image'"):
        load_apps(tmp_path)


def test_compose_without_compose_path_raises(tmp_path):
    content = VALID_CONTAINER.replace("type: container", "type: compose")
    write_app(tmp_path / "apps", "test-app.yaml", content)

    with pytest.raises(AppValidationError, match="requires either 'compose'"):
        load_apps(tmp_path)


def test_compose_with_missing_file_raises(tmp_path):
    content = VALID_CONTAINER.replace("type: container", "type: compose")
    content += "compose: stacks/test-app/docker-compose.yml\n"
    write_app(tmp_path / "apps", "test-app.yaml", content)

    with pytest.raises(AppValidationError, match="does not exist"):
        load_apps(tmp_path)


def test_compose_with_existing_file_succeeds(tmp_path):
    content = VALID_CONTAINER.replace("type: container", "type: compose")
    content += "compose: stacks/test-app/docker-compose.yml\n"
    write_app(tmp_path / "apps", "test-app.yaml", content)

    stack_dir = tmp_path / "stacks" / "test-app"
    stack_dir.mkdir(parents=True)
    (stack_dir / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")

    apps = load_apps(tmp_path)

    assert apps[0].type == "compose"
    assert apps[0].compose == "stacks/test-app/docker-compose.yml"


def test_duplicate_slug_raises(tmp_path):
    write_app(tmp_path / "apps", "a.yaml", VALID_CONTAINER)
    write_app(tmp_path / "apps", "b.yaml", VALID_CONTAINER)

    with pytest.raises(AppValidationError, match="duplicate slug"):
        load_apps(tmp_path)


def test_missing_required_field_raises(tmp_path):
    content = VALID_CONTAINER.replace("logo: https://example.com/logo.png", 'logo: ""')
    write_app(tmp_path / "apps", "test-app.yaml", content)

    with pytest.raises(AppValidationError, match="logo"):
        load_apps(tmp_path)


def test_compose_with_external_repository_succeeds(tmp_path):
    content = VALID_CONTAINER.replace("type: container", "type: compose")
    content = content.replace("image: library/test:latest\n", "")
    content += 'repository:\n  url: https://github.com/someone/templates\n  stackfile: stacks/test-app/docker-compose.yml\n'
    write_app(tmp_path / "apps", "test-app.yaml", content)

    apps = load_apps(tmp_path)

    assert apps[0].type == "compose"
    assert apps[0].compose is None
    assert apps[0].repository == {
        "url": "https://github.com/someone/templates",
        "stackfile": "stacks/test-app/docker-compose.yml",
    }


def test_compose_without_image_or_description_raises(tmp_path):
    content = VALID_CONTAINER.replace("type: container", "type: compose")
    content = content.replace("image: library/test:latest\n", "")
    content = content.replace("description: A test app\n", "description: null\n")
    content += "compose: stacks/test-app/docker-compose.yml\n"
    write_app(tmp_path / "apps", "test-app.yaml", content)

    stack_dir = tmp_path / "stacks" / "test-app"
    stack_dir.mkdir(parents=True)
    (stack_dir / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")

    with pytest.raises(AppValidationError, match="requires 'image'"):
        load_apps(tmp_path)


def test_load_apps_sorted_by_slug(tmp_path):
    write_app(tmp_path / "apps", "z.yaml", VALID_CONTAINER.replace("slug: test-app", "slug: zzz-app"))
    write_app(tmp_path / "apps", "a.yaml", VALID_CONTAINER.replace("slug: test-app", "slug: aaa-app"))

    apps = load_apps(tmp_path)

    assert [a.slug for a in apps] == ["aaa-app", "zzz-app"]
