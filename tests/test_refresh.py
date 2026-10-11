"""deploy/refresh.php installs a main commit only when its archive is complete and unpacked cleanly."""

import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
REFRESH = REPO_ROOT / "deploy" / "refresh.php"
SHA = "1234567890abcdef1234567890abcdef12345678"

# Calls refresh_main() with a stand-in for GitHub: the commits API answers 304
# when If-None-Match carries the current commit (as the real API does), and
# codeload serves the given archive with the given status.
RUNNER = r"""<?php
require $argv[1];
[$dest, $sha, $zip, $log, $zipStatus] = array_slice($argv, 2);
exit(refresh_main($dest, static function (string $url, string $headers) use ($sha, $zip, $log, $zipStatus): array {
    file_put_contents($log, $url . "\n", FILE_APPEND);
    if (str_contains($url, 'api.github.com')) {
        return str_contains($headers, '"' . $sha . '"') ? [304, '', []] : [200, $sha, []];
    }
    return (int) $zipStatus === 200 ? [200, (string) file_get_contents($zip), []] : [(int) $zipStatus, '', []];
}));
"""

COMPLETE = {
    "docs/index.html": "new site",
    "templates.json": '{"version": "3", "templates": []}',
    "stacks/app/docker-compose.yml": "services: {}\n",
    "mcp/index.php": "<?php // new",
    "mcp/.htaccess": "new rules",
    "mcp/AGENT.md": "new agent",
    "mcp/INSTRUKCJA.md": "new guide",
    "mcp/guide/en.md": "# new guide",
    "repository.json": '{"url":"https://github.com/bauerpawel/DOCKYARD"}',
    "mcp/composer.json": (REPO_ROOT / "mcp/composer.json").read_text(encoding="utf-8"),
    "mcp/composer.lock": (REPO_ROOT / "mcp/composer.lock").read_text(encoding="utf-8"),
}
COMPLETE.update({str(path.relative_to(REPO_ROOT)).replace("\\", "/"): path.read_text(encoding="utf-8")
                 for path in (REPO_ROOT / "mcp/vendor").rglob("*") if path.is_file()})


def _php_command():
    php = shutil.which("php")
    if php is None:
        return None
    probe = [php, "-r", "exit(class_exists('ZipArchive') ? 0 : 1);"]
    if subprocess.run(probe, capture_output=True).returncode == 0:
        return [php]
    # Windows PHP without php.ini ships php_zip.dll but does not load it.
    ext = Path(php).resolve().parent / "ext"
    if (ext / "php_zip.dll").is_file():
        return [php, "-d", f"extension_dir={ext}", "-d", "extension=zip"]
    return None


PHP_COMMAND = _php_command()
pytestmark = pytest.mark.skipif(PHP_COMMAND is None, reason="php with the zip extension is not available")


def make_archive(path, entries):
    with zipfile.ZipFile(path, "w") as archive:
        for name, content in entries:
            archive.writestr(f"DOCKYARD-{SHA}/{name}", content)
    return path


def seed_live(dest):
    files = {
        "html/index.html": "old site",
        "templates.json": "old feed",
        "stacks/app/docker-compose.yml": "old stack",
        "mcp/index.php": "<?php // old",
        "mcp/apache.conf": "vhost",
        "mcp/cache/abc.body": "cached stack",
        "mcp/guide/xx.md": "stale guide",
    }
    for name, content in files.items():
        target = dest / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def run_refresh(tmp_path, archive, zip_status=200):
    runner = tmp_path / "runner.php"
    runner.write_text(RUNNER, encoding="utf-8")
    log = tmp_path / "requests.log"
    result = subprocess.run(
        PHP_COMMAND + [str(runner), str(REFRESH), str(tmp_path / "live"), SHA, str(archive), str(log), str(zip_status)],
        capture_output=True,
        text=True,
        check=False,
    )
    requests = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return result, requests


def downloads(requests):
    return [url for url in requests if "codeload.github.com" in url]


