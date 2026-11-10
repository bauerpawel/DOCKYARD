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
    "readeck", "tududi", "easyappointments", "opencloud", "seafile", "directus", "nocobase",
    "librechat", "anythingllm", "dify", "rsshub", "commafeed", "myspeed", "whodb", "wakapi",
    "traccar", "librenms", "zabbix", "onetime-secret", "glitchtip",
    "2fauth", "olivetin", "mazanoke", "dufs", "hoppscotch", "rybbit", "sure",
    "libretranslate", "languagetool", "openlist", "slink", "jelu", "dumbdrop",
    "bar-assistant", "ryot", "linkace", "paperless-ai", "fileflows", "maintainerr", "dispatcharr",
    "dockhand", "zoraxy", "checkmk", "phpipam", "victoriametrics", "sonarqube",
    "apache-answer", "chatwoot", "glpi", "kanboard", "typebot", "erpnext", "owncast",
    "mediamtx", "music-assistant", "gamevault", "borgmatic", "zitadel", "profilarr", "cleanuparr",
    "garage", "seaweedfs", "zot", "openbao", "step-ca", "blocky", "roundcube", "nodebb",
    "zulip", "siyuan", "flatnotes", "etherpad", "papra", "pdfding", "cyberchef", "omni-tools",
    "bytebase", "convex", "shoko-server", "workout-cool",
    "spoolman", "cal-diy", "wekan", "taiga", "fider", "lemmy", "movary", "lyrion",
    "komf", "recyclarr", "scrypted", "dbgate", "couchdb", "clickhouse", "questdb",
    "opensearch", "nats", "redpanda", "prefect", "temporal",
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
    "READECK_ALLOWED_HOSTS": "read.example.com",
    "TUDUDI_USER_EMAIL": "admin@example.com",
    "TUDUDI_URL": "https://tasks.example.com",
    "OC_URL": "https://cloud.example.com",
    "SEAFILE_SERVER_HOSTNAME": "files.example.com",
    "INIT_SEAFILE_ADMIN_EMAIL": "admin@example.com",
    "ADMIN_EMAIL": "admin@example.com",
    "INIT_ROOT_EMAIL": "admin@example.com",
    "LIBRECHAT_URL": "https://chat.example.com",
    "WAKAPI_PUBLIC_URL": "https://coding.example.com",
    "ONETIME_HOST": "secrets.example.com",
    "GLITCHTIP_DOMAIN": "https://errors.example.com",
    "DIFY_URL": "https://ai.example.com",
    "DIFY_SOCKET_URL": "wss://ai.example.com",
    "HOPPSCOTCH_URL": "https://api.example.com",
    "HOPPSCOTCH_WS_URL": "wss://api.example.com",
    "BAR_ASSISTANT_URL": "https://bar.example.com",
    "RYOT_URL": "https://tracker.example.com",
    "DUFS_AUTH": "reader:private-test-password@/:rw",
    "DUMBDROP_PIN": "482619",
    "FRONTEND_URL": "https://support.example.com",
    "NEXT_PUBLIC_VIEWER_URL": "https://bots.example.com",
    "NEXT_PUBLIC_SMTP_FROM": "noreply@example.com",
    "SMTP_USERNAME": "smtp-user",
    "ERPNEXT_URL": "https://erp.example.com",
    "MEDIAMTX_PUBLIC_HOST": "203.0.113.10",
    "SERVER_ADMIN_USERNAME": "administrator",
    "ZITADEL_DOMAIN": "auth.example.com",
    "ZITADEL_ADMIN_EMAIL": "admin@example.com",
    "ZITADEL_ADMIN_PASSWORD": "Private-test-Only1!",
    "GARAGE_DEFAULT_ACCESS_KEY": "GK0123456789abcdef0123456789",
    "DOCKER_STEPCA_INIT_DNS_NAMES": "ca.example.com,localhost",
    "ROUNDCUBEMAIL_DEFAULT_HOST": "ssl://imap.example.com",
    "ROUNDCUBEMAIL_SMTP_SERVER": "tls://smtp.example.com",
    "ROUNDCUBEMAIL_DES_KEY": "a" * 24,
    "HOST_NAME": "pdf.example.com",
    "CONVEX_CLOUD_ORIGIN": "https://api.example.com",
    "CONVEX_SITE_ORIGIN": "https://actions.example.com",
    "SHOKO_MEDIA_DIR": "/srv/media/anime",
    "WORKOUT_URL": "https://workout.example.com",
    "SMTP_FROM": "noreply@example.com",
    "ZULIP_HOST": "chat.example.com",
    "ZULIP_ADMIN_EMAIL": "admin@example.com",
    "CALCOM_URL": "https://calendar.example.com",
    "CALENDSO_ENCRYPTION_KEY": "c" * 32,
    "WEKAN_URL": "https://boards.example.com",
    "TAIGA_DOMAIN": "projects.example.com",
    "LEMMY_HOSTNAME": "community.example.com",
    "LEMMY_ADMIN_EMAIL": "admin@example.com",
    "LYRION_BIND_IP": "192.0.2.10",
    "LYRION_MUSIC_DIR": "/srv/music",
    "KOMF_KOMGA_BASE_URI": "http://komga.example.com:25600",
    "SONARR_URL": "http://sonarr.example.com:8989",
    "OS_ADMIN_PASSWORD": "Private-test-Only1!",
    "PREFECT_URL": "https://flows.example.com",
    "TEMPORAL_UI_URL": "http://localhost:8089",
    "POSTGRES_PASSWORD": "1" * 64,
    "MONGO_ROOT_PASSWORD": "2" * 64,
    "MONGO_PASSWORD": "3" * 64,
    "PICTRS_API_KEY": "4" * 64,
    "LEMMY_ADMIN_PASSWORD": "5" * 64,
    "REDIS_PASSWORD": "6" * 64,
    "OS_DASHBOARDS_PASSWORD": "7" * 64,
    "PREFECT_API_PASSWORD": "8" * 64,
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
    if "DATA_ENCRYPTION_KEY" in values:
        values["DATA_ENCRYPTION_KEY"] = "d" * 32
    if "ZITADEL_MASTERKEY" in values:
        values["ZITADEL_MASTERKEY"] = "e" * 32
    if "ENCRYPTION_SECRET" in values:
        values["ENCRYPTION_SECRET"] = "f" * 32
    if app["slug"] == "typebot":
        values["NEXTAUTH_URL"] = "https://forms.example.com"
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
    if "CREDS_IV" in values:
        values["CREDS_IV"] = "b" * 32
    if "EMAIL_URL" in values:
        values["EMAIL_URL"] = "smtp://mail-user:mail-password@smtp.example.com:587"
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
    if slug not in {"komodo", "windmill", "anythingllm", "librenms", "dockhand", "phpipam", "music-assistant", "borgmatic", "shoko-server", "lyrion", "scrypted"}:
        assert result["plan"]["ready"] is True, result["plan"]["blockers"]
    if source["type"] == "compose":
        assert bool(plan["published_ports"]) is (slug not in {"borgmatic", "recyclarr", "scrypted"}), slug
        assert not any("${" in port for port in plan["published_ports"])
    if slug in {"valkey", "borgmatic", "recyclarr", "scrypted"}:
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


