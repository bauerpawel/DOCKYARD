import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
REQUIREMENTS = REPO_ROOT / "requirements"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# RequirementsLayers::REQUIREMENTS_TXT_REGEX in dependabot-core.
DEPENDABOT_MANIFEST_NAME = re.compile(r"(?:[-._]|^|/)requirements[^\s]*\.txt$", re.IGNORECASE)


def test_dependency_graph_reports_every_lock_file():
    # Dependabot's grapher skips a .txt without a manifest-like name or a same-named
    # .in. A skipped lock keeps its last graph snapshot and raises false alerts.
    for lock in REQUIREMENTS.glob("*.txt"):
        assert DEPENDABOT_MANIFEST_NAME.search(lock.name) or lock.with_suffix(".in").exists(), lock.name


def test_dev_lock_has_no_input_file():
    # A paired .in makes Dependabot recompile the lock from that file alone, which
    # drops everything that comes from pyproject.toml.
    assert not (REQUIREMENTS / "requirements-dev.in").exists()


def test_workflows_install_existing_lock_files():
    installed = {
        path
        for workflow in WORKFLOWS.glob("*.yml")
        for path in re.findall(r"-r (requirements/\S+)", workflow.read_text(encoding="utf-8"))
    }
    assert installed
    for path in installed:
        assert (REPO_ROOT / path).is_file(), path
