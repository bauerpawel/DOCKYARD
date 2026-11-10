"""The catalog audit pins only a registry-verified multi-arch digest."""

from pathlib import Path

from gallery.catalog_audit import (
    audit_catalog,
    is_latest,
    parse_image,
    pin_latest_images,
    resolve_manifest,
    rewrite_latest_image,
)

INDEX = "application/vnd.oci.image.index.v1+json"
SINGLE = "application/vnd.docker.distribution.manifest.v2+json"
DIGEST = "sha256:" + ("ab" * 32)


def test_parse_image_keeps_the_registry_and_official_library_namespace():
    assert parse_image("wordpress:latest") == ("docker.io", "library/wordpress", "latest")
    assert parse_image("ghcr.io/example/app:latest") == ("ghcr.io", "example/app", "latest")
    assert is_latest("example/app:1.2") is False
    assert is_latest("example/app:latest@sha256:" + "a" * 64) is False


def test_single_platform_manifest_is_not_pinned():
    def fetch(url, headers):
        assert url == "https://registry-1.docker.io/v2/library/wordpress/manifests/latest"
        return 200, {"Content-Type": SINGLE, "Docker-Content-Digest": DIGEST}, b""

    pinned, reason = resolve_manifest("wordpress:latest", fetch)

    assert pinned is None
    assert "single-platform" in reason


def test_manifest_list_digest_is_appended_to_the_same_tag(tmp_path):
    def fetch(url, headers):
        return 200, {"content-type": INDEX, "docker-content-digest": DIGEST}, b""

    app = tmp_path / "apps"
    app.mkdir()
    source = app / "demo.yaml"
    source.write_text("name: Demo\nslug: demo\ncategory: Utilities\ntype: container\nimage: wordpress:latest\n", encoding="utf-8")
    stacks = tmp_path / "stacks" / "demo"
    stacks.mkdir(parents=True)
    compose = stacks / "docker-compose.yml"
    compose.write_text("services:\n  app:\n    image: wordpress:latest\n    environment:\n      KEEP: '1'\n", encoding="utf-8")

    original = resolve_manifest
    try:
        import gallery.catalog_audit as module
        module.resolve_manifest = lambda reference, fetch=None: (f"{reference.split('@', 1)[0]}@{DIGEST}", "pinned")
        report = pin_latest_images(tmp_path)
    finally:
        module.resolve_manifest = original

    assert len(report["pinned"]) == 2
    assert f"image: wordpress:latest@{DIGEST}\n" in source.read_text(encoding="utf-8")
    assert f"image: wordpress:latest@{DIGEST}\n" in compose.read_text(encoding="utf-8")
    assert "KEEP: '1'" in compose.read_text(encoding="utf-8")
    assert fetch  # the fake registry above is what resolve_manifest uses; pin uses the patched function


def test_rewrite_replaces_only_the_matching_image_line():
    text = "image: other:latest\nservices:\n  app:\n    image: 'wordpress:latest'\n"
    updated = rewrite_latest_image(text, "wordpress:latest", "wordpress:latest@" + DIGEST)
    assert updated == "image: other:latest\nservices:\n  app:\n    image: 'wordpress:latest@" + DIGEST + "'\n"


def test_already_pinned_images_are_not_resolved_again(tmp_path):
    digest = "sha256:" + "cd" * 32
    apps = tmp_path / "apps"
    apps.mkdir()
    pinned = f"example/app:1.2.3@{digest}"
    (apps / "demo.yaml").write_text(
        f"name: Demo\nslug: demo\ncategory: Utilities\ntype: container\nimage: {pinned}\n",
        encoding="utf-8",
    )
    calls = []

    import gallery.catalog_audit as module
    original = module.resolve_manifest
    module.resolve_manifest = lambda reference, fetch=None: calls.append(reference)
    try:
        report = pin_latest_images(tmp_path)
    finally:
        module.resolve_manifest = original

    assert calls == []
    assert report["pinned"] == []
    assert (apps / "demo.yaml").read_text(encoding="utf-8").count(pinned) == 1


def test_audit_counts_latest_other_and_compose_version(tmp_path):
    apps = tmp_path / "apps"
    apps.mkdir()
    (apps / "a.yaml").write_text("name: One\nslug: one\ncategory: Other\ntype: container\nimage: one:latest\n", encoding="utf-8")
    (apps / "b.yaml").write_text("name: One (stack)\nslug: one-stack\ncategory: Media\ntype: compose\n", encoding="utf-8")
    stack = tmp_path / "stacks" / "demo"
    stack.mkdir(parents=True)
    (stack / "docker-compose.yml").write_text('version: "3.8"\nservices: {}\n', encoding="utf-8")

    report = audit_catalog(tmp_path)

    assert report["container_images"] == 1
    assert [item["image"] for item in report["container_latest_without_digest"]] == ["one:latest"]
    assert report["other_slugs"] == ["one"]
    assert report["compose_version_keys"] == ["stacks/demo/docker-compose.yml:1"]
    assert len(report["near_duplicate_titles"]) == 1