@pytest.mark.parametrize("slug,reason", [("lyrion", "LYRION_MUSIC_DIR"), ("scrypted", "network_mode")])
def test_music_and_camera_host_access_requires_explicit_approval(mcp_results, slug, reason):
    result = mcp_results[slug]
    assert result["plan"]["ready"] is False
    assert result["approved"]["ready"] is True
    assert any(reason in warning for warning in result["plan"]["warnings"])


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


def test_siyuan_access_code_is_local_secret_and_authentication_stays_enabled(mcp_results):
    result = mcp_results["siyuan"]
    spec = next(item for item in result["app"]["env"] if item["name"] == "SIYUAN_ACCESS_AUTH_CODE")
    assert spec["secret"] is True and spec["default"] == ""
    assert "SIYUAN_ACCESS_AUTH_CODE" in result["plan"]["secrets_to_set"]
    compose = yaml.safe_load(result["plan"]["docker"]["compose"])
    app = next(iter(compose["services"].values()))
    assert app["command"] == "serve --workspace=/siyuan/workspace"
    assert "SIYUAN_ACCESS_AUTH_CODE_BYPASS" not in app["environment"]


def test_roundcube_key_and_pdfding_private_registration_survive_feed_conversion(mcp_results):
    roundcube = mcp_results["roundcube"]["plan"]
    assert "ROUNDCUBEMAIL_DES_KEY" in roundcube["secrets_to_set"]
    pdfding = mcp_results["pdfding"]["app"]
    values = {item["name"]: item["default"] for item in pdfding["env"]}
    assert values["DISABLE_USER_SIGNUP"] == "TRUE"
    assert values["SESSION_COOKIE_SECURE"] == values["CSRF_COOKIE_SECURE"] == "TRUE"


def test_windmill_worker_privileges_require_explicit_approval(mcp_results):
    result = mcp_results["windmill"]
    assert result["plan"]["ready"] is False
    assert result["approved"]["ready"] is True
    assert "privileged" in result["app"]["description"]


@pytest.mark.parametrize("slug,capability", [("anythingllm", "SYS_ADMIN"), ("librenms", "NET_ADMIN")])
def test_browser_and_network_polling_capabilities_require_explicit_approval(mcp_results, slug, capability):
    result = mcp_results[slug]
    assert result["plan"]["ready"] is False
    assert result["approved"]["ready"] is True
    assert capability in result["app"]["description"]
    assert any("cap_add" in warning for warning in result["plan"]["warnings"])


@pytest.mark.parametrize("slug,name", [("librechat", "CREDS_IV"), ("librenms", "LIBRENMS_SNMP_COMMUNITY"), ("glitchtip", "EMAIL_URL"), ("dufs", "DUFS_AUTH"), ("dumbdrop", "DUMBDROP_PIN"), ("borgmatic", "BORG_PASSPHRASE")])
def test_unusually_named_credentials_are_requested_locally(additions, mcp_results, slug, name):
    result = mcp_results[slug]
    field = next(spec for spec in result["app"]["env"] if spec["name"] == name)
    assert field["secret"] is True
    assert field["default"] == ""
    assert name in result["plan"]["secrets_to_set"]
    assert env_for(additions[slug])[name] not in json.dumps(result)


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


def test_next_twenty_sql_stacks_reuse_the_catalog_database_image(additions):
    standard = additions["postgresql"]["image"]
    for slug in ["directus", "nocobase", "traccar", "zabbix", "glitchtip", "dify"]:
        stack = yaml.safe_load((ROOT / additions[slug]["compose"]).read_text(encoding="utf-8"))
        database = stack["services"]["db_postgres" if slug == "dify" else "db"]
        assert database["image"] == standard
        assert "database:/var/lib/postgresql" in database["volumes"]
        assert not database.get("ports")


