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
    # Host paths outside the project and data directories, whatever the spelling.
    "services: {app: {image: busybox, volumes: ['../../../../../../../../..:/host:ro']}}",
    "services: {app: {image: busybox, volumes: [{type: bind, source: ../../.., target: /host}]}}",
    "services: {app: {image: busybox, volumes: ['~/.ssh:/keys:ro']}}",
    "services: {app: {image: busybox, volumes: ['/etc/cron.d:/cron']}}",
    "services: {app: {image: busybox, volumes: ['/root:/root']}}",
    "services: {app: {image: busybox, volumes: ['/portainer/../etc:/host-etc']}}",
    "services: {app: {image: busybox, volumes: ['/run/containerd/containerd.sock:/socket']}}",
    "services: {app: {image: busybox, volumes: ['/etc/localtime:/etc/localtime']}}",
    "services: {app: {image: busybox, volumes: ['/mnt/share:/share:rshared']}}",
    "services: {app: {image: busybox, volumes: [{type: bind, source: /mnt/share, target: /share, bind: {propagation: shared}}]}}",
    "services: {app: {image: busybox, volumes: [{type: npipe, source: pipe, target: /pipe}]}}",
    # Keys that reach the host, another container, or the deploying machine without a host path.
    "services: {app: {image: busybox, volumes_from: ['container:portainer']}}",
    "services: {app: {image: busybox, secrets: [s]}}\nsecrets: {s: {file: /etc/shadow}}",
    "services: {app: {image: busybox, configs: [c]}}\nconfigs: {c: {file: ../../etc/hostname}}",
    "services: {app: {image: busybox, secrets: [s]}}\nsecrets: {s: {environment: PORTAINER_API_KEY}}",
    "services: {app: {image: busybox}}\nnetworks: {default: {name: host, external: true}}",
    "services: {app: {image: busybox, volumes: ['pd:/data']}}\nvolumes: {pd: {external: true, name: portainer_data}}",
    "services: {app: {image: busybox, build: {context: ., ssh: [default]}}}",
    "services: {app: {image: busybox, security_opt: ['seccomp:unconfined']}}",
    "services: {app: {image: busybox, network_mode: 'container:portainer'}}",
    "services: {app: {image: busybox, cgroup: host}}",
    "services: {app: {image: busybox, env_file: [/etc/shadow]}}",
    "services: {app: {image: busybox, deploy: {resources: {reservations: {devices: [{capabilities: [gpu]}]}}}}}",
    # Keys the server does not know are not assumed safe.
    "services: {app: {image: busybox, use_api_socket: true}}",
    "models: {llm: {model: ai/smollm2}}\nservices: {app: {image: busybox}}",
    # Line breaks that Symfony YAML reads as text but Compose's YAML reads as a new line.
    "services:\n  app:\n    image: busybox\n    # note\u2028    privileged: true\n",
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
    command: 'echo privileged: true /var/run/docker.sock $$PORTAINER_API_KEY $$HOME'
    volumes: ['data:/data', './data:/config', '.:/project', {target: /anonymous}, '/cache',
              '/portainer/Files/AppData/app:/app', '/srv/media:/media:ro', '/etc/localtime:/etc/localtime:ro',
              {type: bind, source: /mnt/share, target: /share, read_only: true}]
    security_opt: ['no-new-privileges:true']
    env_file: [./app.env, {path: /portainer/Files/AppData/app/extra.env, required: false}]
    x-note: anything
  db:
    image: busybox
    network_mode: 'service:app'
    volumes_from: ['app:ro']
    ipc: shareable
    deploy: {resources: {limits: {memory: 256M}}}
volumes: {data: {driver: local}}
networks: {backend: {driver: bridge, ipam: {config: [{subnet: 10.10.0.0/24}]}}}
configs: {conf: {content: 'a: b'}}
x-defaults: {}
version: '3.8'
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


