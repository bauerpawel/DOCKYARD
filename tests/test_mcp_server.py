"""The Dockyard MCP script answers catalog and deploy-plan checks without Apache."""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
PHP = shutil.which("php")


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