def test_proposed_twenty_databases_and_local_frontends(additions):
    standard = additions["postgresql"]["image"]
    for slug in ["hoppscotch", "rybbit", "sure", "ryot"]:
        services = yaml.safe_load((ROOT / additions[slug]["compose"]).read_text(encoding="utf-8"))["services"]
        assert services["db"]["image"] == standard
        assert "database:/var/lib/postgresql" in services["db"]["volumes"]
    for slug in ["olivetin", "hoppscotch", "rybbit", "sure", "libretranslate", "languagetool",
                 "bar-assistant", "ryot", "linkace", "paperless-ai", "fileflows"]:
        services = yaml.safe_load((ROOT / additions[slug]["compose"]).read_text(encoding="utf-8"))["services"]
        for service in services.values():
            assert all(port.startswith("127.0.0.1:") for port in service.get("ports", []))
            assert not service.get("privileged")
            assert not any("docker.sock" in str(volume) for volume in service.get("volumes", []))
        for name in {"db", "redis", "clickhouse", "meilisearch"} & services.keys():
            assert not services[name].get("ports")


@pytest.mark.parametrize("slug,warning", [("dockhand", "docker.sock"), ("phpipam", "cap_add"),
                                          ("music-assistant", "host"), ("borgmatic", "BACKUP_SOURCE")])
def test_infrastructure_host_access_requires_explicit_approval(mcp_results, slug, warning):
    result = mcp_results[slug]
    assert result["plan"]["ready"] is False
    assert result["approved"]["ready"] is True
    assert any(warning in item for item in result["plan"]["warnings"])


def test_infrastructure_postgresql_storage_and_private_databases(additions):
    for slug in ["sonarqube", "chatwoot", "typebot", "gamevault", "zitadel"]:
        services = yaml.safe_load((ROOT / additions[slug]["compose"]).read_text(encoding="utf-8"))["services"]
        assert "database:/var/lib/postgresql" in services["db"]["volumes"]
        assert not services["db"].get("ports")
        if slug == "chatwoot":
            assert services["db"]["image"].startswith("pgvector/pgvector:pg18-bookworm@sha256:")
        else:
            assert services["db"]["image"] == additions["postgresql"]["image"]
    for slug in ["phpipam", "glpi", "erpnext"]:
        services = yaml.safe_load((ROOT / additions[slug]["compose"]).read_text(encoding="utf-8"))["services"]
        assert not services["db"].get("ports")


def test_checkmk_platform_and_sonarqube_required_host_limits(additions):
    checkmk = yaml.safe_load((ROOT / additions["checkmk"]["compose"]).read_text(encoding="utf-8"))["services"]["checkmk"]
    assert checkmk["platform"] == "linux/amd64"
    assert "/opt/omd/sites/cmk/tmp:uid=1000,gid=1000" in checkmk["tmpfs"]
    sonar = yaml.safe_load((ROOT / additions["sonarqube"]["compose"]).read_text(encoding="utf-8"))["services"]["sonarqube"]
    assert sonar["ulimits"]["nofile"]["soft"] >= 131072
    assert sonar["ulimits"]["nproc"] >= 8192
    assert "vm.max_map_count >= 524288" in additions["sonarqube"]["note"]


def assert_bind_refuses_to_create_host_path(mount, compose_text):
    """The file Compose reads must opt out, and the normalized mount must not ask to create the path.

    Compose v2.40 stores the field as a bool with omitempty, so an explicit
    false renders as `"bind": {}`. Compose v5 stores it as OptOut with
    omitzero, so false is emitted and the default true renders as `"bind": {}`.
    In both versions the bind object is present and is not true, which selects
    the Mount API and does not create a missing host directory. Dropping the
    bind block is the unsafe result: Compose falls back to the legacy bind
    string and creates the directory.
    """
    assert "create_host_path: false" in compose_text
    bind = mount.get("bind")
    assert isinstance(bind, dict), "bind options were dropped; Compose would create the missing host path"
    assert bind.get("create_host_path", False) is False