@pytest.mark.parametrize("compose", [
    "services: {app: {image: busybox, environment: {LEAK: '${PORTAINER_API_KEY}'}}}",
    # A YAML escape hides the dollar sign from the raw text; Compose still substitutes it.
    'services: {app: {image: busybox, environment: {LEAK: "\\x24{PORTAINER_URL}"}}}',
    "services: {app: {image: busybox, command: 'echo $PORTAINER_ENDPOINT_ID'}}",
])
def test_compose_reading_portainer_credentials_is_blocked_even_with_approval(compose_fixture, tmp_path, compose):
    clone, env = compose_fixture
    (clone / "stacks/review/docker-compose.yml").write_text(compose, encoding="utf-8")
    plan = php_json(tmp_path, "echo json_encode(dockyard_prepare_deploy(['slug'=>'review','confirm'=>true,'allow_privileged'=>true]));", index=clone / "mcp/index.php", env=env)
    assert plan["ready"] is False
    assert any("PORTAINER_" in reason for reason in plan["blockers"])


def test_yaml_alias_bomb_is_blocked_quickly(compose_fixture, tmp_path):
    clone, env = compose_fixture
    # 80 aliases expand to 2**40 values; the parser only limits the number of aliases.
    levels = ["x-l0: &l0 [a]"] + [f"x-l{i}: &l{i} [*l{i - 1}, *l{i - 1}]" for i in range(1, 41)]
    (clone / "stacks/review/docker-compose.yml").write_text(
        "\n".join(levels) + "\nservices: {app: {image: busybox, security_opt: [*l40]}}\n", encoding="utf-8")
    started = time.monotonic()
    plan = php_json(tmp_path, "echo json_encode(dockyard_prepare_deploy(['slug'=>'review','confirm'=>true,'allow_privileged'=>true]));", index=clone / "mcp/index.php", env=env)
    assert time.monotonic() - started < 10
    assert plan["ready"] is False
    assert any("kotwic YAML" in reason for reason in plan["blockers"])


def test_container_values_cannot_break_out_of_their_yaml_line(compose_fixture, tmp_path):
    clone, env = compose_fixture
    path = clone / "templates.json"
    feed = json.loads(path.read_text())
    feed["templates"][0] = {"id": 1, "name": "review", "title": "Review privileged: true", "type": 1, "categories": ["Other"],
                            "image": "busybox     privileged: true", "command": "echo a\u0085b c"}
    path.write_text(json.dumps(feed))
    plan = php_json(tmp_path, "echo json_encode(dockyard_prepare_deploy(['slug'=>'review','confirm'=>true]));", index=clone / "mcp/index.php", env=env)
    compose = plan["docker"]["compose"]
    assert not any(separator in compose for separator in "\u0085  ")
    service = yaml.safe_load(compose)["services"]["review"]
    assert service["image"] == "busybox     privileged: true"
    assert "privileged" not in service
    assert plan["ready"] is True


def test_container_env_named_like_portainer_credentials_is_blocked(compose_fixture, tmp_path):
    clone, env = compose_fixture
    path = clone / "templates.json"
    feed = json.loads(path.read_text())
    feed["templates"][0] = {"id": 1, "name": "review", "title": "Review", "type": 1, "image": "busybox:latest", "categories": ["Other"],
                            "env": [{"name": "PORTAINER_API_KEY", "label": "API key"}]}
    path.write_text(json.dumps(feed))
    plan = php_json(tmp_path, "echo json_encode(dockyard_prepare_deploy(['slug'=>'review','confirm'=>true,'allow_privileged'=>true,'local_secrets'=>['PORTAINER_API_KEY']]));", index=clone / "mcp/index.php", env=env)
    assert plan["ready"] is False
    assert any("PORTAINER_API_KEY" in reason for reason in plan["blockers"])


