"""The Dockyard MCP script answers catalog and deploy-plan checks without Apache."""

import hashlib
import shutil
import subprocess
import http.client
import json
import re
import socket
import time
from pathlib import Path

import pytest
import yaml
import os

REPO_ROOT = Path(__file__).resolve().parents[1]
PHP = shutil.which("php")
OFFICIAL_FEED = "https://cdn.jsdelivr.net/gh/bauerpawel/DOCKYARD@main/templates.json"
GUIDE_LANGUAGES = ["en", "pl", "de", "fr"]
BROWSER = {"Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"}


@pytest.fixture(autouse=True)
def local_feed(monkeypatch):
    """An unconfigured server reads the feed from the official CDN; the suite stays offline."""
    monkeypatch.delenv("DOCKYARD_TEMPLATES_URL", raising=False)
    monkeypatch.setenv("DOCKYARD_TEMPLATES", str(REPO_ROOT / "templates.json"))


def php_json(tmp_path, body, *args, index=None, env=None):
    runner = tmp_path / "probe.php"
    runner.write_text("<?php require $argv[1];\n" + body, encoding="utf-8")
    result = subprocess.run([PHP, str(runner), str(index or REPO_ROOT / "mcp/index.php"), *map(str, args)],
                            capture_output=True, text=True, encoding="utf-8", env=env, timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.fixture
def compose_fixture(tmp_path):
    if PHP is None:
        pytest.skip("php is not on PATH")
    clone = tmp_path / "fixture"
    (clone / "mcp").mkdir(parents=True)
    (clone / "stacks/review").mkdir(parents=True)
    shutil.copyfile(REPO_ROOT / "mcp/index.php", clone / "mcp/index.php")
    shutil.copytree(REPO_ROOT / "mcp/vendor", clone / "mcp/vendor")
    (clone / "repository.json").write_text('{"url":"https://github.com/example/fixture"}')
    (clone / "templates.json").write_text(json.dumps({"version": "3", "templates": [{
        "id": 1, "type": 3, "name": "review", "title": "Review", "description": "Test",
        "categories": ["Other"], "repository": {"url": "https://github.com/example/fixture",
                                                 "stackfile": "stacks/review/docker-compose.yml"}
    }]}))
    env = os.environ.copy()
    env.pop("DOCKYARD_TEMPLATES_URL", None)
    env.pop("DOCKYARD_REPO_URL", None)
    env["DOCKYARD_TEMPLATES"] = str(clone / "templates.json")
    return clone, env


@pytest.mark.skipif(PHP is None, reason="php is not on PATH")
def test_mcp_self_test():
    result = subprocess.run(
        [PHP, str(REPO_ROOT / "mcp" / "index.php"), "--self-test"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.fixture
def php_server(tmp_path):
    if PHP is None:
        pytest.skip("php is not on PATH")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with (tmp_path / "php.log").open("w") as log:
        server = subprocess.Popen(
            [PHP, "-S", f"127.0.0.1:{port}", str(REPO_ROOT / "mcp" / "index.php")],
            cwd=REPO_ROOT, stdout=log, stderr=log,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            for _ in range(100):
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                        break
                except OSError:
                    if server.poll() is not None:
                        pytest.fail("PHP test server exited")
                    time.sleep(0.02)
            else:
                pytest.fail("PHP test server did not start")
            yield port
        finally:
            server.terminate()
            server.wait(timeout=5)


@pytest.mark.parametrize("size,status", [(65536, 200), (65537, 413)])
def test_mcp_request_size_limit(php_server, size, status):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"})
    body += " " * (size - len(body))
    connection = http.client.HTTPConnection("127.0.0.1", php_server, timeout=5)
    try:
        connection.request("POST", "/", body, {"Content-Type": "application/json", "Accept": "application/json"})
        response = connection.getresponse()
        decoded = json.loads(response.read())
        assert response.status == status
        assert ("error" in decoded) == (status == 413)
    finally:
        connection.close()


@pytest.mark.skipif(PHP is None, reason="php is not on PATH")
def test_mcp_compose_treats_title_and_network_as_data(tmp_path):
    runner = tmp_path / "runner.php"
    runner.write_text("""<?php
require $argv[1];
echo dockyard_container_compose([
    'image' => 'example/app:latest',
    'title' => "App\\nservices:\\n  injected: {}",
    'network' => "custom:\\n  injected: {}",
], 'safe-app', true, []);
""", encoding="utf-8")

    result = subprocess.run([PHP, str(runner), str(REPO_ROOT / "mcp" / "index.php")], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    parsed = yaml.safe_load(result.stdout)
    assert list(parsed["services"]) == ["safe-app"]
    assert parsed["networks"] == {"custom:\n  injected: {}": {"external": True}}


@pytest.mark.skipif(PHP is None, reason="php is not on PATH")
def test_mcp_local_stack_cannot_read_server_source(tmp_path):
    runner = tmp_path / "runner.php"
    runner.write_text("<?php require $argv[1]; echo json_encode(dockyard_read_local_stack('mcp/index.php'));", encoding="utf-8")

    result = subprocess.run([PHP, str(runner), str(REPO_ROOT / "mcp" / "index.php")], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) is None


@pytest.mark.skipif(PHP is None, reason="php is not on PATH")
@pytest.mark.parametrize("slug,password", [("n8n", "N8N_DB_PASSWORD"), ("gitea", "GITEA_DB_PASSWORD"), ("ghost", "GHOST_DB_PASSWORD"), ("wordpress", "WORDPRESS_DB_PASSWORD"), ("nextcloud", "NEXTCLOUD_DB_PASSWORD"), ("grafana-prometheus", "GRAFANA_ADMIN_PASSWORD")])
def test_local_stack_requires_password_and_accepts_local_secret(tmp_path, slug, password):
    runner = tmp_path / "runner.php"
    runner.write_text("""<?php
require $argv[1];
echo json_encode([
    dockyard_prepare_deploy(['slug' => $argv[2], 'confirm' => true]),
    dockyard_prepare_deploy(['slug' => $argv[2], 'confirm' => true, 'local_secrets' => [$argv[3]]]),
]);
""", encoding="utf-8")

    result = subprocess.run([PHP, str(runner), str(REPO_ROOT / "mcp" / "index.php"), slug, password], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    blocked, local = json.loads(result.stdout)
    assert blocked["ready"] is False
    assert any(password in reason for reason in blocked["blockers"])
    assert f"${{{password}:?" in blocked["docker"]["compose"]
    assert local["ready"] is True
    assert password in local["secrets_to_set"]
    assert f'{password}="CHANGEME"' in local["docker"]["env_file"]


@pytest.mark.skipif(PHP is None, reason="php is not on PATH")
def test_required_compose_vars_ignore_comments_and_escaped_dollars(tmp_path):
    runner = tmp_path / "runner.php"
    runner.write_text("""<?php
require $argv[1];
echo json_encode(dockyard_compose_env_blockers('# ${COMMENT:?not required}' . "\\n" . '$${LITERAL:?not required}', []));
""", encoding="utf-8")

    result = subprocess.run([PHP, str(runner), str(REPO_ROOT / "mcp" / "index.php")], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout) == []


@pytest.mark.parametrize("compose", [
    "services:\n  app:\n    image: busybox\n    privileged: true\n",
    'services: {app: {image: busybox, "privileged": true}}',
    "x-defaults: &defaults {image: busybox, privileged: true}\nservices:\n  app:\n    <<: *defaults\n",
    "services: {app: {image: busybox, privileged: '${ENABLE_PRIVILEGES:-false}'}}",
    "services: {app: {image: busybox, network_mode: host}}",
    "services: {app: {image: busybox, pid: host}}",
    "services: {app: {image: busybox, devices: ['/dev/dri:/dev/dri']}}",
    "services: {app: {image: busybox, cap_add: [SYS_ADMIN]}}",
    "services: {app: {image: busybox, volumes: ['/var/run/docker.sock:/socket:ro']}}",
    "services: {app: {image: busybox, volumes: [{type: bind, source: /var/run/../run/docker.sock, target: /socket}]}}",
    "services: {app: {image: busybox, volumes: ['${HOST_SOURCE}:/data']}}",
    "services: {app: {image: busybox, volumes: ['/:/host']}}",
    "services: {app: {image: busybox, extends: {file: extra.yml, service: base}}}",
    "include: [extra.yml]\nservices: {app: {image: busybox}}",
    "services: {app: {image: busybox, volumes: [host:/host]}}\nvolumes: {host: {driver_opts: {type: none, o: bind, device: /}}}",
])
def test_risky_compose_needs_separate_approval(compose_fixture, tmp_path, compose):
    clone, env = compose_fixture
    (clone / "stacks/review/docker-compose.yml").write_text(compose, encoding="utf-8")
    blocked, allowed = php_json(tmp_path, """
echo json_encode([
    dockyard_prepare_deploy(['slug' => 'review', 'confirm' => true, 'allow_privileged' => false]),
    dockyard_prepare_deploy(['slug' => 'review', 'confirm' => true, 'allow_privileged' => true]),
]);
""", index=clone / "mcp/index.php", env=env)
    assert blocked["ready"] is False
    assert blocked["warnings"] and any("allow_privileged=true" in value for value in blocked["blockers"])
    assert allowed["ready"] is True
    assert allowed["warnings"]


def test_safe_compose_with_comments_and_literals_is_ready(compose_fixture, tmp_path):
    clone, env = compose_fixture
    (clone / "stacks/review/docker-compose.yml").write_text("""# privileged: true
services:
  app:
    image: busybox
    privileged: false
    command: 'echo privileged: true /var/run/docker.sock'
    volumes: ['data:/data', './data:/config', '.:/project', {target: /anonymous}]
""")
    plan = php_json(tmp_path, "echo json_encode(dockyard_prepare_deploy(['slug'=>'review','confirm'=>true]));", index=clone / "mcp/index.php", env=env)
    assert plan["ready"] is True
    assert plan["warnings"] == []


@pytest.mark.parametrize("compose", ["services: [broken", "not-compose", "services: {}", "services: {app: !php/object bad}"])
def test_unparseable_compose_is_blocked_even_with_approval(compose_fixture, tmp_path, compose):
    clone, env = compose_fixture
    (clone / "stacks/review/docker-compose.yml").write_text(compose)
    plan = php_json(tmp_path, "echo json_encode(dockyard_prepare_deploy(['slug'=>'review','confirm'=>true,'allow_privileged'=>true]));", index=clone / "mcp/index.php", env=env)
    assert plan["ready"] is False
    assert plan["blockers"]


@pytest.mark.skipif(PHP is None, reason="php is not on PATH")
@pytest.mark.parametrize("repository", ["https://github.com/unrelated/project", "https://github.com/bauerpawel/DOCKYARD/tree/dev"])
def test_repository_collision_fetches_declared_source(tmp_path, repository):
    value = php_json(tmp_path, """
echo json_encode(dockyard_load_stack(['repository'=>['url'=>$argv[2],'stackfile'=>'stacks/n8n/docker-compose.yml']],
    static fn(string $url): string => 'REMOTE:' . $url));
""", repository)
    assert value.startswith("REMOTE:https://raw.githubusercontent.com/")
    assert ("unrelated/project/HEAD/" if "unrelated" in repository else "DOCKYARD/dev/") in value


@pytest.mark.skipif(PHP is None, reason="php is not on PATH")
def test_invalid_repository_cannot_bypass_checks_via_local_stack(tmp_path):
    value = php_json(tmp_path, """
try { dockyard_load_stack(['repository'=>['url'=>'https://evil.example/repo','stackfile'=>'stacks/n8n/docker-compose.yml']]); echo json_encode(false); }
catch (RuntimeException $error) { echo json_encode(true); }
""")
    assert value is True


@pytest.mark.parametrize("extra", [{"network": "host"}, {"volumes": [{"bind": "/var/run/docker.sock", "container": "/socket"}]}])
def test_generated_container_compose_requires_host_access_approval(compose_fixture, tmp_path, extra):
    clone, env = compose_fixture
    path = clone / "templates.json"
    feed = json.loads(path.read_text())
    feed["templates"][0] = {"id": 1, "name": "review", "title": "Review", "type": 1, "image": "busybox:latest", "categories": ["Other"]} | extra
    path.write_text(json.dumps(feed))
    plan = php_json(tmp_path, "echo json_encode(dockyard_prepare_deploy(['slug'=>'review','confirm'=>true]));", index=clone / "mcp/index.php", env=env)
    assert plan["ready"] is False
    assert any("allow_privileged=true" in value for value in plan["blockers"])


def test_missing_parser_is_blocked(compose_fixture, tmp_path):
    clone, env = compose_fixture
    (clone / "stacks/review/docker-compose.yml").write_text("services: {app: {image: busybox}}")
    (clone / "mcp/vendor/autoload.php").unlink()
    plan = php_json(tmp_path, "echo json_encode(dockyard_prepare_deploy(['slug'=>'review','confirm'=>true,'allow_privileged'=>true]));", index=clone / "mcp/index.php", env=env)
    assert plan["ready"] is False
    assert any("parsera YAML" in message for message in plan["blockers"])


@pytest.mark.parametrize("own,requested,expected", [
    ("example/fixture", "example/fixture", True),
    ("example/fixture", "example/fixture/tree/main", True),
    ("example/fixture", "example/fixture/tree/dev", False),
    ("example/main", "example/HEAD", False),
    ("example/HEAD", "example/main", False),
])
def test_local_repository_matches_identity_and_ref(compose_fixture, tmp_path, own, requested, expected):
    clone, env = compose_fixture
    (clone / "repository.json").write_text(json.dumps({"url": "https://github.com/" + own}))
    local = php_json(tmp_path, "echo json_encode(dockyard_is_local_repository($argv[2], 'stacks/review/docker-compose.yml'));",
                     "https://github.com/" + requested, index=clone / "mcp/index.php", env=env)
    assert local is expected


def compose_command():
    standalone = REPO_ROOT / ".venv/docker-compose.exe"
    if standalone.is_file():
        return [str(standalone)]
    if shutil.which("docker-compose"):
        return [shutil.which("docker-compose")]
    if shutil.which("docker"):
        return [shutil.which("docker"), "compose"]
    return None


COMPOSE = compose_command()


@pytest.mark.skipif(PHP is None or COMPOSE is None, reason="PHP and Docker Compose config CLI required")
@pytest.mark.parametrize("value", ["abc$HOME", "${MY_REVIEW_VAR:-fallback}", "$$literal", r"\$HOME", "quotes ' and \"", r"C:\directory\file", "trailing\\", "line1\nline2", "line1\r\nline2", "a\tb", "", " spaces # comment ", "Zażółć", "\u00a0nonbreaking spaces\u00a0", "\u2002wide spaces\u2002"])
def test_dotenv_round_trip_through_real_compose(tmp_path, value):
    values = tmp_path / "values.json"
    values.write_text(json.dumps({"VALUE": value}), encoding="utf-8")
    encoded = php_json(tmp_path, "echo json_encode(dockyard_dotenv(json_decode(file_get_contents($argv[2]), true)));", values)
    (tmp_path / ".env").write_text(encoded, encoding="utf-8", newline="\n")
    compose = tmp_path / "compose.yml"
    compose.write_text('services:\n  app:\n    image: busybox:latest\n    environment:\n      VALUE: "${VALUE}"\n', encoding="utf-8")
    env = {"SystemRoot": os.environ.get("SystemRoot", ""), "MY_REVIEW_VAR": "SHOULD_NOT_REPLACE_THE_PASSWORD"}
    command = COMPOSE + ["--project-directory", str(tmp_path), "--env-file", str(tmp_path / ".env"), "-f", str(compose), "config"]
    result = subprocess.run(command + ["--format", "json"], capture_output=True, text=True, encoding="utf-8", env=env, timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
    # Compose escapes dollars in exported configuration so it can be loaded again.
    rendered = json.loads(result.stdout)["services"]["app"]["environment"]["VALUE"]
    assert rendered in (value, value.replace("$", "$$"))
    environment = subprocess.run(command + ["--environment"], capture_output=True, text=True, encoding="utf-8", env=env, timeout=20)
    assert environment.returncode == 0, environment.stderr
    # VALUE sorts last in this isolated environment. Check dotenv decoding directly,
    # independently of Compose's escaped JSON presentation. Text mode normalizes CRLF.
    decoded = environment.stdout.split("\nVALUE=", 1)[1] if "\nVALUE=" in environment.stdout else environment.stdout.removeprefix("VALUE=")
    assert decoded == value.replace("\r\n", "\n") + "\n"


def feed_named(name):
    return json.dumps({"version": "3", "templates": [{"id": 1, "type": 1, "name": name, "title": name, "image": "busybox", "categories": ["Other"]}]})


@pytest.fixture
def bare_upload(tmp_path):
    """Only mcp/ on the server and no configuration, the way a manual upload leaves it."""
    if PHP is None:
        pytest.skip("php is not on PATH")
    clone = tmp_path / "bare"
    (clone / "mcp").mkdir(parents=True)
    shutil.copyfile(REPO_ROOT / "mcp/index.php", clone / "mcp/index.php")
    env = os.environ.copy()
    env.pop("DOCKYARD_TEMPLATES_URL", None)
    env.pop("DOCKYARD_TEMPLATES", None)
    return clone, env


def seed_feed_cache(clone, url, body):
    cache = clone / "mcp/cache"
    cache.mkdir(exist_ok=True)
    (cache / f"feed-{hashlib.sha256(url.encode()).hexdigest()}.json").write_text(body, encoding="utf-8")


FIRST_FEED_NAME = "echo json_encode(json_decode(dockyard_templates_json(), true)['templates'][0]['name']);"


def test_unconfigured_server_reads_feed_from_official_cdn(bare_upload, tmp_path):
    clone, env = bare_upload
    seed_feed_cache(clone, OFFICIAL_FEED, feed_named("cdn-app"))

    assert php_json(tmp_path, FIRST_FEED_NAME, index=clone / "mcp/index.php", env=env) == "cdn-app"


def test_local_feed_variable_keeps_server_off_the_cdn(bare_upload, tmp_path):
    clone, env = bare_upload
    seed_feed_cache(clone, OFFICIAL_FEED, feed_named("cdn-app"))
    (tmp_path / "own.json").write_text(feed_named("local-app"), encoding="utf-8")
    env["DOCKYARD_TEMPLATES"] = str(tmp_path / "own.json")

    assert php_json(tmp_path, FIRST_FEED_NAME, index=clone / "mcp/index.php", env=env) == "local-app"


def test_unreachable_cdn_falls_back_to_feed_next_to_the_server(bare_upload, tmp_path):
    clone, env = bare_upload
    (clone / "templates.json").write_text(feed_named("local-app"), encoding="utf-8")

    asked, name = php_json(tmp_path, """
$asked = [];
$json = dockyard_templates_json(static function (string $url, int $max) use (&$asked): string {
    $asked[] = $url;
    throw new RuntimeException('offline');
});
echo json_encode([$asked, json_decode($json, true)['templates'][0]['name']]);
""", index=clone / "mcp/index.php", env=env)

    assert asked == [OFFICIAL_FEED]
    assert name == "local-app"


def http_get(port, path, headers=None, host=None):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    try:
        connection.putrequest("GET", path, skip_host=host is not None)
        if host is not None:
            connection.putheader("Host", host)
        for name, value in (headers or {}).items():
            connection.putheader(name, value)
        connection.endheaders()
        response = connection.getresponse()
        return response.status, {name.lower(): value for name, value in response.getheaders()}, response.read().decode("utf-8")
    finally:
        connection.close()


def test_browser_gets_setup_guide_for_the_address_it_opened(php_server):
    status, headers, body = http_get(php_server, "/mcp", BROWSER)

    assert status == 200
    assert headers["content-type"] == "text/html; charset=utf-8"
    assert '<html lang="en">' in body
    assert f"claude mcp add --scope user --transport http dockyard http://127.0.0.1:{php_server}/mcp\n" in body
    assert f"codex mcp add dockyard --url http://127.0.0.1:{php_server}/mcp\n" in body
    assert "YOUR-DOMAIN" not in body


@pytest.mark.parametrize("path,shown", [("/mcp/", "/mcp/"), ("/mcp/index.php", "/mcp/"), ("/mcp?lang=pl", "/mcp"), ("/", "/")])
def test_guide_shows_the_endpoint_without_file_name_or_query(php_server, path, shown):
    _, _, body = http_get(php_server, path, BROWSER)

    assert f"codex mcp add dockyard --url http://127.0.0.1:{php_server}{shown}\n" in body


@pytest.mark.parametrize("accept_language,path,expected", [
    ("pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7", "/mcp", "pl"),
    ("de-AT,de;q=0.9,en;q=0.8", "/mcp", "de"),
    ("fr", "/mcp", "fr"),
    ("es-ES,es;q=0.9", "/mcp", "en"),
    ("en;q=0.5,fr;q=0.9", "/mcp", "fr"),
    ("pl", "/mcp?lang=de", "de"),
    ("pl", "/mcp?lang=xx", "pl"),
    (None, "/mcp", "en"),
])
def test_guide_language_follows_query_then_browser(php_server, accept_language, path, expected):
    request = dict(BROWSER, **({"Accept-Language": accept_language} if accept_language else {}))

    _, headers, body = http_get(php_server, path, request)

    assert f'<html lang="{expected}">' in body
    assert headers["content-language"] == expected


def test_guide_links_to_every_language(php_server):
    _, _, body = http_get(php_server, "/mcp", BROWSER)

    for language in GUIDE_LANGUAGES:
        assert f'href="?lang={language}"' in body
    assert body.count('aria-current="true"') == 1


@pytest.mark.parametrize("headers", [{}, {"Accept": "text/event-stream"}, {"Accept": "*/*"}, {"Accept": "application/json"}])
def test_mcp_clients_get_405_on_get(php_server, headers):
    status, response_headers, body = http_get(php_server, "/mcp", headers)

    assert status == 405
    assert response_headers["content-type"] == "application/json; charset=utf-8"
    assert json.loads(body)["error"]["code"] == -32600


def test_guide_is_not_cached_and_runs_no_scripts(php_server):
    _, headers, body = http_get(php_server, "/mcp", BROWSER)

    assert headers["cache-control"] == "no-store"
    assert "accept" in headers["vary"].lower()
    assert "default-src 'none'" in headers["content-security-policy"]
    assert "<script" not in body


def test_guide_does_not_reflect_a_hostile_host_header(php_server):
    status, _, body = http_get(php_server, "/mcp", BROWSER, host='evil.example"><img src=x onerror=alert(1)>')

    assert status == 200
    assert "evil.example" not in body
    assert "https://YOUR-DOMAIN/mcp" in body


def test_guide_uses_https_behind_a_tls_proxy(php_server):
    _, _, body = http_get(php_server, "/mcp", dict(BROWSER, **{"X-Forwarded-Proto": "https"}), host="catalog.example")

    assert "codex mcp add dockyard --url https://catalog.example/mcp\n" in body


@pytest.mark.skipif(PHP is None, reason="php is not on PATH")
def test_guide_markdown_becomes_escaped_html(tmp_path):
    rendered = php_json(tmp_path, r"""
echo json_encode(dockyard_markdown_html("# Title <x>\n\nText with `a<b` and **My account → Tokens**,\nsecond line.\n\n## Part\n\n- one `1`\n- two\n\n```bash\necho \"<hi>\" && ls\n```\n"));
""")

    assert rendered == {
        "title": "Title <x>",
        "html": "<h1>Title &lt;x&gt;</h1>\n"
                "<p>Text with <code>a&lt;b</code> and <strong>My account → Tokens</strong>, second line.</p>\n"
                "<h2>Part</h2>\n"
                "<ul>\n<li>one <code>1</code></li>\n<li>two</li>\n</ul>\n"
                "<pre><code>echo &quot;&lt;hi&gt;&quot; &amp;&amp; ls\n</code></pre>\n",
    }


@pytest.mark.parametrize("language", GUIDE_LANGUAGES)
def test_guide_keeps_every_letter_of_the_translation(php_server, language):
    _, _, body = http_get(php_server, f"/mcp?lang={language}", BROWSER)

    # "ą" ends with byte 0x85, which a byte-wise line split takes for a line break.
    assert "�" not in body
    if language == "pl":
        assert "wdrożyć ją u Ciebie" in body


def test_server_without_guides_keeps_answering_405(bare_upload, tmp_path):
    clone, env = bare_upload

    assert php_json(tmp_path, "echo json_encode(dockyard_guide_page('en', 'https://catalog.example/mcp'));", index=clone / "mcp/index.php", env=env) is None


def test_missing_translation_falls_back_to_english(bare_upload, tmp_path):
    clone, env = bare_upload
    (clone / "mcp/guide").mkdir()
    shutil.copyfile(REPO_ROOT / "mcp/guide/en.md", clone / "mcp/guide/en.md")

    page = php_json(tmp_path, "echo json_encode(dockyard_guide_page('de', 'https://catalog.example/mcp'));", index=clone / "mcp/index.php", env=env)

    assert '<html lang="en">' in page


def guide_blocks(language, *kinds):
    text = (REPO_ROOT / "mcp/guide" / f"{language}.md").read_text(encoding="utf-8")
    return [body for kind, body in re.findall(r"^```(\w+)\n(.*?)^```$", text, flags=re.S | re.M) if kind in kinds]


@pytest.mark.parametrize("language", [language for language in GUIDE_LANGUAGES if language != "en"])
def test_translated_guides_keep_the_english_commands_and_sections(language):
    english = (REPO_ROOT / "mcp/guide/en.md").read_text(encoding="utf-8")
    translated = (REPO_ROOT / "mcp/guide" / f"{language}.md").read_text(encoding="utf-8")

    assert guide_blocks(language, "bash", "json", "toml") == guide_blocks("en", "bash", "json", "toml")
    assert len(guide_blocks(language, "text")) == len(guide_blocks("en", "text"))
    assert len(re.findall(r"^## ", translated, flags=re.M)) == len(re.findall(r"^## ", english, flags=re.M))


@pytest.mark.parametrize("language", GUIDE_LANGUAGES)
def test_every_guide_covers_the_popular_agents(language):
    commands = "\n".join(guide_blocks(language, "bash", "json", "toml"))

    for expected in ["claude mcp add", "codex mcp add", "grok mcp add", "gemini mcp add", '"mcp-remote"', '"httpUrl"', '"servers"', "[mcp_servers.dockyard]"]:
        assert expected in commands
    assert commands.count("https://YOUR-DOMAIN/mcp") >= 10
