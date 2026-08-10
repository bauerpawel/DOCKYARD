from pathlib import Path

from gallery.build_site import _resolve_website
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


def test_manual_website_wins():
    app = make_app(website="https://example.com")

    assert _resolve_website(app) == "https://example.com"


def test_falls_back_to_repository_url_for_compose_stacks():
    app = make_app(
        type="compose",
        image=None,
        description="A fake stack",
        repository={"url": "https://github.com/example/stacks", "stackfile": "fake.yml"},
    )

    assert _resolve_website(app) == "https://github.com/example/stacks"


def test_returns_none_without_website_or_repository():
    app = make_app(website=None)

    assert _resolve_website(app) is None
