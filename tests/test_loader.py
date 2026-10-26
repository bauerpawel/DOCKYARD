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


def test_note_and_quoted_no_restart_policy_load_without_changing_their_meaning(tmp_path):
    content = VALID_CONTAINER + 'note: "<p>Keep the existing key.</p>"\nrestart_policy: "no"\n'
    write_app(tmp_path / "apps", "test-app.yaml", content)

    app = load_apps(tmp_path)[0]

    assert app.note == "<p>Keep the existing key.</p>"
    assert app.restart_policy == "no"


@pytest.mark.parametrize("field,value", [("note", "42"), ("restart_policy", "sometimes"),
                                         ("restart_policy", "false"), ("restart_policy", "no")])
def test_invalid_note_or_restart_policy_is_rejected(tmp_path, field, value):
    write_app(tmp_path / "apps", "test-app.yaml", VALID_CONTAINER + f"{field}: {value}\n")

    with pytest.raises(AppValidationError, match=field):
        load_apps(tmp_path)


def test_compose_restart_policy_is_rejected_instead_of_silently_ignored(tmp_path):
    content = VALID_CONTAINER.replace("type: container", "type: compose")
    content += 'repository: {url: https://github.com/example/templates, stackfile: app.yml}\n'
    content += 'restart_policy: unless-stopped\n'
    write_app(tmp_path / "apps", "test-app.yaml", content)

    with pytest.raises(AppValidationError, match="only supported for container templates"):
        load_apps(tmp_path)


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


@pytest.mark.parametrize("content", ["- name: App\n", "not a mapping\n"])
def test_rejects_non_mapping_definition(tmp_path, content):
    write_app(tmp_path / "apps", "bad.yaml", content)

    with pytest.raises(AppValidationError, match="must be a mapping"):
        load_apps(tmp_path)


@pytest.mark.parametrize("field", ["website", "logo"])
@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,hello", "file:///etc/passwd", "//example.com", "https://user:password@example.com", "https://example.com:bad"])
def test_rejects_unsafe_web_urls(tmp_path, field, url):
    original = "https://example.com/logo.png" if field == "logo" else "https://example.com"
    content = VALID_CONTAINER.replace(f"{field}: {original}", f"{field}: {url}")
    write_app(tmp_path / "apps", "bad.yaml", content)

    with pytest.raises(AppValidationError, match=f"'{field}' must be an absolute HTTP"):
        load_apps(tmp_path)


@pytest.mark.parametrize("path", ["../outside.yml", "/outside.yml", "C:/outside.yml", "stacks/../../outside.yml"])
def test_compose_rejects_paths_outside_repository(tmp_path, path):
    content = VALID_CONTAINER.replace("type: container", "type: compose") + f"compose: {path}\n"
    write_app(tmp_path / "apps", "bad.yaml", content)

    with pytest.raises(AppValidationError, match="relative path within the repository"):
        load_apps(tmp_path)


def test_compose_rejects_symlink_outside_repository(tmp_path):
    repo = tmp_path / "repo"
    target = tmp_path / "outside.yml"
    target.write_text("services: {}\n", encoding="utf-8")
    stack = repo / "stacks" / "app.yml"
    stack.parent.mkdir(parents=True)
    try:
        stack.symlink_to(target)
    except OSError:
        pytest.skip("symlink creation is not available")
    content = VALID_CONTAINER.replace("type: container", "type: compose") + "compose: stacks/app.yml\n"
    write_app(repo / "apps", "bad.yaml", content)

    with pytest.raises(AppValidationError, match="stay within the repository"):
        load_apps(repo)


@pytest.mark.parametrize("repository", ["not-a-mapping", {"url": "javascript:alert(1)", "stackfile": "app.yml"}, {"url": "https://github.com/a/b", "stackfile": "../app.yml"}])
def test_rejects_unsafe_external_repository(tmp_path, repository):
    import yaml

    data = yaml.safe_load(VALID_CONTAINER)
    data.update(type="compose", repository=repository)
    write_app(tmp_path / "apps", "bad.yaml", yaml.safe_dump(data))

    with pytest.raises(AppValidationError, match="repository"):
        load_apps(tmp_path)


@pytest.mark.parametrize("override,field", [
    ({"env": ["bad"]}, "env[0]"),
    ({"env": [{}]}, "env[0]"),
    ({"env": [{"name": "X", "default": 42}]}, "default"),
    ({"env": [{"name": "X", "select": [{"text": "X"}]}]}, "select"),
    ({"volumes": [{}]}, "volumes[0]"),
    ({"volumes": [{"container": "/data", "readonly": "false"}]}, "readonly"),
    ({"image": 42}, "image"),
    ({"privileged": "false"}, "privileged"),
    ({"ports": "8080/tcp"}, "ports"),
    ({"ports": [8080]}, "ports[0]"),
    ({"description": ["bad"]}, "description"),
])
def test_invalid_nested_types_report_file_and_field(tmp_path, override, field):
    import yaml
    data = yaml.safe_load(VALID_CONTAINER) | override
    write_app(tmp_path / "apps", "bad.yaml", yaml.safe_dump(data))
    with pytest.raises(AppValidationError) as caught:
        load_apps(tmp_path)
    assert "bad.yaml" in str(caught.value)
    assert field in str(caught.value)


@pytest.mark.parametrize("create_directory", [False, True])
def test_missing_or_empty_catalog_is_rejected(tmp_path, create_directory):
    if create_directory:
        (tmp_path / "apps").mkdir()
    with pytest.raises(AppValidationError, match="app directory|no app definitions"):
        load_apps(tmp_path)


def test_yaml_syntax_errors_are_aggregated_with_model_errors(tmp_path):
    write_app(tmp_path / "apps", "syntax.yaml", "name: [broken\n")
    write_app(tmp_path / "apps", "invalid.yaml", VALID_CONTAINER.replace("image: library/test:latest", "image: 42"))
    with pytest.raises(AppValidationError) as caught:
        load_apps(tmp_path)
    message = str(caught.value)
    assert "syntax.yaml:" in message and "invalid YAML" in message
    assert "invalid.yaml" in message and "image" in message
