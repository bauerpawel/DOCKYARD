import hashlib
import json
from pathlib import Path

import pytest
import requests

from gallery.stack_pins import (
    STACK_MAX_BYTES,
    is_own_repository,
    load_lock,
    missing_pins,
    parse_github_repository,
    pin_stacks,
    third_party_stackfiles,
)
from gallery.validate import validate_stack_pins

REPO_ROOT = Path(__file__).resolve().parents[1]
OWN = "https://github.com/bauerpawel/DOCKYARD"
OLD = "a" * 40
NEW = "b" * 40


class FakeResponse:
    def __init__(self, status, body=b""):
        self.status_code = status
        self.content = body
        self.text = body.decode("utf-8")

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def iter_content(self, size):
        for start in range(0, len(self.content), size):
            yield self.content[start:start + size]

    def close(self):
        pass


class FakeGitHub:
    """Serves commit lookups and raw files from dicts and records every URL asked for."""

    def __init__(self, heads, files):
        self.heads = heads
        self.files = files
        self.asked = []

    def get(self, url, headers=None, timeout=None, stream=False):
        self.asked.append(url)
        if url.startswith("https://api.github.com/"):
            assert headers == {"Accept": "application/vnd.github.sha"}
            head = self.heads.get(url.split("/repos/", 1)[1])
            return FakeResponse(200, head.encode()) if head else FakeResponse(404)
        body = self.files.get(url.removeprefix("https://raw.githubusercontent.com/"))
        return FakeResponse(200, body) if body is not None else FakeResponse(404)


def wanted(*pairs):
    return third_party_stackfiles(pairs, OWN)


def sha(body):
    return hashlib.sha256(body).hexdigest()


@pytest.mark.parametrize("url,expected", [
    ("https://github.com/owner/repo", ("owner", "repo", None)),
    ("https://www.github.com/owner/repo.git/", ("owner", "repo", None)),
    ("https://github.com/owner/repo/tree/dev", ("owner", "repo", "dev")),
    ("http://github.com/owner/repo", None),
    ("https://user:token@github.com/owner/repo", None),
    ("https://gitlab.com/owner/repo", None),
    ("https://github.com/owner", None),
])
def test_parse_github_repository(url, expected):
    assert parse_github_repository(url) == expected


@pytest.mark.parametrize("url,own", [
    (OWN, True),
    (OWN + "/tree/main", True),
    (OWN + "/tree/HEAD", True),
    (OWN + "/tree/dev", False),
    ("https://github.com/bauerpawel/DOCKYARD-fork", False),
    ("https://github.com/someone/DOCKYARD", False),
])
def test_own_repository_matches_the_mcp_server(url, own):
    assert is_own_repository(url, OWN) is own


def test_third_party_stackfiles_skip_own_stacks_and_group_by_repository():
    groups = wanted((OWN, "stacks/app/docker-compose.yml"),
                    ("https://github.com/Owner/Repo", "a.yml"),
                    ("https://github.com/owner/repo", "dir\\b.yml"))
    assert list(groups) == ["owner/repo"]
    assert groups["owner/repo"]["stackfiles"] == {"a.yml", "dir/b.yml"}


def test_conflicting_refs_and_non_github_repositories_are_rejected():
    with pytest.raises(ValueError, match="different refs"):
        wanted(("https://github.com/o/r", "a.yml"), ("https://github.com/o/r/tree/dev", "b.yml"))
    with pytest.raises(ValueError, match="https://github.com/OWNER/REPO"):
        wanted(("https://gitlab.com/o/r", "a.yml"))


def test_new_stackfiles_are_pinned_to_the_resolved_commit(tmp_path):
    github = FakeGitHub({"o/r/commits/dev": OLD}, {f"o/r/{OLD}/a.yml": b"services: {}\n"})

    pin_stacks(tmp_path, wanted(("https://github.com/o/r/tree/dev", "a.yml")), session=github)

    assert load_lock(tmp_path) == {"version": 1, "repositories": {
        "o/r": {"commit": OLD, "stackfiles": {"a.yml": sha(b"services: {}\n")}}}}
    assert github.asked == ["https://api.github.com/repos/o/r/commits/dev",
                            f"https://raw.githubusercontent.com/o/r/{OLD}/a.yml"]


def test_existing_pins_stay_on_the_reviewed_commit(tmp_path):
    github = FakeGitHub({"o/r/commits/HEAD": OLD}, {f"o/r/{OLD}/a.yml": b"a", f"o/r/{OLD}/b.yml": b"b"})
    pin_stacks(tmp_path, wanted(("https://github.com/o/r", "a.yml")), session=github)
    github.heads["o/r/commits/HEAD"] = NEW
    github.asked.clear()

    pin_stacks(tmp_path, wanted(("https://github.com/o/r", "a.yml"), ("https://github.com/o/r", "b.yml")), session=github)

    assert load_lock(tmp_path)["repositories"]["o/r"] == {"commit": OLD, "stackfiles": {"a.yml": sha(b"a"), "b.yml": sha(b"b")}}
    assert github.asked == [f"https://raw.githubusercontent.com/o/r/{OLD}/b.yml"]


