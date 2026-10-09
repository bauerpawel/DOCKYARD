"""Shared repository identity for generated feeds and the PHP MCP server."""
import json
from pathlib import Path

from .security import is_web_url

CONFIG_NAME = "repository.json"
SOURCE_ROOT = Path(__file__).resolve().parents[2]


def repository_url(repo_root: Path, override: str | None = None) -> str:
    config = repo_root / CONFIG_NAME
    if override is None:
        if not config.is_file():
            config = SOURCE_ROOT / CONFIG_NAME
        try:
            override = json.loads(config.read_text(encoding="utf-8"))["url"]
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ValueError(f"{config}: expected a JSON object containing a repository URL") from error
    if not is_web_url(override):
        raise ValueError("repository URL must be an absolute HTTP(S) URL without credentials")
    if "/OWNER/REPO" in override.upper():
        raise ValueError("replace the OWNER/REPO placeholder with the real repository URL")
    return override.rstrip("/")
