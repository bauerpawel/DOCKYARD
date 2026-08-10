from pathlib import Path

import pytest

from gallery.dockerhub import is_docker_hub_image, resolve_description, resolve_docker_hub_url
from gallery.models import App

FAKE_SOURCE = Path("apps/fake.yaml")


def make_app(**overrides) -> App:
    defaults = dict(
        name="Fake App",
        slug="fake-app",
        category="Utilities",
        type="container",
        image="library/fake:latest",
        logo="https://example.com/logo.png",
        source_file=FAKE_SOURCE,
    )
    defaults.update(overrides)
    return App(**defaults)


@pytest.mark.parametrize(
    "image,expected",
    [
        ("postgres:13", True),
        ("httpd:latest", True),
        ("linuxserver/openvpn-as", True),
        ("ghcr.io/morgankryze/cairn:latest", False),
        ("lscr.io/linuxserver/code-server:latest", False),
        ("registry.gitlab.com/bockiii/deemix-docker", False),
        ("localhost:5000/ns/repo", False),
        ("docker.elastic.co/elasticsearch/elasticsearch:7.15.1", False),
    ],
)
def test_is_docker_hub_image(image, expected):
    assert is_docker_hub_image(image) == expected


def test_resolve_description_strips_markdown_links():
    app = make_app(
        description=(
            "[Airsonic-advanced](https://github.com/kagemomiji/airsonic-advanced) "
            "is a free, web-based media streamer."
        )
    )

    assert resolve_description(app, cache={}) == (
        "Airsonic-advanced is a free, web-based media streamer."
    )


def test_resolve_description_strips_markdown_links_from_cache():
    app = make_app(description=None, image="linuxserver/example")
    cache = {"linuxserver/example": {"description": "[Example](https://example.com) does things."}}

    assert resolve_description(app, cache) == "Example does things."


def test_resolve_docker_hub_url_skips_non_docker_hub_images():
    app = make_app(image="ghcr.io/example/example:latest")

    assert resolve_docker_hub_url(app, cache={}) is None


def test_resolve_description_skips_non_docker_hub_images_without_manual_description():
    app = make_app(description=None, image="ghcr.io/example/example:latest")

    assert resolve_description(app, cache={}) is None
