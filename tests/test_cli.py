import pytest
import yaml
import json
from pathlib import Path
import shutil

from gallery import cli
from gallery import publish

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def build_repo(tmp_path, monkeypatch):
    (tmp_path / "apps").mkdir()
    (tmp_path / "apps/app.yaml").write_text(yaml.safe_dump({
        "name": "App", "slug": "app", "category": "Other", "type": "compose",
        "compose": "stacks/app/docker-compose.yml", "description": "Test app",
        "logo": "https://example.com/logo.png",
    }), encoding="utf-8")
    (tmp_path / "stacks/app").mkdir(parents=True)
    (tmp_path / "stacks/app/docker-compose.yml").write_text("services: {}\n")
    shutil.copytree(ROOT / "schema", tmp_path / "schema")
    shutil.copytree(ROOT / "site_src", tmp_path / "site_src")
    (tmp_path / "docs/static").mkdir(parents=True)
    (tmp_path / "docs/index.html").write_text("old site")
    (tmp_path / "docs/CNAME").write_text("old.example\n")
    (tmp_path / "docs/static/obsolete.js").write_text("old asset")
    (tmp_path / "templates.json").write_text("old feed")
    (tmp_path / "repository.json").write_text('{"url":"https://github.com/example/fork"}')
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    return tmp_path


@pytest.mark.parametrize("slug", ["../escape", "/absolute", "a/b", "a\\b", "Upper_Case", "..", "", "a\nprivileged: true"])
def test_new_rejects_unsafe_slugs_without_writing(tmp_path, monkeypatch, slug):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)

    assert cli.main(["new", slug]) == 1
    assert list(tmp_path.iterdir()) == []


def test_new_creates_definition_and_preserves_existing_file(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)

    assert cli.main(["new", "my-app", "--type", "compose"]) == 0
    path = tmp_path / "apps" / "my-app.yaml"
    content = path.read_text(encoding="utf-8")
    definition = yaml.safe_load(content)
    assert definition["slug"] == "my-app"
    assert definition["category"] == "Other"
    assert definition["compose"] == "stacks/my-app/docker-compose.yml"
    assert cli.main(["new", "my-app"]) == 1
    assert path.read_text(encoding="utf-8") == content


def test_build_rejects_script_repository_url_before_writing(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)

    assert cli.main(["build", "--repo-url", "javascript:alert(1)"]) == 1
    assert list(tmp_path.iterdir()) == []


def test_default_build_uses_shared_repository_configuration(build_repo):
    assert cli.main(["build"]) == 0
    feed = json.loads((build_repo / "templates.json").read_text())
    assert feed["templates"][0]["repository"]["url"] == "https://github.com/example/fork"
    assert "example/fork@main/templates.json" in (build_repo / "docs/index.html").read_text(encoding="utf-8")
    assert not (build_repo / "docs/static/obsolete.js").exists()
    assert not list(build_repo.glob(".gallery-build-*"))


def test_repository_override_updates_feed_site_and_identity(build_repo):
    assert cli.main(["build", "--repo-url", "https://github.com/example/new-fork"]) == 0
    assert json.loads((build_repo / "repository.json").read_text())["url"] == "https://github.com/example/new-fork"
    assert json.loads((build_repo / "templates.json").read_text())["templates"][0]["repository"]["url"].endswith("new-fork")


def test_placeholder_repository_does_not_replace_outputs(build_repo):
    assert cli.main(["build", "--repo-url", "https://github.com/OWNER/REPO"]) == 1
    assert (build_repo / "templates.json").read_text() == "old feed"


def test_render_failure_does_not_replace_any_output(build_repo, monkeypatch):
    from gallery import build_site
    def fail(*args, **kwargs):
        raise RuntimeError("render failed")
    monkeypatch.setattr(build_site, "build_site", fail)
    assert cli.main(["build"]) == 1
    assert (build_repo / "templates.json").read_text() == "old feed"
    assert (build_repo / "docs/index.html").read_text() == "old site"
    assert not list(build_repo.glob(".gallery-build-*"))


@pytest.mark.parametrize("fail_at", [2, 3, 4, 5, 6])
def test_publication_failure_restores_whole_build(build_repo, monkeypatch, fail_at):
    real_replace = publish.os.replace
    calls = 0
    def fail_once(source, target):
        nonlocal calls
        calls += 1
        if calls == fail_at:
            raise OSError("injected rename failure")
        return real_replace(source, target)
    monkeypatch.setattr(publish.os, "replace", fail_once)
    assert cli.main(["build", "--repo-url", "https://github.com/example/new-fork"]) == 1
    assert (build_repo / "templates.json").read_text() == "old feed"
    assert (build_repo / "docs/index.html").read_text() == "old site"
    assert (build_repo / "docs/static/obsolete.js").read_text() == "old asset"
    assert (build_repo / "docs/CNAME").read_text() == "old.example\n"
    assert json.loads((build_repo / "repository.json").read_text())["url"] == "https://github.com/example/fork"
    assert not list(build_repo.glob(".gallery-build-*"))


def test_failed_rollback_preserves_backups(build_repo, monkeypatch, capsys):
    real_replace = publish.os.replace
    calls = 0
    def fail_twice(source, target):
        nonlocal calls
        calls += 1
        if calls in (4, 6):
            raise OSError("injected failure")
        return real_replace(source, target)
    monkeypatch.setattr(publish.os, "replace", fail_twice)
    assert cli.main(["build"]) == 1
    stages = list(build_repo.glob(".gallery-build-*"))
    assert len(stages) == 1
    assert (stages[0] / "backup/templates.json").read_text() == "old feed"
    assert str(stages[0]) in capsys.readouterr().err


def test_invalid_generated_feed_is_not_published(build_repo, monkeypatch):
    monkeypatch.setattr(cli, "build_templates", lambda *args, **kwargs: {"version": "invalid", "templates": []})
    assert cli.main(["build"]) == 1
    assert (build_repo / "templates.json").read_text() == "old feed"
    assert (build_repo / "docs/index.html").read_text() == "old site"


def test_malformed_repository_configuration_is_reported(build_repo, capsys):
    (build_repo / "repository.json").write_text('{"wrong_key": "value"}')
    assert cli.main(["build"]) == 1
    assert "repository.json" in capsys.readouterr().err
    assert (build_repo / "templates.json").read_text() == "old feed"


def test_build_publishes_hosting_metadata_from_canonical_sources(build_repo):
    (build_repo / "site_src/CNAME").write_text("new.example\n")
    (build_repo / "site_src/.nojekyll").write_text("")
    assert cli.main(["build"]) == 0
    assert (build_repo / "docs/CNAME").read_text() == "new.example\n"
    assert (build_repo / "docs/.nojekyll").is_file()
    (build_repo / "site_src/CNAME").unlink()
    assert cli.main(["build"]) == 0
    assert not (build_repo / "docs/CNAME").exists()
