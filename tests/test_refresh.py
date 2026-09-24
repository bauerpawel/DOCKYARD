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
}


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
    assert (dest / "mcp" / "apache.conf").read_text(encoding="utf-8") == "vhost"
    assert (dest / "mcp" / "cache" / "abc.body").read_text(encoding="utf-8") == "cached stack"
    assert (dest / ".refresh-sha").read_text(encoding="utf-8").strip() == SHA
    assert sorted(p.name for p in dest.iterdir()) == [".refresh-sha", ".refresh.lock", "html", "mcp", "stacks", "templates.json"]
    assert sorted(p.name for p in (dest / "mcp").iterdir()) == [".htaccess", "AGENT.md", "INSTRUKCJA.md", "apache.conf", "cache", "index.php"]


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