def test_complete_commit_is_installed(tmp_path):
    dest = tmp_path / "live"
    seed_live(dest)
    archive = make_archive(tmp_path / "src.zip", COMPLETE.items())

    result, _ = run_refresh(tmp_path, archive)

    assert result.returncode == 0, result.stdout + result.stderr
    assert (dest / "html" / "index.html").read_text(encoding="utf-8") == "new site"
    assert (dest / "templates.json").read_text(encoding="utf-8") == '{"version": "3", "templates": []}'
    assert (dest / "stacks" / "app" / "docker-compose.yml").read_text(encoding="utf-8") == "services: {}\n"
    assert (dest / "mcp" / "index.php").read_text(encoding="utf-8") == "<?php // new"
    assert (dest / "mcp" / "AGENT.md").read_text(encoding="utf-8") == "new agent"
    assert (dest / "mcp" / "guide" / "en.md").read_text(encoding="utf-8") == "# new guide"
    assert not (dest / "mcp" / "guide" / "xx.md").exists()
    assert (dest / "mcp" / "apache.conf").read_text(encoding="utf-8") == "vhost"
    assert (dest / "mcp" / "cache" / "abc.body").read_text(encoding="utf-8") == "cached stack"
    assert (dest / ".refresh-sha").read_text(encoding="utf-8").strip() == SHA
    assert sorted(p.name for p in dest.iterdir()) == [".refresh-sha", ".refresh.lock", "html", "mcp", "repository.json", "stacks", "templates.json"]
    assert sorted(p.name for p in (dest / "mcp").iterdir()) == [".htaccess", "AGENT.md", "INSTRUKCJA.md", "apache.conf", "cache", "composer.json", "composer.lock", "guide", "index.php", "vendor"]


def test_incomplete_commit_changes_nothing(tmp_path):
    dest = tmp_path / "live"
    seed_live(dest)
    without_mcp = [(name, body) for name, body in COMPLETE.items() if not name.startswith("mcp/")]
    archive = make_archive(tmp_path / "src.zip", without_mcp)

    result, _ = run_refresh(tmp_path, archive)

    assert result.returncode == 1
    assert "mcp/index.php" in result.stderr
    assert (dest / "html" / "index.html").read_text(encoding="utf-8") == "old site"
    assert (dest / "templates.json").read_text(encoding="utf-8") == "old feed"
    assert (dest / "stacks" / "app" / "docker-compose.yml").read_text(encoding="utf-8") == "old stack"
    assert not (dest / ".refresh-src").exists()


def test_commit_without_guides_changes_nothing(tmp_path):
    dest = tmp_path / "live"
    seed_live(dest)
    without_guides = [(name, body) for name, body in COMPLETE.items() if not name.startswith("mcp/guide/")]
    archive = make_archive(tmp_path / "src.zip", without_guides)

    result, _ = run_refresh(tmp_path, archive)

    assert result.returncode == 1
    assert "mcp/guide/" in result.stderr
    assert (dest / "mcp" / "index.php").read_text(encoding="utf-8") == "<?php // old"
    assert (dest / "mcp" / "guide" / "xx.md").read_text(encoding="utf-8") == "stale guide"


def test_incomplete_commit_is_not_downloaded_again(tmp_path):
    dest = tmp_path / "live"
    seed_live(dest)
    without_mcp = [(name, body) for name, body in COMPLETE.items() if not name.startswith("mcp/")]
    archive = make_archive(tmp_path / "src.zip", without_mcp)

    first, _ = run_refresh(tmp_path, archive)
    second, requests = run_refresh(tmp_path, archive)

    assert first.returncode == 1
    assert second.returncode == 0, second.stderr
    assert len(downloads(requests)) == 1


def test_failed_download_is_retried(tmp_path):
    dest = tmp_path / "live"
    seed_live(dest)
    archive = make_archive(tmp_path / "src.zip", COMPLETE.items())

    first, _ = run_refresh(tmp_path, archive, zip_status=500)
    second, requests = run_refresh(tmp_path, archive, zip_status=500)

    assert first.returncode == 1
    assert second.returncode == 1
    assert len(downloads(requests)) == 2
    assert (dest / "html" / "index.html").read_text(encoding="utf-8") == "old site"


def test_failed_extraction_changes_nothing(tmp_path):
    dest = tmp_path / "live"
    seed_live(dest)
    # "extra" is written as a file, so "extra/nested" cannot be unpacked after it.
    broken = list(COMPLETE.items()) + [("extra", "file"), ("extra/nested", "unreachable")]
    archive = make_archive(tmp_path / "src.zip", broken)

    result, _ = run_refresh(tmp_path, archive)

    assert result.returncode == 1
    assert (dest / "html" / "index.html").read_text(encoding="utf-8") == "old site"
    assert (dest / "templates.json").read_text(encoding="utf-8") == "old feed"
    assert not (dest / ".refresh-sha").exists()


