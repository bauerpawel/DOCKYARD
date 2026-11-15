from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).resolve().parent.parent / ".github" / "workflows"


def _upload_steps():
    for workflow in sorted(WORKFLOWS.glob("*.yml")):
        jobs = yaml.safe_load(workflow.read_text(encoding="utf-8")).get("jobs") or {}
        for job_name, job in jobs.items():
            for step in job.get("steps") or []:
                if str(step.get("uses", "")).startswith("actions/upload-artifact@"):
                    yield pytest.param(step, id=f"{workflow.name}:{job_name}")


@pytest.mark.parametrize("step", list(_upload_steps()))
def test_site_artifacts_keep_hidden_files(step):
    # upload-artifact skips dot paths by default. Without docs/.well-known the publish job
    # deletes the MCP server card from main, and deploy/refresh.php refuses that release.
    paths = str(step["with"]["path"]).split()
    if "docs" not in paths:
        pytest.skip("this artifact does not carry the site")
    assert step["with"].get("include-hidden-files") is True
