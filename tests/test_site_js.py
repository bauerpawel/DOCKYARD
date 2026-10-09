from pathlib import Path
import shutil
import subprocess

import pytest

NODE = shutil.which("node")


@pytest.mark.skipif(NODE is None, reason="Node.js required for JavaScript behavior tests")
def test_copy_button_behavior():
    suite = Path(__file__).with_name("copy.test.cjs")
    result = subprocess.run([NODE, "--test", str(suite)], capture_output=True, text=True, encoding="utf-8", timeout=20)
    assert result.returncode == 0, result.stdout + result.stderr
