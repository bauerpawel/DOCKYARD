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


def test_container_entry_includes_network_when_set():
    app = make_container_app(network="host")

    entry = build_template_entry(app, index=1, cache={}, repo_url="https://github.com/x/y")

    assert entry["network"] == "host"


def test_container_entry_omits_network_when_unset():
    app = make_container_app()

    entry = build_template_entry(app, index=1, cache={}, repo_url="https://github.com/x/y")

    assert "network" not in entry


def test_container_entry_includes_command_when_set():
    app = make_container_app(command="start --foo")

    entry = build_template_entry(app, index=1, cache={}, repo_url="https://github.com/x/y")

    assert entry["command"] == "start --foo"


def test_container_entry_includes_privileged_when_set():
    app = make_container_app(privileged=True)

    entry = build_template_entry(app, index=1, cache={}, repo_url="https://github.com/x/y")

    assert entry["privileged"] is True


def test_container_entry_omits_privileged_when_unset():
    app = make_container_app()

    entry = build_template_entry(app, index=1, cache={}, repo_url="https://github.com/x/y")

    assert "privileged" not in entry


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


@pytest.mark.parametrize("factory", [make_container_app, make_compose_app])
def test_deployment_note_preserves_portainer_html_and_newlines(factory):
    note = '<p>Set the <b>required secret</b>.</p>\n<p>Read the setup guide before upgrading.</p>'
    app = factory(note=note)
    entry = build_template_entry(app, index=1, cache={}, repo_url="https://github.com/x/y")

    assert entry["note"] == note
    assert entry["description"] == app.description


@pytest.mark.parametrize("note", [None, "", "  \n"])
def test_unset_or_blank_note_is_omitted(note):
    entry = build_template_entry(make_container_app(note=note), index=1, cache={}, repo_url="https://github.com/x/y")

    assert "note" not in entry


@pytest.mark.parametrize("policy", ["always", "unless-stopped", "on-failure", "no"])
def test_explicit_container_restart_policy_reaches_portainer(policy):
    entry = build_template_entry(make_container_app(restart_policy=policy), index=1, cache={}, repo_url="https://github.com/x/y")

    assert entry["restart_policy"] == policy


def test_restart_policy_is_not_inserted_when_unset():
    for factory in [make_container_app, make_compose_app]:
        entry = build_template_entry(factory(), index=1, cache={}, repo_url="https://github.com/x/y")
        assert "restart_policy" not in entry
