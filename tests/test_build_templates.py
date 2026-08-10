from pathlib import Path

import pytest

from gallery.build_templates import (
    TemplateBuildError,
    build_template_entry,
    build_templates,
)
from gallery.models import App

FAKE_SOURCE = Path("apps/fake.yaml")


def make_container_app(**overrides) -> App:
    defaults = dict(
        name="Fake App",
        slug="fake-app",
        category="Utilities",
        type="container",
        image="library/fake:latest",
        logo="https://example.com/logo.png",
        source_file=FAKE_SOURCE,
        description="A fake app",
    )
    defaults.update(overrides)
    return App(**defaults)


def make_compose_app(**overrides) -> App:
    defaults = dict(
        name="Fake Stack",
        slug="fake-stack",
        category="Productivity",
        type="compose",
        image="library/fake:latest",
        compose="stacks/fake-stack/docker-compose.yml",
        logo="https://example.com/logo.png",
        source_file=FAKE_SOURCE,
        description="A fake stack",
    )
    defaults.update(overrides)
    return App(**defaults)


def test_container_entry_has_image_and_type_1():
    app = make_container_app(ports=["80/tcp"])

    entry = build_template_entry(app, index=1, cache={}, repo_url="https://github.com/x/y")

    assert entry["type"] == 1
    assert entry["image"] == "library/fake:latest"
    assert "repository" not in entry
    assert entry["ports"] == ["80/tcp"]
    assert entry["categories"] == ["Utilities"]
    assert entry["name"] == "fake-app"


def test_compose_entry_has_repository_and_type_3():
    app = make_compose_app()

    entry = build_template_entry(app, index=2, cache={}, repo_url="https://github.com/x/y")

    assert entry["type"] == 3
    assert "image" not in entry
    assert entry["repository"] == {
        "url": "https://github.com/x/y",
        "stackfile": "stacks/fake-stack/docker-compose.yml",
    }


def test_external_repository_used_verbatim_ignoring_repo_url():
    app = make_compose_app(
        image=None,
        compose=None,
        repository={"url": "https://github.com/someone/templates", "stackfile": "stacks/x/docker-compose.yml"},
    )

    entry = build_template_entry(app, index=1, cache={}, repo_url="https://github.com/x/y")

    assert entry["repository"] == {
        "url": "https://github.com/someone/templates",
        "stackfile": "stacks/x/docker-compose.yml",
    }


def test_manual_description_overrides_cache():
    app = make_container_app(description="Manual description")
    cache = {"library/fake": {"description": "Cached description"}}

    entry = build_template_entry(app, index=1, cache=cache, repo_url="https://github.com/x/y")

    assert entry["description"] == "Manual description"


def test_cached_description_used_when_no_manual_override():
    app = make_container_app(description=None)
    cache = {"library/fake": {"description": "Cached description"}}

    entry = build_template_entry(app, index=1, cache=cache, repo_url="https://github.com/x/y")

    assert entry["description"] == "Cached description"


def test_missing_description_raises():
    app = make_container_app(description=None)

    with pytest.raises(TemplateBuildError, match="no description available"):
        build_template_entry(app, index=1, cache={}, repo_url="https://github.com/x/y")


def test_stable_ids_across_two_builds():
    apps = [
        make_container_app(slug="aaa", name="AAA"),
        make_container_app(slug="bbb", name="BBB"),
        make_compose_app(slug="ccc", name="CCC"),
    ]

    first = build_templates(apps, cache={})
    second = build_templates(apps, cache={})

    ids_by_slug_first = {t["title"]: t["id"] for t in first["templates"]}
    ids_by_slug_second = {t["title"]: t["id"] for t in second["templates"]}
    assert ids_by_slug_first == ids_by_slug_second
    assert first["version"] == "3"