def test_compose_variables_outside_the_plan_need_a_value_or_approval(compose_fixture, tmp_path):
    clone, env = compose_fixture
    (clone / "stacks/review/docker-compose.yml").write_text(
        "services: {app: {image: busybox, environment: {KEY: '${OPENAI_API_KEY:-}', DB: '${DB_PASSWORD}'}}}", encoding="utf-8")
    unset, local = php_json(tmp_path, """
echo json_encode([
    dockyard_prepare_deploy(['slug' => 'review', 'confirm' => true]),
    dockyard_prepare_deploy(['slug' => 'review', 'confirm' => true, 'local_secrets' => ['OPENAI_API_KEY', 'DB_PASSWORD']]),
]);
""", index=clone / "mcp/index.php", env=env)
    assert unset["ready"] is False
    assert any("OPENAI_API_KEY, DB_PASSWORD" in warning for warning in unset["warnings"])
    assert any("allow_privileged=true" in reason for reason in unset["blockers"])
    assert local["ready"] is True
    assert local["warnings"] == []
    assert local["secrets_to_set"] == ["OPENAI_API_KEY", "DB_PASSWORD"]
    assert local["docker"]["env_file"] == 'OPENAI_API_KEY="CHANGEME"\nDB_PASSWORD="CHANGEME"\n'


@pytest.mark.skipif(PHP is None, reason="php is not on PATH")
def test_oversized_or_malformed_arguments_stay_cheap_and_quiet(tmp_path):
    warnings, slug, listed, empty, project, env_file, method = php_json(tmp_path, """
$warnings = 0;
set_error_handler(static function () use (&$warnings): bool { $warnings++; return true; });
// Eight distinct terms that all match n8n; the ninth would match nothing and is past the limit.
$capped = dockyard_list_apps(['query' => 'n8n n 8 n8 workflow automation postgresql owner zzz-not-in-catalog']);
$long = dockyard_list_apps(['query' => trim(str_repeat('a ', 32000))]);
$arrays = dockyard_list_apps(['query' => ['x'], 'category' => ['y'], 'kind' => ['z']]);
$plan = dockyard_prepare_deploy(['slug' => 'adguard', 'name' => [], 'data_dir' => [], 'local_secrets' => 'x',
    'env' => array_merge(array_fill(0, 500, ['name' => [], 'value' => []]), [['name' => 'TZ', 'value' => []], ['name' => 'TZ', 'value' => 'Europe/Warsaw']])]);
$rpc = dockyard_dispatch(['jsonrpc' => '2.0', 'id' => 1, 'method' => ['tools/list']]);
echo json_encode([$warnings, $capped['apps'][0]['slug'] ?? null, $long['total'], $arrays['total'], $plan['project'],
    $plan['docker']['env_file'], $rpc['error']['code'] ?? null]);
""")
    assert warnings == 0
    assert slug == "n8n"
    assert listed > 0 and empty > 0
    assert project == "adguard"
    assert "TZ=Europe/Warsaw\n" in env_file
    assert method == -32601


PIN_COMMIT ="0123456789abcdef0123456789abcdef01234567"
# argv: 2 repository URL, 3 stackfile, 4 lock JSON file, 5 file the fake download returns.
LOAD_PINNED = """
$asked = [];
try {
    $body = dockyard_load_stack(['repository' => ['url' => $argv[2], 'stackfile' => $argv[3]]],
        static function (string $url) use (&$asked, $argv): string { $asked[] = $url; return file_get_contents($argv[5]); },
        json_decode(file_get_contents($argv[4]), true));
    echo json_encode([$asked, $body, null]);
} catch (RuntimeException $error) {
    echo json_encode([$asked, null, $error->getMessage()]);
}
"""


def load_pinned(tmp_path, repository, stackfile, pins, served):
    (tmp_path / "lock.json").write_text(json.dumps(pins), encoding="utf-8")
    (tmp_path / "served.yml").write_bytes(served.encode("utf-8"))
    return php_json(tmp_path, LOAD_PINNED, repository, stackfile, tmp_path / "lock.json", tmp_path / "served.yml")


def pin(key, stackfile, body):
    return {key: {"commit": PIN_COMMIT, "stackfiles": {stackfile: hashlib.sha256(body.encode("utf-8")).hexdigest()}}}