def test_live_files_are_replaced_not_rewritten_in_place(tmp_path):
    # A file rewritten in place can be read half-written by a concurrent MCP
    # request; a file renamed over the old one is a new file (new inode).
    dest = tmp_path / "live"
    seed_live(dest)
    before = {name: (dest / name).stat().st_ino for name in ("templates.json", "mcp/index.php")}
    archive = make_archive(tmp_path / "src.zip", COMPLETE.items())

    result, _ = run_refresh(tmp_path, archive)

    assert result.returncode == 0, result.stdout + result.stderr
    for name, inode in before.items():
        assert (dest / name).stat().st_ino != inode, name


@pytest.mark.parametrize("name,content", [
    ("templates.json", "not JSON"),
    ("templates.json", '{"version":"2","templates":[]}'),
    ("docs/index.html", ""),
    ("mcp/index.php", "<?php function broken( {"),
    ("repository.json", '{"url":"https://github.com/OWNER/REPO"}'),
    ("mcp/vendor/symfony/yaml/Yaml.php", "<?php this is invalid PHP"),
    ("mcp/composer.lock", "invalid JSON"),
    ("mcp/vendor/composer/installed.json", '{"packages":[]}'),
])
def test_invalid_release_changes_nothing(tmp_path, name, content):
    dest = tmp_path / "live"
    seed_live(dest)
    archive = make_archive(tmp_path / "src.zip", (COMPLETE | {name: content}).items())
    result, _ = run_refresh(tmp_path, archive)
    assert result.returncode == 1
    assert (dest / "html/index.html").read_text() == "old site"
    assert (dest / "templates.json").read_text() == "old feed"
    assert (dest / "mcp/index.php").read_text() == "<?php // old"
    assert not (dest / ".refresh-sha").exists()


@pytest.mark.parametrize("fail_at", [2, 4, 7, 9, 13, 17])
def test_mid_publication_failure_restores_whole_release(tmp_path, fail_at):
    dest = tmp_path / "live"
    seed_live(dest)
    source = tmp_path / "source"
    for name, content in COMPLETE.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    runner = tmp_path / "rollback.php"
    runner.write_text("""<?php
require $argv[1];
$calls = 0;
try {
    refresh_install($argv[2], $argv[3], static function(string $source, string $target) use (&$calls, $argv): bool {
        $calls++;
        return $calls === (int) $argv[4] ? false : rename($source, $target);
    });
    exit(2);
} catch (RuntimeException $error) { echo $error->getMessage(); }
""", encoding="utf-8")
    result = subprocess.run(PHP_COMMAND + [str(runner), str(REFRESH), str(source), str(dest), str(fail_at)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "przywrócono" in result.stdout
    assert (dest / "html/index.html").read_text() == "old site"
    assert (dest / "templates.json").read_text() == "old feed"
    assert (dest / "stacks/app/docker-compose.yml").read_text() == "old stack"
    assert (dest / "mcp/index.php").read_text() == "<?php // old"
    assert (dest / "mcp/apache.conf").read_text() == "vhost"
    assert (dest / "mcp/cache/abc.body").read_text() == "cached stack"
    assert (dest / "mcp/guide/xx.md").read_text() == "stale guide"
    assert not (dest / "repository.json").exists()
    assert not list(dest.glob(".refresh-stage-*"))


def test_failed_rollback_keeps_old_release_backups(tmp_path):
    dest = tmp_path / "live"
    seed_live(dest)
    source = tmp_path / "source"
    for name, content in COMPLETE.items():
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    runner = tmp_path / "failed-rollback.php"
    runner.write_text("""<?php
require $argv[1];
$calls = 0;
try {
    refresh_install($argv[2], $argv[3], static function(string $source, string $target) use (&$calls): bool {
        $calls++;
        return in_array($calls, [4, 5], true) ? false : rename($source, $target);
    });
    exit(2);
} catch (RuntimeException $error) { echo $error->getMessage(); }
""", encoding="utf-8")
    result = subprocess.run(PHP_COMMAND + [str(runner), str(REFRESH), str(source), str(dest)], capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    stages = list(dest.glob(".refresh-stage-*"))
    assert len(stages) == 1
    assert str(stages[0]).replace("\\", "/") in result.stdout.replace("\\", "/")
    assert (stages[0] / "backup/templates.json").read_text() == "old feed"
    assert (stages[0] / "backup/html/index.html").read_text() == "old site"