@pytest.mark.skipif(COMPOSE is None, reason="Docker Compose config CLI is not installed")
def test_compose_keeps_create_host_path_false_distinct_from_omitted(tmp_path):
    compose = tmp_path / "docker-compose.yml"
    compose.write_text("""services:
  off:
    image: busybox:latest
    volumes:
      - type: bind
        source: /tmp/missing-off
        target: /data
        bind:
          create_host_path: false
  on:
    image: busybox:latest
    volumes:
      - type: bind
        source: /tmp/missing-on
        target: /data
        bind:
          create_host_path: true
  omitted:
    image: busybox:latest
    volumes:
      - type: bind
        source: /tmp/missing-omitted
        target: /data
""", encoding="utf-8")
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    result = subprocess.run(
        COMPOSE + ["--project-directory", str(tmp_path), "--env-file", str(empty), "-f", str(compose), "config", "--format", "json"],
        capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert result.returncode == 0, result.stderr
    services = json.loads(result.stdout)["services"]
    off = services["off"]["volumes"][0]
    on = services["on"]["volumes"][0]
    omitted = services["omitted"]["volumes"][0]
    source = compose.read_text(encoding="utf-8")
    assert_bind_refuses_to_create_host_path(off, source)
    # Explicit true is rendered as true on Compose v2 and omitted inside a
    # present bind object on Compose v5, where true is the default. It must
    # not render as false, and it must not collapse into the omitted form.
    on_bind = on.get("bind")
    assert isinstance(on_bind, dict)
    assert on_bind.get("create_host_path") is not False
    assert "bind" not in omitted


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
        if slug not in {"formbricks", "zammad", "dify"}:
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
    elif slug == "librechat":
        mongo = services["mongodb"]["environment"]
        web = services["librechat"]
        assert f":{mongo['MONGO_INITDB_ROOT_PASSWORD']}@mongodb:27017/LibreChat?authSource=admin" in web["environment"]["MONGO_URI"]
        assert not services["mongodb"].get("ports")
        assert web["environment"]["SEARCH"] == "false"
        assert web["ports"][0]["host_ip"] == "127.0.0.1"
    elif slug == "anythingllm":
        web = services["anythingllm"]
        assert web["environment"]["STORAGE_DIR"] == "/app/server/storage"
        assert any(mount["target"] == "/app/server/storage" for mount in web["volumes"])
        assert "/app/server/storage/runtime.env" in web["command"][0]
        assert web["ports"][0]["host_ip"] == "127.0.0.1"
    elif slug == "seafile":
        web = services["seafile"]["environment"]
        assert web["SEAFILE_MYSQL_DB_PASSWORD"] == env_for(additions[slug])["SEAFILE_MYSQL_DB_PASSWORD"]
        assert web["INIT_SEAFILE_MYSQL_ROOT_PASSWORD"] == services["db"]["environment"]["MARIADB_ROOT_PASSWORD"]
        assert web["REDIS_PASSWORD"] == services["redis"]["environment"]["REDIS_PASSWORD"]
        assert web["ENABLE_SEADOC"] == web["ENABLE_NOTIFICATION_SERVER"] == web["ENABLE_SEAFILE_AI"] == "false"
        assert not services["db"].get("ports")
        assert not services["redis"].get("ports")
    elif slug == "traccar":
        config = parsed["configs"]["traccar-config"]["content"]
        entries = {entry.attrib["key"]: entry.text for entry in ET.fromstring(config)}
        assert entries["database.password"] == services["db"]["environment"]["POSTGRES_PASSWORD"]
        assert entries["database.driver"] == "org.postgresql.Driver"
        assert {p["protocol"] for p in services["traccar"]["ports"] if p["target"] == 5055} == {"tcp", "udp"}
    elif slug == "zabbix":
        password = services["db"]["environment"]["POSTGRES_PASSWORD"]
        assert services["server"]["environment"]["POSTGRES_PASSWORD"] == services["web"]["environment"]["POSTGRES_PASSWORD"] == password
        assert services["web"]["ports"][0]["host_ip"] == "127.0.0.1"
    elif slug == "dify":
        api = services["api"]["environment"]
        plugin = services["plugin_daemon"]["environment"]
        agent = services["agent_backend"]["environment"]
        assert api["DB_PASSWORD"] == plugin["DB_PASSWORD"] == services["db_postgres"]["environment"]["POSTGRES_PASSWORD"]
        assert api["REDIS_PASSWORD"] == plugin["REDIS_PASSWORD"] == services["redis"]["environment"]["REDISCLI_AUTH"]
        assert plugin["REDIS_HOST"] == api["REDIS_HOST"] == "redis"
        assert api["PLUGIN_DAEMON_KEY"] == plugin["SERVER_KEY"] == agent["DIFY_AGENT_PLUGIN_DAEMON_API_KEY"]
        assert api["INNER_API_KEY_FOR_PLUGIN"] == plugin["DIFY_INNER_API_KEY"] == agent["DIFY_AGENT_INNER_API_KEY"]
        assert api["AGENT_BACKEND_API_TOKEN"] == agent["DIFY_AGENT_API_TOKEN"]
        assert services["local_sandbox"]["environment"]["SHELLCTL_AUTH_TOKEN"] == agent["DIFY_AGENT_LOCAL_SANDBOX_AUTH_TOKEN"]
        assert api["CODE_EXECUTION_API_KEY"] == services["sandbox"]["environment"]["API_KEY"]
        vector = services["weaviate"]["environment"]
        assert api["WEAVIATE_API_KEY"] == vector["AUTHENTICATION_APIKEY_ALLOWED_KEYS"]
        assert vector["AUTHENTICATION_ANONYMOUS_ACCESS_ENABLED"] == "false"
        for name in ["worker", "worker_beat", "api_websocket"]:
            assert services[name]["environment"]["MIGRATION_ENABLED"] == "false"
            assert services[name]["depends_on"]["api"]["condition"] == "service_healthy"
            assert services[name]["volumes"] == services["api"]["volumes"]
        assert {name for name, service in services.items() if service.get("ports")} == {"nginx"}
        assert services["nginx"]["ports"][0]["host_ip"] == "127.0.0.1"
        for name in ["sandbox", "local_sandbox"]:
            assert all(parsed["networks"][network]["internal"] for network in services[name]["networks"])
        nginx = parsed["configs"]["nginx-default"]["content"].replace("$$", "$")
        assert "api_websocket:5001" in nginx and "$http_upgrade" in nginx
        assert "CREATE DATABASE dify_plugin OWNER dify" in parsed["configs"]["database-init"]["content"]
        assert "additional conditions" in (ROOT / "stacks/dify/LICENSE.upstream").read_text(encoding="utf-8")
    elif slug == "hoppscotch":
        services = parsed["services"]
        app = services["hoppscotch"]
        assert app["environment"] == services["migrate"]["environment"]
        assert app["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
        assert services["migrate"]["working_dir"] == "/dist/backend"
        assert services["migrate"]["command"] == ["sh", "-c", "pnpm exec prisma migrate deploy"]
        assert ":" + services["db"]["environment"]["POSTGRES_PASSWORD"] + "@db:5432/" in app["environment"]["DATABASE_URL"]
        assert app["environment"]["VITE_BACKEND_WS_URL"] == EXAMPLES["HOPPSCOTCH_WS_URL"] + "/backend/graphql"
        assert app["environment"]["VITE_ADMIN_URL"] == EXAMPLES["HOPPSCOTCH_URL"] + "/admin"
        assert app["environment"]["ENABLE_SUBPATH_BASED_ACCESS"] == "true"
        assert any(volume["target"] == "/data" for volume in app["volumes"])
    elif slug == "rybbit":
        services = parsed["services"]
        backend = services["backend"]["environment"]
        assert backend["POSTGRES_PASSWORD"] == services["db"]["environment"]["POSTGRES_PASSWORD"]
        assert backend["CLICKHOUSE_PASSWORD"] == services["clickhouse"]["environment"]["CLICKHOUSE_PASSWORD"]
        assert backend["REDIS_PASSWORD"] == services["redis"]["environment"]["REDISCLI_AUTH"]
        assert backend["BASE_URL"] == services["client"]["environment"]["NEXT_PUBLIC_BACKEND_URL"]
        assert {name for name, service in services.items() if service.get("ports")} == {"web"}
        for name, spec in parsed["configs"].items():
            if name.startswith("clickhouse_"):
                ET.fromstring(spec["content"])
    elif slug == "sure":
        services = parsed["services"]
        web = services["web"]["environment"]
        assert web == services["worker"]["environment"]
        assert web["POSTGRES_PASSWORD"] == services["db"]["environment"]["POSTGRES_PASSWORD"]
        assert services["redis"]["environment"]["REDISCLI_AUTH"] in web["REDIS_URL"]
        assert services["worker"]["depends_on"]["web"]["condition"] == "service_healthy"
    elif slug == "bar-assistant":
        services = parsed["services"]
        app = services["bar-assistant"]["environment"]
        assert app["MEILISEARCH_KEY"] == services["meilisearch"]["environment"]["MEILI_MASTER_KEY"]
        assert app["APP_URL"] == services["salt-rim"]["environment"]["API_URL"] == EXAMPLES["BAR_ASSISTANT_URL"] + "/bar"
        assert services["salt-rim"]["environment"]["MEILISEARCH_URL"] == EXAMPLES["BAR_ASSISTANT_URL"] + "/search"
        assert {name for name, service in services.items() if service.get("ports")} == {"web"}
    elif slug == "linkace":
        services = parsed["services"]
        app = services["app"]["environment"]
        assert app["DB_PASSWORD"] == services["db"]["environment"]["MARIADB_PASSWORD"]
        assert app["REDIS_PASSWORD"] == services["redis"]["environment"]["REDISCLI_AUTH"]
        assert app["MEILISEARCH_KEY"] == services["meilisearch"]["environment"]["MEILI_MASTER_KEY"]
    elif slug == "languagetool":
        env = parsed["services"]["languagetool"]["environment"]
        assert env["JAVA_XMX"] == "1g"
        assert "Java_Xmx" not in env
    elif slug == "olivetin":
        config = yaml.safe_load(parsed["configs"]["olivetin-config"]["content"])
        assert config["actions"][0]["shell"] == "date -u"
    elif slug == "phpipam":
        services = parsed["services"]
        for name in ["web", "cron"]:
            assert services[name]["environment"]["IPAM_DATABASE_PASS"] == services["db"]["environment"]["MARIADB_PASSWORD"]
            assert {"NET_ADMIN", "NET_RAW"} <= set(services[name]["cap_add"])
    elif slug == "chatwoot":
        services = parsed["services"]
        assert services["web"]["environment"] == services["worker"]["environment"] == services["prepare"]["environment"]
        env = services["web"]["environment"]
        assert env["POSTGRES_PASSWORD"] == services["db"]["environment"]["POSTGRES_PASSWORD"]
        assert env["REDIS_PASSWORD"] == services["redis"]["environment"]["REDISCLI_AUTH"]
        assert services["prepare"]["command"] == ["bundle", "exec", "rails", "db:chatwoot_prepare"]
        for name in ["web", "worker"]:
            assert services[name]["depends_on"]["prepare"]["condition"] == "service_completed_successfully"
            assert services[name]["volumes"] == services["prepare"]["volumes"]
    elif slug == "glpi":
        services = parsed["services"]
        assert services["glpi"]["environment"]["GLPI_DB_PASSWORD"] == services["db"]["environment"]["MARIADB_PASSWORD"]
        assert services["glpi"]["environment"]["GLPI_CRONTAB_ENABLED"] == "true"
    elif slug == "typebot":
        services = parsed["services"]
        env = services["builder"]["environment"]
        assert env == services["viewer"]["environment"]
        assert services["db"]["environment"]["POSTGRES_PASSWORD"] in env["DATABASE_URL"]
        assert services["redis"]["environment"]["REDISCLI_AUTH"] in env["REDIS_URL"]
        assert len(env["ENCRYPTION_SECRET"]) == 32
        assert services["viewer"]["depends_on"]["builder"]["condition"] == "service_healthy"
        assert env["NEXTAUTH_URL"] == "https://forms.example.com"
        assert env["NEXT_PUBLIC_VIEWER_URL"] == EXAMPLES["NEXT_PUBLIC_VIEWER_URL"]
        assert "Functional Source License" in (ROOT / "stacks/typebot/LICENSE.upstream").read_text(encoding="utf-8")
    elif slug == "erpnext":
        services = parsed["services"]
        config_env = services["configurator"]["environment"]
        password = services["redis-cache"]["environment"]["REDISCLI_AUTH"]
        assert password == services["redis-queue"]["environment"]["REDISCLI_AUTH"]
        assert f":{password}@redis-cache:" in config_env["FRAPPE_REDIS_CACHE"]
        assert f":{password}@redis-queue:" in config_env["FRAPPE_REDIS_QUEUE"]
        site_env = services["create-site"]["environment"]
        assert site_env["DB_ROOT_PASSWORD"] == services["db"]["environment"]["MARIADB_ROOT_PASSWORD"]
        assert services["create-site"]["depends_on"]["configurator"]["condition"] == "service_completed_successfully"
        script = services["create-site"]["command"][0].replace("$$", "$")
        assert '.dockyard-initialized' in script
        assert '--admin-password "${ERPNEXT_ADMIN_PASSWORD}"' in script
        assert site_env["ERPNEXT_ADMIN_PASSWORD"] not in script
        for name in ["backend", "websocket", "queue-short", "queue-long", "scheduler"]:
            assert services[name]["depends_on"]["create-site"]["condition"] == "service_completed_successfully"
            assert services[name]["volumes"] == services["create-site"]["volumes"]
        assert {name for name, service in services.items() if service.get("ports")} == {"frontend"}
    elif slug == "mediamtx":
        config = yaml.safe_load(parsed["configs"]["mediamtx-config"]["content"])
        publisher, viewer = config["authInternalUsers"]
        assert publisher["pass"] == env_for(additions[slug])["MEDIAMTX_PUBLISH_PASSWORD"]
        assert viewer["pass"] == env_for(additions[slug])["MEDIAMTX_READ_PASSWORD"]
        assert {permission["action"] for permission in publisher["permissions"]} == {"publish"}
        assert {permission["action"] for permission in viewer["permissions"]} == {"read", "playback"}
        assert config["api"] is False and config["rtspTransports"] == ["tcp"]
        assert config["webrtcAdditionalHosts"] == [EXAMPLES["MEDIAMTX_PUBLIC_HOST"]]
    elif slug == "gamevault":
        services = parsed["services"]
        assert services["gamevault"]["environment"]["DB_PASSWORD"] == services["db"]["environment"]["POSTGRES_PASSWORD"]
        assert services["gamevault"]["environment"]["SERVER_ADMIN_USERNAME"] == EXAMPLES["SERVER_ADMIN_USERNAME"]
    elif slug == "borgmatic":
        services = parsed["services"]
        assert not any(service.get("ports") for service in services.values())
        assert services["init"]["command"] == ["borgmatic", "repo-create", "--encryption", "repokey-blake2"]
        assert services["init"]["environment"]["CRON"] == "false"
        assert services["borgmatic"]["depends_on"]["init"]["condition"] == "service_completed_successfully"
        for service in services.values():
            source = next(volume for volume in service["volumes"] if volume["target"] == "/mnt/source")
            assert source["read_only"] is True
        config = yaml.safe_load(parsed["configs"]["borgmatic-config"]["content"])
        assert config["source_directories"] == ["/mnt/source"]
    elif slug == "zitadel":
        services = parsed["services"]
        api = services["zitadel"]
        assert api["command"] == ["start-from-init", "--masterkeyFromEnv"]
        assert len(api["environment"]["ZITADEL_MASTERKEY"]) == 32
        assert services["db"]["environment"]["POSTGRES_PASSWORD"] in api["environment"]["ZITADEL_DATABASE_POSTGRES_DSN"]
        assert api["environment"]["ZITADEL_FIRSTINSTANCE_ORG_HUMAN_EMAIL_ADDRESS"] == EXAMPLES["ZITADEL_ADMIN_EMAIL"]
        login = services["login"]
        assert login["environment"]["ZITADEL_SERVICE_USER_TOKEN_FILE"] == api["environment"]["ZITADEL_FIRSTINSTANCE_LOGINCLIENTPATPATH"]
        assert login["volumes"][0]["source"] == api["volumes"][0]["source"]
        assert login["volumes"][0]["read_only"] is True
        assert "reverse_proxy h2c://zitadel:8080" in parsed["configs"]["web"]["content"]
        assert "header_up X-Forwarded-Proto https" in parsed["configs"]["web"]["content"]
        assert {name for name, service in services.items() if service.get("ports")} == {"web"}
    elif slug == "profilarr":
        services = parsed["services"]
        assert services["profilarr"]["environment"]["PARSER_HOST"] == "parser"
        assert not services["parser"].get("ports")
    elif slug == "garage":
        app = parsed["services"]["garage"]
        config = tomllib.loads(parsed["configs"]["garage-config"]["content"])
        assert app["command"] == ["/garage", "server", "--single-node", "--default-bucket"]
        assert config["replication_factor"] == 1
        assert app["environment"]["GARAGE_DEFAULT_ACCESS_KEY"] == EXAMPLES["GARAGE_DEFAULT_ACCESS_KEY"]
        assert app["ports"][0]["host_ip"] == "127.0.0.1"
    elif slug == "seaweedfs":
        config = json.loads(parsed["configs"]["s3-config"]["content"])
        credentials = config["identities"][0]["credentials"][0]
        assert credentials["accessKey"] == env_for(additions[slug])["S3_ACCESS_KEY_ID"]
        assert credentials["secretKey"] == env_for(additions[slug])["S3_SECRET_ACCESS_KEY"]
        filer = tomllib.loads(parsed["configs"]["filer-config"]["content"])
        assert filer["leveldb2"] == {"enabled": True, "dir": "/data/filerldb2"}
        assert [p["target"] for p in parsed["services"]["seaweedfs"]["ports"]] == [8333]
    elif slug == "zot":
        services = parsed["services"]
        config = json.loads(parsed["configs"]["zot-config"]["content"])
        assert config["http"]["auth"]["htpasswd"]["path"] == "/auth/htpasswd"
        assert services["zot"]["depends_on"]["auth-init"]["condition"] == "service_completed_successfully"
        script = services["auth-init"]["command"][0].replace("$$", "$")
        assert '"$ZOT_PASSWORD"' in script
        assert env_for(additions[slug])["ZOT_PASSWORD"] not in script
        assert not services["auth-init"].get("ports")
    elif slug == "openbao":
        app = parsed["services"]["openbao"]
        config = json.loads(app["environment"]["BAO_LOCAL_CONFIG"])
        assert app["command"] == ["server"]
        assert config["storage"] == {"file": {"path": "/openbao/file"}}
        assert config["disable_mlock"] is True
        assert "BAO_DEV_ROOT_TOKEN_ID" not in app["environment"]
        assert app["ports"][0]["host_ip"] == "127.0.0.1"
        assert not app.get("cap_add")
    elif slug == "blocky":
        config = yaml.safe_load(parsed["configs"]["blocky-config"]["content"])
        assert config["blocking"]["clientGroupsBlock"]["default"] == ["ads"]
        ports = parsed["services"]["blocky"]["ports"]
        assert {p["protocol"] for p in ports if p["target"] == 53} == {"tcp", "udp"}
        assert all(p["host_ip"] == "127.0.0.1" for p in ports)
    elif slug == "nodebb":
        services = parsed["services"]
        config = json.loads(parsed["configs"]["nodebb-setup"]["content"])
        assert config["defaults"]["postgres"]["password"] == services["db"]["environment"]["POSTGRES_PASSWORD"]
        assert not services["db"].get("ports")
        assert {v["target"] for v in services["nodebb"]["volumes"]} >= {"/opt/config", "/usr/src/app/public/uploads", "/usr/src/app/node_modules"}
    elif slug == "etherpad":
        services = parsed["services"]
        app = services["etherpad"]["environment"]
        assert app["DB_PASS"] == services["db"]["environment"]["POSTGRES_PASSWORD"]
        assert app["REQUIRE_AUTHENTICATION"] == "true"
        assert app["AUTHENTICATION_METHOD"] == "apikey"
        assert any(v["target"] == "/opt/etherpad-lite/var" for v in services["etherpad"]["volumes"])
    elif slug == "bytebase":
        app = parsed["services"]["bytebase"]
        assert app["init"] is True
        assert any(v["target"] == "/var/opt/bytebase" for v in app["volumes"])
    elif slug == "convex":
        services = parsed["services"]
        assert services["dashboard"]["environment"]["NEXT_PUBLIC_DEPLOYMENT_URL"] == services["backend"]["environment"]["CONVEX_CLOUD_ORIGIN"]
        assert services["dashboard"]["depends_on"]["backend"]["condition"] == "service_healthy"
        assert all(p["host_ip"] == "127.0.0.1" for s in services.values() for p in s.get("ports", []))
    elif slug == "shoko-server":
        app = parsed["services"]["shoko"]
        mount = next(v for v in app["volumes"] if v["target"] == "/mnt/anime")
        assert mount["type"] == "bind" and mount["read_only"] is True
        assert_bind_refuses_to_create_host_path(mount, compose.read_text(encoding="utf-8"))
        assert mcp_results[slug]["plan"]["ready"] is False
        assert mcp_results[slug]["approved"]["ready"] is True
    elif slug == "workout-cool":
        services = parsed["services"]
        app = services["workout"]
        assert ":" + services["db"]["environment"]["POSTGRES_PASSWORD"] + "@db:5432/" in app["environment"]["DATABASE_URL"]
        assert app["entrypoint"] == ["/bin/sh", "-ec"]
        assert app["command"][0].index("prisma migrate deploy") < app["command"][0].index("exec pnpm start")
        assert app["environment"]["BETTER_AUTH_URL"] == app["environment"]["NEXT_PUBLIC_APP_URL"]
        assert app["environment"]["DEFAULT_BILLING_MODE"] == "DISABLED"
    elif slug == "zulip":
        services = parsed["services"]
        app = services["zulip"]["environment"]
        assert app["SECRETS_postgres_password"] == services["database"]["environment"]["POSTGRES_PASSWORD"]
        assert app["SECRETS_redis_password"] == services["redis"]["environment"]["REDISCLI_AUTH"]
        assert app["SECRETS_rabbitmq_password"] == services["rabbitmq"]["environment"]["RABBITMQ_DEFAULT_PASS"]
        assert app["SECRETS_memcached_password"] == services["memcached"]["environment"]["MEMCACHED_PASSWORD"]
        assert app["SECRETS_email_password"] == env_for(additions[slug])["SMTP_PASSWORD"]
        assert app["TRUST_GATEWAY_IP"] == "true"
        assert {name for name, service in services.items() if service.get("ports")} == {"zulip"}
    elif slug == "cal-diy":
        services = parsed["services"]
        app = services["calcom"]["environment"]
        assert ":" + services["db"]["environment"]["POSTGRES_PASSWORD"] + "@db:5432/" in app["DATABASE_URL"]
        assert app["DATABASE_DIRECT_URL"] == app["DATABASE_URL"]
        assert app["NEXTAUTH_URL"] == app["NEXT_PUBLIC_WEBAPP_URL"] + "/api/auth"
        assert len(app["CALENDSO_ENCRYPTION_KEY"]) == 32
        assert services["calcom"]["platform"] == "linux/amd64"
    elif slug == "wekan":
        services = parsed["services"]
        db = services["db"]["environment"]
        assert db["MONGO_INITDB_ROOT_PASSWORD"] != db["MONGO_APP_PASSWORD"]
        assert "mongodb://wekan:" + db["MONGO_APP_PASSWORD"] + "@db:" in services["wekan"]["environment"]["MONGO_URL"]
        assert services["wekan"]["environment"]["WEKAN_DB"] == "mongodb"
        assert not services["db"].get("ports")
        init = parsed["configs"]["mongo-init"]["content"]
        assert "process.env.MONGO_APP_PASSWORD" in init and "role: 'readWrite'" in init
    elif slug == "lemmy":
        services = parsed["services"]
        config = json.loads(parsed["configs"]["lemmy-config"]["content"])
        assert config["database"]["password"] == services["db"]["environment"]["POSTGRES_PASSWORD"]
        assert config["pictrs"]["api_key"] == services["pictrs"]["environment"]["PICTRS__SERVER__API_KEY"]
        assert config["setup"]["admin_password"] == env_for(additions[slug])["LEMMY_ADMIN_PASSWORD"]
        assert config["hostname"] == services["lemmy-ui"]["environment"]["LEMMY_UI_LEMMY_EXTERNAL_HOST"]
        assert services["pictrs"]["depends_on"]["image-init"]["condition"] == "service_completed_successfully"
        assert {name for name, service in services.items() if service.get("ports")} == {"gateway"}
    elif slug == "lyrion":
        app = parsed["services"]["lyrion"]
        mount = next(v for v in app["volumes"] if v["target"] == "/music")
        assert mount["read_only"] is True
        assert_bind_refuses_to_create_host_path(mount, compose.read_text(encoding="utf-8"))
        assert {p["host_ip"] for p in app["ports"]} == {EXAMPLES["LYRION_BIND_IP"]}
        assert {p["protocol"] for p in app["ports"] if p["target"] == 3483} == {"tcp", "udp"}
    elif slug == "scrypted":
        app = parsed["services"]["scrypted"]
        assert app["network_mode"] == "host" and not app.get("ports")
        assert not any(v["type"] == "bind" for v in app["volumes"])
    elif slug == "opensearch":
        services = parsed["services"]
        init = services["security-init"]
        admin = services["opensearch"]["environment"]["OPENSEARCH_INITIAL_ADMIN_PASSWORD"]
        assert init["environment"]["OPENSEARCH_INITIAL_ADMIN_PASSWORD"] == admin
        assert services["dashboards"]["environment"]["OPENSEARCH_PASSWORD"] == init["environment"]["OS_DASHBOARDS_PASSWORD"] != admin
        assert services["dashboards"]["depends_on"]["security-init"]["condition"] == "service_completed_successfully"
    elif slug == "redpanda":
        services = parsed["services"]
        config = yaml.safe_load(parsed["configs"]["console-config"]["content"])
        broker = services["redpanda"]["environment"]
        assert broker["RP_BOOTSTRAP_USER"] == "admin:" + config["kafka"]["sasl"]["password"]
        assert config["redpanda"]["adminApi"]["authentication"]["basic"]["password"] == config["kafka"]["sasl"]["password"]
        assert yaml.safe_load(parsed["configs"]["redpanda-bootstrap"]["content"])["admin_api_require_auth"] is True
    elif slug == "prefect":
        services = parsed["services"]
        server = services["server"]["environment"]
        assert ":" + services["db"]["environment"]["POSTGRES_PASSWORD"] + "@db:5432/" in server["PREFECT_SERVER_DATABASE_CONNECTION_URL"]
        assert server["PREFECT_REDIS_MESSAGING_PASSWORD"] == services["redis"]["environment"]["REDISCLI_AUTH"]
        assert server["PREFECT_SERVER_API_AUTH_STRING"] == services["worker"]["environment"]["PREFECT_API_AUTH_STRING"]
        assert services["services"]["environment"]["PREFECT_SERVER_DATABASE_CONNECTION_URL"] == server["PREFECT_SERVER_DATABASE_CONNECTION_URL"]
        assert services["worker"]["depends_on"]["server"]["condition"] == "service_healthy"
    elif slug == "temporal":
        services = parsed["services"]
        assert services["schema"]["environment"]["SQL_PASSWORD"] == services["db"]["environment"]["POSTGRES_PASSWORD"] == services["temporal"]["environment"]["POSTGRES_PWD"]
        assert services["temporal"]["depends_on"]["schema"]["condition"] == "service_completed_successfully"
        assert services["ui"]["depends_on"]["namespace"]["condition"] == "service_completed_successfully"
        schema = services["schema"]["command"][0]
        assert schema.index("setup-schema") < schema.index("update-schema")
        assert "temporal temporal_visibility" in schema


@pytest.mark.skipif(COMPOSE is None, reason="Docker Compose config CLI is not installed")
def test_required_compose_values_cannot_be_silently_omitted(tmp_path, additions):
    for slug, app in additions.items():
        if app["type"] != "compose":
            continue
        text = (ROOT / app["compose"]).read_text(encoding="utf-8")
        # Escaped $${...} belongs to embedded scripts executed inside containers.
        required = set(re.findall(r"(?<!\$)\$\{([A-Z_0-9]+):\?", text))
        assert required or slug in {"myspeed", "olivetin", "libretranslate", "languagetool", "paperless-ai", "fileflows", "dockhand", "zoraxy", "victoriametrics", "kanboard", "owncast", "cleanuparr", "openbao", "blocky", "bytebase", "scrypted"}, slug
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