@pytest.mark.skipif(PHP is None, reason="php is not on PATH")
@pytest.mark.parametrize("repository,key,path", [
    ("https://github.com/unrelated/project", "unrelated/project", "unrelated/project"),
    ("https://github.com/bauerpawel/DOCKYARD/tree/dev", "bauerpawel/dockyard", "bauerpawel/DOCKYARD"),
])
def test_repository_collision_fetches_declared_source(tmp_path, repository, key, path):
    body = "services: {app: {image: busybox}}\n"
    asked, loaded, error = load_pinned(tmp_path, repository, "stacks/n8n/docker-compose.yml",
                                       pin(key, "stacks/n8n/docker-compose.yml", body), body)
    assert error is None
    assert asked == [f"https://raw.githubusercontent.com/{path}/{PIN_COMMIT}/stacks/n8n/docker-compose.yml"]
    assert loaded == body


@pytest.mark.skipif(PHP is None, reason="php is not on PATH")
def test_unpinned_third_party_stack_is_never_fetched(tmp_path):
    asked, loaded, error = load_pinned(tmp_path, "https://github.com/unrelated/project", "stack.yml",
                                       pin("unrelated/project", "other.yml", "services: {}"), "services: {}")
    assert asked == [] and loaded is None
    assert "stacks.lock.json" in error


@pytest.mark.skipif(PHP is None, reason="php is not on PATH")
def test_changed_upstream_stack_is_refused(tmp_path):
    reviewed = "services: {app: {image: busybox}}\n"
    changed = "services: {app: {image: busybox, privileged: true}}\n"
    asked, loaded, error = load_pinned(tmp_path, "https://github.com/Unrelated/Project", "stack.yml",
                                       pin("unrelated/project", "stack.yml", reviewed), changed)
    assert asked == [f"https://raw.githubusercontent.com/Unrelated/Project/{PIN_COMMIT}/stack.yml"]
    assert loaded is None
    assert "SHA-256" in error


def test_prepare_deploy_serves_only_the_pinned_third_party_stack(compose_fixture, tmp_path):
    clone, env = compose_fixture
    feed = json.loads((clone / "templates.json").read_text())
    feed["templates"][0]["repository"] = {"url": "https://github.com/example/upstream", "stackfile": "stack.yml"}
    (clone / "templates.json").write_text(json.dumps(feed))
    reviewed = "services:\n  app:\n    image: busybox\n"
    (clone / "stacks.lock.json").write_text(json.dumps({"version": 1, "repositories": pin("example/upstream", "stack.yml", reviewed)}))
    url = f"https://raw.githubusercontent.com/example/upstream/{PIN_COMMIT}/stack.yml"
    cached = clone / "mcp/cache" / f"{hashlib.sha256(url.encode()).hexdigest()}.body"
    cached.parent.mkdir()
    deploy = "echo json_encode(dockyard_prepare_deploy(['slug'=>'review','confirm'=>true]));"

    cached.write_bytes(reviewed.encode())
    plan = php_json(tmp_path, deploy, index=clone / "mcp/index.php", env=env)
    assert plan["ready"] is True
    assert plan["portainer"]["body"]["stackFileContent"] == reviewed

    cached.write_bytes((reviewed + "    privileged: false\n").encode())
    changed = php_json(tmp_path, deploy, index=clone / "mcp/index.php", env=env)
    assert changed["ready"] is False
    assert any("SHA-256" in reason for reason in changed["blockers"])


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


def test_generated_container_compose_mounts_host_time_files_read_only(compose_fixture, tmp_path):
    clone, env = compose_fixture
    path = clone / "templates.json"
    feed = json.loads(path.read_text())
    feed["templates"][0] = {"id": 1, "name": "review", "title": "Review", "type": 1, "image": "busybox:latest", "categories": ["Other"],
                            "volumes": [{"bind": "/etc/localtime", "container": "/etc/localtime"}, {"bind": "/srv/review", "container": "/data"}]}
    path.write_text(json.dumps(feed))
    plan = php_json(tmp_path, "echo json_encode(dockyard_prepare_deploy(['slug'=>'review','confirm'=>true]));", index=clone / "mcp/index.php", env=env)
    assert plan["ready"] is True
    assert plan["warnings"] == []
    assert "/etc/localtime:/etc/localtime:ro" in plan["docker"]["compose"]
    assert "/srv/review:/data\n" in plan["docker"]["compose"].replace('"', "")


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


