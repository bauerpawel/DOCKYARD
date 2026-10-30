"""Exercise catalog additions through the real feed, PHP MCP and Compose CLI."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SLUGS = [
    "postgresql", "sftpgo", "wallos", "convertx", "metabase", "adventurelog",
    "qdrant", "valkey", "netbird", "headscale", "memos", "lubelogger", "warracker",
    "spliit", "grist", "firefly-iii", "wanderer", "mailpit", "paperless-gpt", "komodo",
    "donetick", "silverbullet", "kitchenowl", "snipe-it", "opengist", "zipline",
    "bugsink", "openobserve", "docling-serve", "keycloak",
]
PHP = shutil.which("php")
STANDALONE = ROOT / ".venv/docker-compose.exe"
COMPOSE = ([str(STANDALONE)] if STANDALONE.is_file() else
           [shutil.which("docker-compose")] if shutil.which("docker-compose") else
           [shutil.which("docker"), "compose"] if shutil.which("docker") else None)
EXAMPLES = {
    "NETBIRD_DOMAIN": "netbird.example.com",
    "LETSENCRYPT_EMAIL": "admin@example.com",
    "HEADSCALE_SERVER_URL": "https://headscale.example.com",
    "SITE_URL": "https://travel.example.com",
    "DJANGO_ADMIN_EMAIL": "admin@example.com",
    "APP_BASE_URL": "https://warranties.example.com",
    "APP_URL": "https://finance.example.com",
    "ORIGIN": "https://trails.example.com",
    "PAPERLESS_BASE_URL": "http://paperless.example.com:8000",
    "OLLAMA_HOST": "http://ollama.example.com:11434",
    "LLM_MODEL": "qwen3:8b",
    "KOMODO_HOST": "https://komodo.example.com",
    "BASE_URL": "https://errors.example.com",
    "BUGSINK_ADMIN_EMAIL": "admin@example.com",
    "ZO_ROOT_USER_EMAIL": "admin@example.com",
    "KC_HOSTNAME": "https://login.example.com",
    "KC_PROXY_TRUSTED_ADDRESSES": "172.20.0.1/32",
}


@pytest.fixture(scope="module")
def additions():
    return {slug: yaml.safe_load((ROOT / "apps" / f"{slug}.yaml").read_text(encoding="utf-8"))
            for slug in SLUGS}


def env_for(app):
    values = {}
    for spec in app.get("env", []):
        name = spec["name"]
        values[name] = spec.get("default", EXAMPLES.get(name, "a" * 64))
    for name in {"APP_KEY", "STATIC_CRON_TOKEN", "POCKETBASE_ENCRYPTION_KEY", "OG_SECRET_KEY"} & values.keys():
        values[name] = "b" * 32
    for name in {"NETBIRD_DATASTORE_ENCRYPTION_KEY", "NETBIRD_SESSION_COOKIE_ENCRYPTION_KEY"} & values.keys():
        values[name] = "YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE="
    if "SNIPEIT_APP_KEY" in values:
        values["SNIPEIT_APP_KEY"] = "base64:YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE="
    return values


@pytest.fixture(scope="module")
def mcp_results(tmp_path_factory, additions):
    if PHP is None:
        pytest.skip("PHP is not installed")
    directory = tmp_path_factory.mktemp("catalog-mcp")
    inputs = directory / "inputs.json"
    inputs.write_text(json.dumps({slug: env_for(app) for slug, app in additions.items()}), encoding="utf-8")
    runner = directory / "probe.php"
    runner.write_text('''<?php
require $argv[1];
$results = [];
foreach (json_decode(file_get_contents($argv[2]), true) as $slug => $values) {
    $app = dockyard_get_app(['slug' => $slug]);
    $secrets = [];
    foreach ($app['env'] as $spec) {
        if ($spec['secret']) {
            $secrets[] = $spec['name'];
            unset($values[$spec['name']]);
        }
    }
    $args = ['slug' => $slug, 'confirm' => true, 'env' => $values, 'local_secrets' => $secrets];
    $results[$slug] = [
        'app' => $app,
        'listed' => dockyard_list_apps(['query' => $slug, 'limit' => 50]),
        'plan' => dockyard_prepare_deploy($args),
        'approved' => dockyard_prepare_deploy($args + ['allow_privileged' => true]),
    ];
}
echo json_encode($results, JSON_THROW_ON_ERROR);
''', encoding="utf-8")
    environment = os.environ.copy()
    environment.pop("DOCKYARD_TEMPLATES_URL", None)
    environment["DOCKYARD_TEMPLATES"] = str(ROOT / "templates.json")
    result = subprocess.run([PHP, str(runner), str(ROOT / "mcp/index.php"), str(inputs)],
                            capture_output=True, text=True, encoding="utf-8", env=environment, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("slug", SLUGS)
def test_new_apps_keep_descriptions_setup_notes_and_secrets_in_mcp(additions, mcp_results, slug):
    source = additions[slug]
    result = mcp_results[slug]
    app = result["app"]
    assert app["description"] == source["description"]
    assert app["note"] == source["note"]
    assert len(app["note"]) < 4000
    assert app["kind"] == source["type"]
    assert all(spec["description"] for spec in app["env"])
    for spec in app["env"]:
        if re.search(r"PASSWORD|SECRET|TOKEN|(?:^|_)KEY$", spec["name"]):
            assert spec["secret"] is True, spec
            assert spec["default"] == "", spec
    assert slug in {item["slug"] for item in result["listed"]["apps"]}
    plan = result["approved"]
    assert plan["description"] == app["description"]
    assert plan["note"] == app["note"]
    assert plan["ready"] is True, plan["blockers"]
    if slug != "komodo":
        assert result["plan"]["ready"] is True, result["plan"]["blockers"]
    if source["type"] == "compose":
        assert plan["published_ports"], slug
        assert not any("${" in port for port in plan["published_ports"])
    if slug == "valkey":
        assert plan["suggested_url"] is None
    if slug == "paperless-gpt":
        assert plan["suggested_url"] == "http://localhost:8087"
    assert not any("zmienne, których plan nie ustawia" in warning for warning in plan["warnings"])
    assert plan["docker"]["compose"]
    assert plan["portainer"]["body"]["stackFileContent"]
    assert not any(spec["default"] for spec in app["env"] if spec["secret"])


def test_komodo_host_access_requires_separate_approval(mcp_results):
    result = mcp_results["komodo"]
    assert result["plan"]["ready"] is False
    assert result["approved"]["ready"] is True
    assert any("docker.sock" in warning for warning in result["plan"]["warnings"])
    assert "host" in result["app"]["description"]


def test_sql_stacks_reuse_the_catalog_postgresql_image_and_keep_databases_private(additions):
    image = additions["postgresql"]["image"]
    for slug in ["metabase", "warracker", "spliit", "firefly-iii", "zipline", "bugsink", "keycloak"]:
        stack = yaml.safe_load((ROOT / additions[slug]["compose"]).read_text(encoding="utf-8"))
        database = stack["services"]["db"]
        assert database["image"] == image
        assert not database.get("ports")
        assert "database:/var/lib/postgresql" in database["volumes"]


@pytest.mark.skipif(COMPOSE is None, reason="Docker Compose config CLI is not installed")
@pytest.mark.parametrize("slug", SLUGS)
def test_mcp_deployments_resolve_with_the_real_compose_parser(tmp_path, additions, mcp_results, slug):
    plan = mcp_results[slug]["approved"]
    compose = tmp_path / "docker-compose.yml"
    compose.write_text(plan["docker"]["compose"], encoding="utf-8")
    # Use explicit test values instead of CHANGEME to validate length-sensitive configs.
    environment = {name: value for name, value in os.environ.items()
                   if name not in {spec["name"] for app in additions.values() for spec in app.get("env", [])}}
    environment.update(env_for(additions[slug]))
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    result = subprocess.run(COMPOSE + ["--project-directory", str(tmp_path), "--env-file", str(empty),
                                      "-f", str(compose), "config", "--format", "json"],
                            capture_output=True, text=True, encoding="utf-8", env=environment, timeout=30)
    assert result.returncode == 0, result.stderr
    parsed = json.loads(result.stdout)
    for service in parsed["services"].values():
        assert "build" not in service
        assert not service.get("env_file")
        assert "@sha256:" in service["image"]
    for name, config in parsed.get("configs", {}).items():
        assert "file" not in config
        assert "${" not in config["content"]
        if slug == "headscale" or (slug == "netbird" and name == "server-config"):
            assert isinstance(yaml.safe_load(config["content"]), dict)
    if slug in {"metabase", "warracker", "spliit", "firefly-iii", "zipline", "bugsink", "keycloak", "snipe-it"}:
        services = parsed["services"]
        password = services["db"]["environment"].get("POSTGRES_PASSWORD", services["db"]["environment"].get("MARIADB_PASSWORD"))
        app = services.get(slug, services.get("app"))
        if slug == "metabase":
            assert app["environment"]["MB_DB_PASS"] == password
        elif slug == "spliit":
            assert f":{password}@db:5432/" in app["environment"]["POSTGRES_PRISMA_URL"]
        elif slug == "bugsink":
            assert f":{password}@db:5432/" in app["environment"]["DATABASE_URL"]
            assert app["environment"]["CREATE_SUPERUSER"] == "admin@example.com:" + env_for(additions[slug])["BUGSINK_ADMIN_PASSWORD"]
        elif slug == "zipline":
            assert app["environment"]["DATABASE_PASSWORD"] == password
            assert app["environment"]["DATABASE_NAME"] == services["db"]["environment"]["POSTGRES_DB"]
        elif slug == "keycloak":
            assert app["environment"]["KCRAW_DB_PASSWORD"] == password
            assert app["command"] == ["start"]
            assert app["ports"][0]["host_ip"] == "127.0.0.1"
            assert app["environment"]["KC_PROXY_TRUSTED_ADDRESSES"] == EXAMPLES["KC_PROXY_TRUSTED_ADDRESSES"]
        else:
            assert app["environment"]["DB_PASSWORD"] == password
        if slug == "snipe-it":
            assert app["environment"]["DB_USERNAME"] == services["db"]["environment"]["MARIADB_USER"]
            assert app["environment"]["DB_DATABASE"] == services["db"]["environment"]["MARIADB_DATABASE"]
            assert "MYSQL_ROOT_PASSWORD" not in app["environment"]
            assert "MARIADB_ROOT_PASSWORD" not in app["environment"]
            assert not services["db"].get("ports")
    if slug == "docling-serve":
        app = next(iter(parsed["services"].values()))
        assert app["environment"]["DOCLING_SERVE_API_KEY"]
        assert app["environment"]["DOCLING_DEVICE"] == "cpu"
        assert app["environment"]["DOCLING_SERVE_ENABLE_UI"] == "false"
        assert not app.get("devices")


@pytest.mark.skipif(COMPOSE is None, reason="Docker Compose config CLI is not installed")
def test_required_compose_values_cannot_be_silently_omitted(tmp_path, additions):
    for slug, app in additions.items():
        if app["type"] != "compose":
            continue
        text = (ROOT / app["compose"]).read_text(encoding="utf-8")
        required = set(re.findall(r"\$\{([A-Z_0-9]+):\?", text))
        assert required, slug
        declared = {spec["name"] for spec in app["env"]}
        assert required <= declared, (slug, required - declared)
        for missing in required:
            values = env_for(app)
            values.pop(missing)
            empty = tmp_path / "empty.env"
            empty.write_text("", encoding="utf-8")
            environment = {key: value for key, value in os.environ.items() if key not in declared}
            environment.update(values)
            result = subprocess.run(COMPOSE + ["--env-file", str(empty), "-f", str(ROOT / app["compose"]), "config"],
                                    capture_output=True, text=True, encoding="utf-8", env=environment, timeout=30)
            assert result.returncode != 0, (slug, missing)
            assert missing in result.stderr