def test_update_moves_to_the_current_head_and_rehashes(tmp_path):
    github = FakeGitHub({"o/r/commits/HEAD": OLD}, {f"o/r/{OLD}/a.yml": b"old", f"o/r/{NEW}/a.yml": b"new"})
    pin_stacks(tmp_path, wanted(("https://github.com/o/r", "a.yml")), session=github)
    github.heads["o/r/commits/HEAD"] = NEW

    pin_stacks(tmp_path, wanted(("https://github.com/o/r", "a.yml")), update=True, session=github)

    assert load_lock(tmp_path)["repositories"]["o/r"] == {"commit": NEW, "stackfiles": {"a.yml": sha(b"new")}}


def test_pins_nothing_refers_to_are_dropped(tmp_path):
    github = FakeGitHub({"o/r/commits/HEAD": OLD, "x/y/commits/HEAD": OLD},
                        {f"o/r/{OLD}/a.yml": b"a", f"o/r/{OLD}/b.yml": b"b", f"x/y/{OLD}/c.yml": b"c"})
    pin_stacks(tmp_path, wanted(("https://github.com/o/r", "a.yml"), ("https://github.com/o/r", "b.yml"),
                                ("https://github.com/x/y", "c.yml")), session=github)

    pin_stacks(tmp_path, wanted(("https://github.com/o/r", "a.yml")), session=github)

    assert load_lock(tmp_path)["repositories"] == {"o/r": {"commit": OLD, "stackfiles": {"a.yml": sha(b"a")}}}


def test_missing_upstream_file_is_reported_and_the_rest_is_pinned(tmp_path):
    github = FakeGitHub({"o/r/commits/HEAD": OLD}, {f"o/r/{OLD}/a.yml": b"a"})

    with pytest.raises(RuntimeError, match="o/r: gone.yml: 404"):
        pin_stacks(tmp_path, wanted(("https://github.com/o/r", "a.yml"), ("https://github.com/o/r", "gone.yml")), session=github)

    assert load_lock(tmp_path)["repositories"] == {"o/r": {"commit": OLD, "stackfiles": {"a.yml": sha(b"a")}}}


def test_unresolvable_commit_keeps_the_old_pins(tmp_path):
    github = FakeGitHub({"o/r/commits/HEAD": OLD}, {f"o/r/{OLD}/a.yml": b"a"})
    pin_stacks(tmp_path, wanted(("https://github.com/o/r", "a.yml")), session=github)
    github.heads.clear()

    with pytest.raises(RuntimeError, match="o/r: 404"):
        pin_stacks(tmp_path, wanted(("https://github.com/o/r", "a.yml")), update=True, session=github)

    assert load_lock(tmp_path)["repositories"] == {"o/r": {"commit": OLD, "stackfiles": {"a.yml": sha(b"a")}}}


def test_oversized_stackfile_is_not_pinned(tmp_path):
    github = FakeGitHub({"o/r/commits/HEAD": OLD}, {f"o/r/{OLD}/big.yml": b"x" * (STACK_MAX_BYTES + 1)})

    with pytest.raises(RuntimeError, match="larger than"):
        pin_stacks(tmp_path, wanted(("https://github.com/o/r", "big.yml")), session=github)

    assert load_lock(tmp_path)["repositories"] == {"o/r": {"commit": OLD, "stackfiles": {}}}


@pytest.mark.parametrize("pinned", [
    {},
    {"o/r": {"commit": "main", "stackfiles": {"a.yml": "0" * 64}}},
    {"o/r": {"commit": OLD, "stackfiles": {"a.yml": "not-a-digest"}}},
    {"o/r": {"commit": OLD, "stackfiles": {"other.yml": "0" * 64}}},
])
def test_malformed_or_missing_pins_are_reported(pinned):
    assert missing_pins({"repositories": pinned}, wanted(("https://github.com/o/r", "a.yml"))) == ["o/r: a.yml"]


def write_feed(root, *repositories):
    templates = [{"id": index, "type": 3, "repository": {"url": url, "stackfile": stackfile}}
                 for index, (url, stackfile) in enumerate(repositories, 1)]
    (root / "templates.json").write_text(json.dumps({"version": "3", "templates": templates}), encoding="utf-8")
    (root / "repository.json").write_text(json.dumps({"url": OWN}), encoding="utf-8")


def test_validate_requires_a_pin_for_every_third_party_stackfile(tmp_path):
    write_feed(tmp_path, (OWN, "stacks/app/docker-compose.yml"), ("https://github.com/o/r", "a.yml"))

    with pytest.raises(ValueError, match="o/r: a.yml"):
        validate_stack_pins(tmp_path)

    (tmp_path / "stacks.lock.json").write_text(json.dumps({"version": 1, "repositories": {
        "o/r": {"commit": OLD, "stackfiles": {"a.yml": "0" * 64}}}}), encoding="utf-8")
    validate_stack_pins(tmp_path)


def test_committed_feed_has_every_third_party_stackfile_pinned():
    validate_stack_pins(REPO_ROOT)