@pytest.mark.parametrize("note,expected", [
    (None, None),
    ("  ", None),
    ("<p>Set <strong>APP_KEY</strong> &amp; keep it.</p><p>Then sign in.<br>Read the guide.</p>",
     "Set APP_KEY & keep it.\nThen sign in.\nRead the guide."),
])
def test_app_and_deploy_plan_return_plain_text_setup_notes(compose_fixture, tmp_path, note, expected):
    clone, env = compose_fixture
    path = clone / "templates.json"
    feed = json.loads(path.read_text())
    feed["templates"][0] = {"id": 1, "name": "review", "title": "Review", "type": 1,
                            "description": "Application purpose", "image": "busybox:latest", "note": note}
    path.write_text(json.dumps(feed))
    app, plan = php_json(tmp_path, """
echo json_encode([dockyard_get_app(['slug'=>'review']),
                  dockyard_prepare_deploy(['slug'=>'review','confirm'=>true])]);
""", index=clone / "mcp/index.php", env=env)
    assert app["note"] == expected
    assert plan["note"] == expected
    assert plan["description"] == app["description"] == "Application purpose"


def test_port_metadata_resolves_overrides_and_ignores_unpublished_urls(compose_fixture, tmp_path):
    clone, env = compose_fixture
    (clone / "stacks/review/docker-compose.yml").write_text('''services:
  app:
    image: busybox:latest
    ports:
      - "127.0.0.1:${WEB_PORT:-8080}:3000"
      - target: 3478
        published: "${STUN_PORT:-3478}"
        protocol: udp
    environment:
      INTERNAL_URL: http://database:8090
  database:
    image: busybox:latest
    expose: [8090]
''')
    plan = php_json(tmp_path, """
echo json_encode(dockyard_prepare_deploy(['slug'=>'review','confirm'=>true,
    'env'=>['WEB_PORT'=>'18080','STUN_PORT'=>'13478']]));
""", index=clone / "mcp/index.php", env=env)
    assert plan["ready"] is True
    assert plan["published_ports"] == ["127.0.0.1:18080:3000/tcp", "13478:3478/udp"]
    assert plan["suggested_url"] == "http://localhost:18080"


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


OFFICIAL_PINS = "https://cdn.jsdelivr.net/gh/bauerpawel/DOCKYARD@main/stacks.lock.json"


def pins_named(key):
    return json.dumps({"version": 1, "repositories": {key: {}}})


def test_stack_pins_come_from_the_cdn_next_to_the_feed(bare_upload, tmp_path):
    clone, env = bare_upload
    seed_feed_cache(clone, OFFICIAL_PINS, pins_named("cdn/pins"))
    (clone / "templates.json").write_text(feed_named("local-app"), encoding="utf-8")
    (clone / "stacks.lock.json").write_text(pins_named("local/pins"), encoding="utf-8")

    assert php_json(tmp_path, "echo json_encode(array_keys(dockyard_stack_lock()));", index=clone / "mcp/index.php", env=env) == ["cdn/pins"]


def test_unreachable_cdn_falls_back_to_pins_next_to_the_feed(bare_upload, tmp_path):
    clone, env = bare_upload
    (clone / "templates.json").write_text(feed_named("local-app"), encoding="utf-8")
    (clone / "stacks.lock.json").write_text(pins_named("local/pins"), encoding="utf-8")

    asked, keys = php_json(tmp_path, """
$asked = [];
$lock = dockyard_stack_lock(static function (string $url, int $max) use (&$asked): string {
    $asked[] = $url;
    throw new RuntimeException('offline');
});
echo json_encode([$asked, array_keys($lock)]);
""", index=clone / "mcp/index.php", env=env)

    assert asked == [OFFICIAL_PINS]
    assert keys == ["local/pins"]


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
