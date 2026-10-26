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
    "_APP_DOMAIN": "appwrite.example.com",
    "_APP_DB_PASS": "1" * 64,
    "_APP_OPENSSL_KEY_V1": "2" * 64,
    "_APP_NOTIFICATIONS_TRACKING_SECRET": "3" * 64,
    "_APP_EXECUTOR_SECRET": "4" * 64,
    "_APP_JOBS_SECRET": "5" * 64,
    "_APP_GEO_SECRET": "6" * 64,
    "_APP_USAGE_PASS": "7" * 64,
    "PLANE_DOMAIN": "plane.example.com",
    "WEB_URL": "https://plane.example.com",
    "PGPASSWORD": "8" * 64,
    "RABBITMQ_PASSWORD": "9" * 64,
    "PLANE_SECRET_KEY": "a1" * 32,
    "LIVE_SERVER_SECRET_KEY": "b2" * 32,
    "AWS_ACCESS_KEY_ID": "dockyard-test-user",
    "AWS_SECRET_ACCESS_KEY": "c3" * 32,
    "PRINTER_DEVICE": "/dev/ttyACM0",
    "KLIPPER_CONFIG_DIR": "/srv/dockyard/klipper",
}
REQUIRED = {
    "open-webui": ["WEBUI_SECRET_KEY"],
    "pocket-id": ["APP_URL", "ENCRYPTION_KEY"],
    "karakeep": ["NEXTAUTH_URL", "NEXTAUTH_SECRET", "MEILI_MASTER_KEY"],
    "pangolin": ["PANGOLIN_BASE_DOMAIN", "PANGOLIN_DASHBOARD_DOMAIN", "PANGOLIN_SECRET", "LETSENCRYPT_EMAIL"],
    "appwrite": ["_APP_DOMAIN", "_APP_DB_PASS", "_APP_OPENSSL_KEY_V1", "_APP_NOTIFICATIONS_TRACKING_SECRET",
                 "_APP_EXECUTOR_SECRET", "_APP_JOBS_SECRET", "_APP_GEO_SECRET", "_APP_USAGE_PASS"],
    "plane": ["PLANE_DOMAIN", "WEB_URL", "PGPASSWORD", "RABBITMQ_PASSWORD", "PLANE_SECRET_KEY",
              "LIVE_SERVER_SECRET_KEY", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"],
    "klipper": ["PRINTER_DEVICE", "KLIPPER_CONFIG_DIR"],
}


def compose_config(tmp_path, slug, missing=None):
    empty_env = tmp_path / "empty.env"
    empty_env.write_text("", encoding="utf-8")
    stack = ROOT / "stacks" / slug / "docker-compose.yml"
    # Isolate these tests from local credentials and port overrides.
    env = {key: value for key, value in os.environ.items()
           if key not in VALUES and not key.startswith(("OLLAMA_", "OPEN_WEBUI_", "POCKET_ID_", "KARAKEEP_", "_APP_", "AWS_", "PLANE_", "RABBITMQ_"))
           and key not in {"TRUST_PROXY", "OPENAI_API_KEY", "OPENAI_BASE_URL", "INFERENCE_TEXT_MODEL",
                           "INFERENCE_IMAGE_MODEL", "COMPOSE_FILE", "COMPOSE_ENV_FILES", "PGUSER", "PGDATABASE"}}
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


@pytest.mark.parametrize("slug", ["appwrite", "plane"])
def test_repaired_stacks_resolve_without_a_source_tree_or_env_files(tmp_path, slug):
    result = compose_config(tmp_path, slug)
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    for service in config["services"].values():
        assert "build" not in service
        assert not service.get("env_file")
        assert "@sha256:" in service["image"]
        for volume in service.get("volumes", []):
            if volume["type"] == "bind":
                assert slug == "appwrite"
                assert volume["source"] in {"/var/run/docker.sock", "/tmp"}
    assert all("file" not in source for source in config.get("configs", {}).values())


def test_appwrite_credentials_match_database_workers_and_service_backends(tmp_path):
    result = compose_config(tmp_path, "appwrite")
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    database = services["postgresql"]["environment"]
    api = services["appwrite"]["environment"]
    assert database["POSTGRES_PASSWORD"] == VALUES["_APP_DB_PASS"]
    for service in services.values():
        if service["image"].startswith("appwrite/appwrite:"):
            env = service["environment"]
            assert env["_APP_DB_PASS"] == database["POSTGRES_PASSWORD"]
            assert env["_APP_DB_USER"] == database["POSTGRES_USER"]
            assert env["_APP_DB_SCHEMA"] == database["POSTGRES_DB"]
            assert env["_APP_OPENSSL_KEY_V1"] == VALUES["_APP_OPENSSL_KEY_V1"]
    assert api["_APP_EXECUTOR_SECRET"] == services["openruntimes-executor"]["environment"]["OPR_EXECUTOR_SECRET"]
    assert api["_APP_GEO_SECRET"] == services["appwrite-geo"]["environment"]["GEO_SECRET"]
    assert VALUES["_APP_USAGE_PASS"] == services["clickhouse"]["environment"]["CLICKHOUSE_PASSWORD"]
    assert VALUES["_APP_USAGE_PASS"] in api["_APP_CONNECTIONS_DB_USAGE"]
    assert "mariadb" not in services
    assert "mongodb" not in services


def test_plane_rustfs_and_database_configuration_is_consistent(tmp_path):
    result = compose_config(tmp_path, "plane")
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    storage = services["plane-minio"]
    assert storage["image"].startswith("rustfs/rustfs:1.0.4@sha256:")
    assert not storage.get("ports")
    assert storage["environment"]["RUSTFS_CONSOLE_ENABLE"] == "false"
    for name in ["api", "worker", "beat-worker", "migrator"]:
        env = services[name]["environment"]
        assert env["DATABASE_URL"] == f"postgresql://plane:{VALUES['PGPASSWORD']}@plane-db/plane"
        assert env["POSTGRES_PASSWORD"] == services["plane-db"]["environment"]["POSTGRES_PASSWORD"]
        assert env["AMQP_URL"] == f"amqp://plane:{VALUES['RABBITMQ_PASSWORD']}@plane-mq:5672/plane"
        assert env["AWS_ACCESS_KEY_ID"] == storage["environment"]["RUSTFS_ACCESS_KEY"]
        assert env["AWS_SECRET_ACCESS_KEY"] == storage["environment"]["RUSTFS_SECRET_KEY"]
        assert env["AWS_S3_ENDPOINT_URL"] == "http://plane-minio:9000"
        assert env["USE_MINIO"] == "1"
    assert services["api"]["depends_on"]["storage-init"]["condition"] == "service_completed_successfully"
    assert services["api"]["depends_on"]["migrator"]["condition"] == "service_completed_successfully"
    assert services["live"]["environment"]["LIVE_SERVER_SECRET_KEY"] == services["api"]["environment"]["LIVE_SERVER_SECRET_KEY"]


def test_klipper_uses_valid_variable_names_and_passes_the_selected_device(tmp_path):
    result = compose_config(tmp_path, "klipper")
    assert result.returncode == 0, result.stderr
    config = json.loads(result.stdout)
    device = config["services"]["klipper"]["devices"][0]
    assert device["source"] == VALUES["PRINTER_DEVICE"]
    assert device["target"] == VALUES["PRINTER_DEVICE"]
    assert "${" not in result.stdout
