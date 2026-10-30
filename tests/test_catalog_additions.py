"""Exercise catalog additions through the real feed, PHP MCP and Compose CLI."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tomllib
import xml.etree.ElementTree as ET

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
SLUGS = [
    "postgresql", "sftpgo", "wallos", "convertx", "metabase", "adventurelog",
    "qdrant", "valkey", "netbird", "headscale", "memos", "lubelogger", "warracker",
    "spliit", "grist", "firefly-iii", "wanderer", "mailpit", "paperless-gpt", "komodo",
    "donetick", "silverbullet", "kitchenowl", "snipe-it", "opengist", "zipline",
    "bugsink", "openobserve", "docling-serve", "keycloak",
    "kopia", "bichon", "pulse", "tinyauth", "esphome", "litellm", "twenty",
    "formbricks", "documenso", "zammad", "linkwarden", "affine", "openproject",
    "windmill", "mattermost", "jitsi", "yourls", "microbin", "booklore", "sparkyfitness",
    "ente-photos", "plausible", "rallly", "invoiceshelf", "dolibarr", "teable",
    "wishlist", "docspell", "openspeedtest", "synapse",
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
    "ENTE_PHOTOS_URL": "https://photos.example.com",
    "ENTE_ALBUMS_URL": "https://albums.example.com",
    "ENTE_ACCOUNTS_URL": "https://accounts.example.com",
    "ENTE_API_URL": "https://api.photos.example.com",
    "ENTE_S3_ENDPOINT": "https://s3.photos.example.com",
    "NEXT_PUBLIC_BASE_URL": "https://meet.example.com",
    "RALLLY_ADMIN_EMAIL": "admin@example.com",
    "SMTP_HOST": "smtp.example.com",
    "SMTP_USER": "admin@example.com",
    "DOLI_URL_ROOT": "https://erp.example.com",
    "PUBLIC_ORIGIN": "https://tables.example.com",
    "SYNAPSE_SERVER_NAME": "matrix.example.com",
    "SYNAPSE_PUBLIC_BASEURL": "https://matrix.example.com/",
    "TINYAUTH_APPURL": "https://auth.example.com",
    "TINYAUTH_AUTH_USERS": "user:$2a$10$UdLYoJ5lgPsC0RKqYH/jMua7zIn0g9kPqWmhYayJYLaZQ/FTmH2/u",
    "TINYAUTH_AUTH_TRUSTEDPROXIES": "172.20.0.1/32",
    "SERVER_URL": "https://crm.example.com",
    "NEXTAUTH_URL": "https://links.example.com/api/v1/auth",
    "YOURLS_SITE": "https://go.example.com",
    "SPARKY_FITNESS_FRONTEND_URL": "https://fitness.example.com",
    "SPARKY_FITNESS_ADMIN_EMAIL": "admin@example.com",
    "NEXT_PUBLIC_WEBAPP_URL": "https://sign.example.com",
    "MAIL_FROM": "noreply@example.com",
    "AFFINE_URL": "https://notes.example.com",
    "OPENPROJECT_HOST_NAME": "projects.example.com",
    "OPENPROJECT_ADMIN_EMAIL": "admin@example.com",
    "MM_SERVICESETTINGS_SITEURL": "https://chat.example.com",
    "ZAMMAD_HOSTNAME": "support.example.com",
    "PUBLIC_URL": "https://meet.example.com",
    "JVB_ADVERTISE_IPS": "203.0.113.10",
    "FORMBRICKS_URL": "https://surveys.example.com",
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
    if app["slug"] == "invoiceshelf":
        values["APP_KEY"] = "base64:YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE="
    if app["slug"] == "twenty":
        values["ENCRYPTION_KEY"] = "YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE="
    if app["slug"] == "sparkyfitness":
        values["BETTER_AUTH_SECRET"] = "YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE="
    for name in {"ENTE_ENCRYPTION_KEY", "TOTP_VAULT_KEY"} & values.keys():
        values[name] = "YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE="
    if "ENTE_HASH_KEY" in values:
        values["ENTE_HASH_KEY"] = "YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYQ=="
    for name in {"S3_ACCESS_KEY_ID", "ENTE_S3_ACCESS_KEY"} & values.keys():
        values[name] = "c" * 32
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
        if spec["name"] != "TOKEN_TIME" and re.search(r"PASSWORD|SECRET|TOKEN|(?:^|_)KEY$", spec["name"]):
            assert spec["secret"] is True, spec
            assert spec["default"] == "", spec
    assert slug in {item["slug"] for item in result["listed"]["apps"]}
    plan = result["approved"]
    assert plan["description"] == app["description"]
    assert plan["note"] == app["note"]
    assert plan["ready"] is True, plan["blockers"]
    if slug not in {"komodo", "windmill"}:
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


def test_wishlist_expiry_is_a_duration_and_does_not_request_a_local_secret(mcp_results):
    result = mcp_results["wishlist"]
    expiry = next(spec for spec in result["app"]["env"] if spec["name"] == "TOKEN_TIME")
    assert expiry["secret"] is False
    assert expiry["default"] == "72"
    assert "TOKEN_TIME" not in result["plan"]["secrets_to_set"]
    assert result["plan"]["ready"] is True


def test_tinyauth_user_hashes_are_requested_as_local_secrets(mcp_results):
    result = mcp_results["tinyauth"]
    users = next(spec for spec in result["app"]["env"] if spec["name"] == "TINYAUTH_AUTH_USERS")
    assert users["secret"] is True
    assert users["default"] == ""
    assert "TINYAUTH_AUTH_USERS" in result["plan"]["secrets_to_set"]
    assert EXAMPLES["TINYAUTH_AUTH_USERS"] not in json.dumps(result)


def test_windmill_worker_privileges_require_explicit_approval(mcp_results):
    result = mcp_results["windmill"]
    assert result["plan"]["ready"] is False
    assert result["approved"]["ready"] is True
    assert "privileged" in result["app"]["description"]


def test_sql_stacks_reuse_the_catalog_postgresql_image_and_keep_databases_private(additions):
    image = additions["postgresql"]["image"]
    for slug in ["metabase", "warracker", "spliit", "firefly-iii", "zipline", "bugsink", "keycloak",
                 "ente-photos", "plausible", "rallly", "teable", "docspell", "synapse"]:
        stack = yaml.safe_load((ROOT / additions[slug]["compose"]).read_text(encoding="utf-8"))
        database = stack["services"]["db"]
        assert database["image"] == image
        assert not database.get("ports")
        assert "database:/var/lib/postgresql" in database["volumes"]


def test_missing_batch_reuses_postgresql_except_for_required_vector_extension(additions):
    standard = additions["postgresql"]["image"]
    for slug in ["litellm", "twenty", "documenso", "zammad", "linkwarden", "openproject", "windmill", "mattermost", "sparkyfitness"]:
        database = yaml.safe_load((ROOT / additions[slug]["compose"]).read_text(encoding="utf-8"))["services"]["db"]
        assert database["image"] == standard
        assert not database.get("ports")
        assert "database:/var/lib/postgresql" in database["volumes"]
    for slug in ["affine", "formbricks"]:
        database = yaml.safe_load((ROOT / additions[slug]["compose"]).read_text(encoding="utf-8"))["services"]["db"]
        assert database["image"].startswith("pgvector/pgvector:pg18-bookworm@sha256:")
        assert "pgvector" in additions[slug]["description"]
        assert not database.get("ports")


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
        if slug not in {"formbricks", "zammad"}:
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
    services = parsed["services"]
    if slug == "ente-photos":
        config = yaml.safe_load(parsed["configs"]["museum-config"]["content"])
        bucket = config["s3"]["b2-eu-cen"]
        storage = services["storage"]["environment"]
        assert bucket["key"] == storage["MINIO_ROOT_USER"]
        assert bucket["secret"] == storage["MINIO_ROOT_PASSWORD"]
        assert bucket["endpoint"] == EXAMPLES["ENTE_S3_ENDPOINT"]
        assert config["s3"]["are_local_buckets"] is False
        assert services["museum"]["environment"]["ENTE_DB_PASSWORD"] == services["db"]["environment"]["POSTGRES_PASSWORD"]
        assert services["web"]["environment"]["ENTE_API_ORIGIN"] == EXAMPLES["ENTE_API_URL"]
        assert config["apps"]["accounts"] == EXAMPLES["ENTE_ACCOUNTS_URL"]
        assert config["apps"]["public-albums"] == EXAMPLES["ENTE_ALBUMS_URL"]
        assert services["museum"]["depends_on"]["storage-init"]["condition"] == "service_completed_successfully"
        assert services["storage"]["volumes"][0]["type"] == "volume"
    elif slug == "plausible":
        web = services["plausible"]["environment"]
        assert f":{services['db']['environment']['POSTGRES_PASSWORD']}@db:5432/" in web["DATABASE_URL"]
        events = services["events"]["environment"]
        assert f"{events['CLICKHOUSE_USER']}:{events['CLICKHOUSE_PASSWORD']}@events:8123/{events['CLICKHOUSE_DB']}" in web["CLICKHOUSE_DATABASE_URL"]
        for config in parsed["configs"].values():
            assert ET.fromstring(config["content"]).tag == "clickhouse"
        assert not services["events"].get("ports")
    elif slug == "rallly":
        web = services["rallly"]["environment"]
        storage = services["garage"]["environment"]
        assert web["S3_ACCESS_KEY_ID"] == storage["GARAGE_DEFAULT_ACCESS_KEY"]
        assert web["S3_SECRET_ACCESS_KEY"] == storage["GARAGE_DEFAULT_SECRET_KEY"]
        assert web["S3_BUCKET_NAME"] == storage["GARAGE_DEFAULT_BUCKET"]
        assert web["ALLOWED_EMAILS"] == web["INITIAL_ADMIN_EMAIL"] == EXAMPLES["RALLLY_ADMIN_EMAIL"]
        config = tomllib.loads(parsed["configs"]["garage-config"]["content"])
        assert config["s3_api"]["api_bind_addr"].endswith(":3900")
        assert not services["garage"].get("ports")
        assert "license" in additions[slug]["description"]
    elif slug == "dolibarr":
        web = services["dolibarr"]["environment"]
        database = services["db"]["environment"]
        assert web["DOLI_DB_PASSWORD"] == database["MARIADB_PASSWORD"]
        assert web["DOLI_DB_USER"] == database["MARIADB_USER"]
        assert web["DOLI_DB_NAME"] == database["MARIADB_DATABASE"]
        assert "MARIADB_ROOT_PASSWORD" not in web
        assert web["DOLI_INSTANCE_UNIQUE_ID"] == env_for(additions[slug])["DOLIBARR_SECRET_ID"]
        assert not services["db"].get("ports")
    elif slug == "teable":
        web = services["teable"]["environment"]
        assert f":{services['db']['environment']['POSTGRES_PASSWORD']}@db:5432/" in web["PRISMA_DATABASE_URL"]
        assert f":{services['cache']['environment']['REDIS_PASSWORD']}@cache:6379/" in web["BACKEND_CACHE_REDIS_URI"]
        assert not services["cache"].get("ports")
    elif slug == "docspell":
        for name in ["restserver", "joex"]:
            assert services[name]["platform"] == "linux/amd64"
        assert "AMD64" in additions[slug]["description"]
        assert not services["joex"].get("ports")
        assert services["restserver"]["environment"]["DOCSPELL_SERVER_BACKEND_SIGNUP_MODE"] == "invite"
        assert services["restserver"]["environment"]["DOCSPELL_SERVER_BACKEND_JDBC_PASSWORD"] == services["joex"]["environment"]["DOCSPELL_JOEX_JDBC_PASSWORD"] == services["db"]["environment"]["POSTGRES_PASSWORD"]
    elif slug == "synapse":
        config = yaml.safe_load(parsed["configs"]["homeserver-config"]["content"])
        assert config["database"]["args"]["password"] == services["db"]["environment"]["POSTGRES_PASSWORD"]
        assert "--locale=C" in services["db"]["environment"]["POSTGRES_INITDB_ARGS"]
        assert config["server_name"] == services["init"]["environment"]["SYNAPSE_SERVER_NAME"]
        assert config["signing_key_path"] == "/data/" + config["server_name"] + ".signing.key"
        assert services["init"]["volumes"] == services["synapse"]["volumes"]
        assert config["enable_registration"] is False
        assert services["init"]["command"] == ["generate"]
        assert services["synapse"]["ports"][0]["host_ip"] == "127.0.0.1"
    elif slug == "tinyauth":
        web = next(iter(services.values()))
        assert web["environment"]["TINYAUTH_AUTH_USERS"].replace("$$", "$") == EXAMPLES["TINYAUTH_AUTH_USERS"]
    elif slug == "twenty":
        assert services["server"]["environment"]["PG_DATABASE_URL"] == services["worker"]["environment"]["PG_DATABASE_URL"]
        assert services["server"]["environment"]["ENCRYPTION_KEY"] == services["worker"]["environment"]["ENCRYPTION_KEY"]
        assert services["server"]["volumes"] == services["worker"]["volumes"]
        assert services["worker"]["depends_on"]["server"]["condition"] == "service_healthy"
    elif slug == "documenso":
        web = services["documenso"]["environment"]
        assert web["NEXT_PRIVATE_DATABASE_URL"] == web["NEXT_PRIVATE_DIRECT_DATABASE_URL"]
        assert f":{services['db']['environment']['POSTGRES_PASSWORD']}@db:5432/" in web["NEXT_PRIVATE_DATABASE_URL"]
        assert web["NEXT_PRIVATE_SIGNING_LOCAL_FILE_CONTENTS"] == env_for(additions[slug])["DOCUMENSO_SIGNING_CERTIFICATE_SECRET"]
        assert not services["documenso"].get("volumes")
        assert web["NEXT_PUBLIC_UPLOAD_TRANSPORT"] == "database"
    elif slug == "affine":
        assert services["affine"]["environment"]["DATABASE_URL"] == services["migration"]["environment"]["DATABASE_URL"]
        assert services["affine"]["volumes"] == services["migration"]["volumes"] == services["config-init"]["volumes"]
        assert services["affine"]["depends_on"]["migration"]["condition"] == "service_completed_successfully"
        assert services["migration"]["depends_on"]["config-init"]["condition"] == "service_completed_successfully"
    elif slug == "linkwarden":
        assert services["linkwarden"]["environment"]["MEILI_MASTER_KEY"] == services["search"]["environment"]["MEILI_MASTER_KEY"]
    elif slug == "openproject":
        for name in ["web", "worker", "cron", "seeder"]:
            assert services[name]["environment"]["DATABASE_URL"] == services["web"]["environment"]["DATABASE_URL"]
            assert services[name]["volumes"] == services["web"]["volumes"]
        assert services["web"]["environment"]["OPENPROJECT_COLLABORATIVE__EDITING__HOCUSPOCUS__SECRET"] == services["hocuspocus"]["environment"]["SECRET"]
        assert services["web"]["environment"]["OPENPROJECT_SEED__ADMIN__USER__PASSWORD"] == env_for(additions[slug])["OPENPROJECT_ADMIN_PASSWORD"]
    elif slug == "jitsi":
        assert services["prosody"]["environment"]["JICOFO_AUTH_PASSWORD"] == services["jicofo"]["environment"]["JICOFO_AUTH_PASSWORD"]
        assert services["prosody"]["environment"]["JVB_AUTH_PASSWORD"] == services["jvb"]["environment"]["JVB_AUTH_PASSWORD"]
        media = services["jvb"]["ports"][0]
        assert media["protocol"] == "udp"
        assert int(media["published"]) == media["target"] == int(services["jvb"]["environment"]["JVB_PORT"])
        initialized = {mount["source"] for mount in services["volume-init"]["volumes"]}
        for name in ["web", "prosody", "jicofo", "jvb"]:
            assert services[name]["read_only"] is True
            assert {mount["source"] for mount in services[name]["volumes"]} <= initialized
            assert services[name]["depends_on"]["volume-init"]["condition"] == "service_completed_successfully"
        assert services["prosody"]["environment"]["ENABLE_AUTH"] == "1"
    elif slug == "zammad":
        web = services["zammad-railsserver"]["environment"]
        database = services["db"]["environment"]
        assert web["POSTGRESQL_PASS"] == database["ZAMMAD_DB_PASS"]
        assert web["POSTGRESQL_USER"] != database["POSTGRES_USER"]
        assert web["POSTGRESQL_DB_CREATE"] == "false"
        assert "CREATE ROLE zammad LOGIN" in parsed["configs"]["database-init"]["content"]
        assert services["zammad-railsserver"]["depends_on"]["zammad-init"]["condition"] == "service_completed_successfully"
    elif slug == "formbricks":
        web = services["formbricks"]["environment"]
        assert web["AUTHZED_TOKEN"] == services["spicedb"]["environment"]["SPICEDB_GRPC_PRESHARED_KEY"]
        assert web["HUB_API_KEY"] == services["hub"]["environment"]["API_KEY"]
        assert web["CUBEJS_API_SECRET"] == services["cube"]["environment"]["CUBEJS_API_SECRET"]
        assert services["formbricks"]["depends_on"]["authzed-initialize"]["condition"] == "service_completed_successfully"
        assert services["hub-migrate"]["depends_on"]["formbricks-migrate"]["condition"] == "service_completed_successfully"
        assert services["authzed-initialize"]["depends_on"]["spicedb"]["condition"] == "service_healthy"
        assert "${CUBE}.user_id" in parsed["configs"]["cube-model"]["content"].replace("$$", "$")
        node = shutil.which("node")
        if node:
            for name in ["cube-config", "cube-model"]:
                javascript = tmp_path / f"{name}.js"
                javascript.write_text(parsed["configs"][name]["content"].replace("$$", "$"), encoding="utf-8")
                checked = subprocess.run([node, "--check", str(javascript)], capture_output=True, text=True, timeout=20)
                assert checked.returncode == 0, checked.stderr
        assert "GNU AFFERO GENERAL PUBLIC LICENSE" in (ROOT / "stacks/formbricks/LICENSE.upstream").read_text(encoding="utf-8")
    elif slug == "sparkyfitness":
        server = services["server"]["environment"]
        assert server["SPARKY_FITNESS_DB_PASSWORD"] == services["db"]["environment"]["POSTGRES_PASSWORD"]
        assert services["frontend"]["environment"]["SPARKY_FITNESS_SERVER_HOST"] == "server"
        assert int(services["frontend"]["environment"]["SPARKY_FITNESS_SERVER_PORT"]) == int(server["SPARKY_FITNESS_SERVER_PORT"])


@pytest.mark.skipif(COMPOSE is None, reason="Docker Compose config CLI is not installed")
def test_required_compose_values_cannot_be_silently_omitted(tmp_path, additions):
    for slug, app in additions.items():
        if app["type"] != "compose":
            continue
        text = (ROOT / app["compose"]).read_text(encoding="utf-8")
        # Escaped $${...} belongs to embedded scripts executed inside containers.
        required = set(re.findall(r"(?<!\$)\$\{([A-Z_0-9]+):\?", text))
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
