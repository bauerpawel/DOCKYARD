from pathlib import Path
import shutil

from gallery.build_site import _resolve_website, build_site
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


def test_render_escapes_text_and_blocks_script_urls_from_apps_and_cache(tmp_path):
    root = Path(__file__).resolve().parents[1]
    shutil.copytree(root / "site_src", tmp_path / "site_src")
    app = make_app(name="<script>alert(1)</script>", description="<img src=x onerror=alert(1)>", website="javascript:alert(2)")
    cache = {"library/fake": {"docker_hub_url": "javascript:alert(3)"}}

    build_site(tmp_path, [app], cache)
    html = (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")

    assert "javascript:" not in html
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "<img src=x onerror=alert(1)>" not in html
