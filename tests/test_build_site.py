from html import unescape
import json
from pathlib import Path
import re
import shutil
from xml.etree import ElementTree

import pytest

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


ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ["en", "pl", "de", "fr"]


def render(tmp_path, repo_url="https://github.com/example/catalog", apps=None, domain="catalog.example", mcp="https://catalog.example/mcp"):
    shutil.copytree(ROOT / "site_src", tmp_path / "site_src")
    cname = tmp_path / "site_src" / "CNAME"
    cname.unlink(missing_ok=True)
    if domain:
        cname.write_text(domain + "\n", encoding="utf-8")
    address = tmp_path / "site_src" / "MCP_URL"
    address.unlink(missing_ok=True)
    if mcp:
        address.write_text(mcp + "\n", encoding="utf-8")
    build_site(tmp_path, apps or [make_app()], {}, repo_url)
    return (tmp_path / "docs" / "index.html").read_text(encoding="utf-8")


def repo_link(html):
    return re.search(r'<p class="repo-link">(.*?)</p>', html, flags=re.S).group(1)


def mcp_note(html):
    match = re.search(r'<div class="mcp-note">(.*?)</div>', html, flags=re.S)
    return match.group(1) if match else None


def translations(html):
    return json.loads(re.search(r'<script type="application/json" id="i18n">(.*?)</script>', html, flags=re.S).group(1))


def test_github_link_with_logo_follows_the_feed_ticket(tmp_path):
    html = render(tmp_path)

    assert html.index('class="ticket"') < html.index('class="repo-link"') < html.index('class="controls')
    link = repo_link(html)
    assert 'href="https://github.com/example/catalog"' in link
    assert link.index("<svg") < link.index("github.com/example/catalog</span>")


def test_repository_outside_github_is_linked_without_the_github_logo(tmp_path):
    link = repo_link(render(tmp_path, repo_url="https://git.example.org/team/catalog"))

    assert 'href="https://git.example.org/team/catalog"' in link
    assert "git.example.org/team/catalog</span>" in link
    assert "<svg" not in link


def test_mcp_server_address_sits_between_the_feed_ticket_and_the_repository_link(tmp_path):
    html = render(tmp_path, mcp="https://catalog.example/mcp")
    english = translations(html)["en"]

    assert html.index('class="ticket"') < html.index('class="mcp-note"') < html.index('class="repo-link"')
    note = mcp_note(html)
    assert 'href="https://catalog.example/mcp"' in note
    assert ">https://catalog.example/mcp</a>" in note
    assert english["mcp_label"] in note
    assert english["mcp_hint"] in note


@pytest.mark.parametrize("address", [None, "javascript:alert(1)", "catalog.example/mcp"])
def test_site_without_a_usable_mcp_address_shows_no_mcp_note(tmp_path, address):
    html = render(tmp_path, mcp=address)

    assert mcp_note(html) is None
    assert "javascript:" not in html


def test_language_switcher_links_every_language(tmp_path):
    switcher = re.search(r'<nav class="lang-switch".*?</nav>', render(tmp_path), flags=re.S).group(0)

    assert re.findall(r'data-lang="(\w+)"', switcher) == LANGUAGES
    assert re.findall(r'href="([^"]*)"', switcher) == ["./", "?lang=pl", "?lang=de", "?lang=fr"]
    assert switcher.count('aria-current="true"') == 1


def test_translations_cover_the_same_strings_in_every_language(tmp_path):
    table = translations(render(tmp_path))

    assert list(table) == LANGUAGES
    for language in LANGUAGES[1:]:
        assert set(table[language]) == set(table["en"]), language
        assert set(table[language]["categories"]) == set(table["en"]["categories"]), language
        assert all(value.strip() for key, value in table[language].items() if key != "categories"), language


def test_page_marks_only_strings_that_have_translations(tmp_path):
    html = render(tmp_path)
    english = translations(html)["en"]

    marked = set(re.findall(r'data-i18n(?:-[a-z-]+)?="([a-z_]+)"', html))
    assert {"tagline", "ticket_label", "copy", "search_placeholder", "all", "empty"} <= marked
    assert marked <= set(english)
    assert english["tagline"] in html


