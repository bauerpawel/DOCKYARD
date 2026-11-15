import re
from pathlib import Path

import pytest

HTACCESS = Path(__file__).resolve().parent.parent / "deploy" / "public_html.htaccess"
RULE = re.compile(r"^RewriteRule\s+(\S+)\s+(\S+)(?:\s+\[([^\]]*)\])?\s*$")


def _rules() -> list[tuple[re.Pattern, str]]:
    rules = []
    for line in HTACCESS.read_text(encoding="utf-8").splitlines():
        if line.startswith("RewriteRule"):
            match = RULE.match(line)
            assert match, line
            assert "END" in (match.group(3) or "").split(","), f"every rule must stop processing: {line}"
            rules.append((re.compile(match.group(1)), match.group(2)))
    return rules


def _route(path: str) -> str:
    """What Apache serves for a request path, relative to public_html. Every rule here ends with [END]."""
    for pattern, target in _rules():
        match = pattern.search(path)
        if match:
            return path if target == "-" else re.sub(r"\$(\d)", lambda ref: match.group(int(ref.group(1))), target)
    return path


@pytest.mark.parametrize(("path", "served"), [
    ("", "html/"),
    ("apps/plex/", "html/apps/plex/"),
    ("llms.txt", "html/llms.txt"),
    (".well-known/mcp/server-card.json", "html/.well-known/mcp/server-card.json"),
    (".well-known/acme-challenge/token", ".well-known/acme-challenge/token"),
    ("mcp", "mcp"),
    ("mcp/", "mcp/"),
    ("mcpx", "html/mcpx"),
    ("templates.json", "templates.json"),
    (".refresh-sha", "html/.refresh-sha"),
    ("stacks/plane/docker-compose.yml", "html/stacks/plane/docker-compose.yml"),
])
def test_public_html_routes(path, served):
    # The MCP card rule must come before the rule that keeps .well-known out of html/,
    # or the card published in llms.txt answers 404 (2026-11-15).
    assert _route(path) == served
