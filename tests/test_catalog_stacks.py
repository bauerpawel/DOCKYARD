"""Validate local app stacks with the real Compose parser, without starting containers."""

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
STANDALONE = ROOT / ".venv/docker-compose.exe"
if STANDALONE.exists():
    COMPOSE = [str(STANDALONE)]
elif shutil.which("docker-compose"):
    COMPOSE = [shutil.which("docker-compose")]
elif shutil.which("docker"):
    COMPOSE = [shutil.which("docker"), "compose"]
else:
    COMPOSE = None

pytestmark = pytest.mark.skipif(COMPOSE is None, reason="Docker Compose is not installed")

VALUES = {
    "WEBUI_SECRET_KEY": "a" * 64,
    "APP_URL": "https://login.example.com",
    "ENCRYPTION_KEY": "b" * 43 + "=",
    "NEXTAUTH_URL": "https://bookmarks.example.com",
    "NEXTAUTH_SECRET": "c" * 64,
    "MEILI_MASTER_KEY": "d" * 64,
    "PANGOLIN_BASE_DOMAIN": "example.com",
    "PANGOLIN_DASHBOARD_DOMAIN": "pangolin.example.com",
    "PANGOLIN_SECRET": "e" * 64,
    "LETSENCRYPT_EMAIL": "admin@example.com",
}
REQUIRED = {
    "open-webui": ["WEBUI_SECRET_KEY"],
    "pocket-id": ["APP_URL", "ENCRYPTION_KEY"],
    "karakeep": ["NEXTAUTH_URL", "NEXTAUTH_SECRET", "MEILI_MASTER_KEY"],
    "pangolin": ["PANGOLIN_BASE_DOMAIN", "PANGOLIN_DASHBOARD_DOMAIN", "PANGOLIN_SECRET", "LETSENCRYPT_EMAIL"],
}


def compose_config(tmp_path, slug, missing=None):
    empty_env = tmp_path / "empty.env"
    empty_env.write_text("", encoding="utf-8")
    stack = ROOT / "stacks" / slug / "docker-compose.yml"
    # Isolate these tests from local credentials and port overrides.
    env = {key: value for key, value in os.environ.items()
           if key not in VALUES and not key.startswith(("OLLAMA_", "OPEN_WEBUI_", "POCKET_ID_", "KARAKEEP_"))
           and key not in {"TRUST_PROXY", "OPENAI_API_KEY", "OPENAI_BASE_URL", "INFERENCE_TEXT_MODEL",
                           "INFERENCE_IMAGE_MODEL", "COMPOSE_FILE", "COMPOSE_ENV_FILES"}}
    env.update(VALUES)
    if missing:
        env.pop(missing)
    return subprocess.run(
        COMPOSE + ["--project-directory", str(tmp_path), "--env-file", str(empty_env),
                   "-f", str(stack), "config", "--format", "json"],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=30,
    )


@pytest.mark.parametrize("slug", ["open-webui", "ollama", "pocket-id", "karakeep", "pangolin"])
def test_new_stack_resolves_without_external_config_files(tmp_path, slug):
    result = compose_config(tmp_path, slug)
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    assert config["services"]
    for service in config["services"].values():
        assert "build" not in service
        assert all(volume["type"] == "volume" for volume in service.get("volumes", []))
    for source in config.get("configs", {}).values():
        assert "file" not in source
        assert isinstance(yaml.safe_load(source["content"]), dict)
        assert "${" not in source["content"]


@pytest.mark.parametrize("slug,variable", [(slug, variable) for slug, variables in REQUIRED.items() for variable in variables])
def test_new_stack_rejects_each_missing_required_value(tmp_path, slug, variable):
    result = compose_config(tmp_path, slug, missing=variable)
    assert result.returncode != 0
    assert variable in result.stderr


def test_ollama_is_private_and_webui_uses_its_internal_service(tmp_path):
    standalone = compose_config(tmp_path, "ollama")
    assert standalone.returncode == 0, standalone.stderr
    ollama = json.loads(standalone.stdout)["services"]["ollama"]
    assert ollama["ports"][0]["host_ip"] == "127.0.0.1"
    combined = compose_config(tmp_path, "open-webui")
    assert combined.returncode == 0, combined.stderr
    services = json.loads(combined.stdout)["services"]
    assert not services["ollama"].get("ports")
    assert services["open-webui"]["environment"]["OLLAMA_BASE_URL"] == "http://ollama:11434"


def test_pangolin_embedded_configs_share_domains_and_certificate_settings(tmp_path):
    result = compose_config(tmp_path, "pangolin")
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    files = {name: yaml.safe_load(source["content"]) for name, source in config["configs"].items()}
    app = files["pangolin-config"]
    assert app["server"]["secret"] == VALUES["PANGOLIN_SECRET"]
    assert app["app"]["dashboard_url"] == "https://pangolin.example.com"
    assert app["gerbil"]["base_endpoint"] == VALUES["PANGOLIN_DASHBOARD_DOMAIN"]
    assert app["domains"]["domain1"]["base_domain"] == VALUES["PANGOLIN_BASE_DOMAIN"]
    traefik = files["traefik-config"]
    assert traefik["certificatesResolvers"]["letsencrypt"]["acme"]["email"] == VALUES["LETSENCRYPT_EMAIL"]
    routers = files["traefik-dynamic"]["http"]["routers"]
    assert all("Host(`pangolin.example.com`)" in router["rule"] for router in routers.values())
    assert config["services"]["traefik"]["network_mode"] == "service:gerbil"
    assert {port["target"] for port in config["services"]["gerbil"]["ports"]} == {80, 443, 51820, 21820}