def test_marked_elements_start_with_their_english_string(tmp_path):
    html = render(tmp_path)
    english = translations(html)["en"]

    rendered = re.findall(r'data-i18n="([a-z_]+)"[^>]*>([^<]*)<', html)
    assert "copy" in dict(rendered)
    for key, text in rendered:
        assert unescape(text) == english[key], key


def test_translated_titles_carry_the_app_count(tmp_path):
    table = translations(render(tmp_path, apps=[make_app(), make_app(name="Second", slug="second")]))

    for language in LANGUAGES:
        assert "2" in table[language]["meta_title"], language
        assert "{count}" not in json.dumps(table[language]), language


def test_every_catalog_category_is_translated():
    feed = json.loads((ROOT / "templates.json").read_text(encoding="utf-8"))
    used = {category for template in feed["templates"] for category in template.get("categories", [])}
    table = json.loads((ROOT / "site_src" / "i18n.json").read_text(encoding="utf-8"))

    for language in LANGUAGES:
        assert used <= set(table[language]["categories"]), f"add the missing categories to site_src/i18n.json ({language})"


def test_search_engines_get_canonical_urls_and_a_social_card(tmp_path):
    html = render(tmp_path)

    assert '<link rel="canonical" href="https://catalog.example/">' in html
    assert dict(re.findall(r'<link rel="alternate" hreflang="([\w-]+)" href="([^"]+)">', html)) == {
        "x-default": "https://catalog.example/",
        "en": "https://catalog.example/",
        "pl": "https://catalog.example/?lang=pl",
        "de": "https://catalog.example/?lang=de",
        "fr": "https://catalog.example/?lang=fr",
    }
    assert '<meta property="og:url" content="https://catalog.example/">' in html
    assert '<meta property="og:image" content="https://catalog.example/static/dockyard-social-preview.png">' in html
    assert '<meta name="twitter:card" content="summary_large_image">' in html
    assert (tmp_path / "docs" / "static" / "dockyard-social-preview.png").is_file()


def test_structured_data_describes_the_site_and_the_feed(tmp_path):
    html = render(tmp_path)

    data = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, flags=re.S).group(1))
    nodes = {node["@type"]: node for node in data["@graph"]}
    assert data["@context"] == "https://schema.org"
    assert nodes["WebSite"]["url"] == "https://catalog.example/"
    assert nodes["WebSite"]["inLanguage"] == LANGUAGES
    assert nodes["DataFeed"]["url"] == "https://cdn.jsdelivr.net/gh/example/catalog@main/templates.json"


def test_robots_and_sitemap_list_every_language_version(tmp_path):
    render(tmp_path)

    robots = (tmp_path / "docs" / "robots.txt").read_text(encoding="utf-8")
    assert robots.splitlines() == ["User-agent: *", "Allow: /", "", "Sitemap: https://catalog.example/sitemap.xml"]
    sitemap = ElementTree.parse(tmp_path / "docs" / "sitemap.xml")
    locations = [node.text for node in sitemap.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.sitemaps.org/schemas/sitemap/0.9}loc")]
    assert locations == ["https://catalog.example/", "https://catalog.example/?lang=pl", "https://catalog.example/?lang=de", "https://catalog.example/?lang=fr"]
    alternates = sitemap.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url/{http://www.w3.org/1999/xhtml}link")
    assert len(alternates) == 4 * 5


def test_site_without_a_domain_claims_no_absolute_urls(tmp_path):
    html = render(tmp_path, domain=None)

    for claim in ('rel="canonical"', 'rel="alternate"', "og:url", "og:image", "twitter:image"):
        assert claim not in html
    assert (tmp_path / "docs" / "robots.txt").read_text(encoding="utf-8").splitlines() == ["User-agent: *", "Allow: /"]
    assert not (tmp_path / "docs" / "sitemap.xml").exists()
