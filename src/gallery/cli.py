"""Command-line entry point: `python -m gallery <command>`."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

import jsonschema
from jinja2 import TemplateError

from .build_templates import TemplateBuildError, build_templates
from .dockerhub import fetch_metadata, load_cache
from .config import repository_url
from .loader import load_apps
from .models import AppValidationError
from .security import is_valid_slug
from .publish import PublishError, publish_outputs
from .stack_pins import LOCK_PATH, pin_stacks, third_party_stackfiles
from .validate import load_schema, validate_stack_pins, validate_templates

REPO_ROOT = Path(__file__).resolve().parents[2]

NEW_APP_TEMPLATE = """\
name: {title}
slug: {slug}
category: Other
type: {type}                # container | compose
image: ""                   # e.g. namespace/repo:tag - required (also used for Docker Hub lookup)
{compose_line}description: null              # null = auto-fetch from Docker Hub, or set your own text
note: null                      # optional - Portainer deployment instructions (HTML supported)
logo: ""                    # required - URL to a logo image
website: null                # optional - project's own site or source repo
network: null                 # optional - container | Docker network to attach to, e.g. host or a compose-created network
command: null                 # optional - container | override the container's command
privileged: null              # optional - container | true to run in privileged mode
restart_policy: null          # optional, container only - always | unless-stopped | on-failure | "no"
ports: []                   # e.g. ["8080/tcp"]
volumes: []                 # e.g. [{{container: /data}}]
env: []                     # e.g. [{{name: PASSWORD, label: "Admin password"}}]
"""


def cmd_fetch_metadata(args: argparse.Namespace) -> int:
    apps = load_apps(REPO_ROOT)
    print(f"Fetching Docker Hub metadata for {len(apps)} apps...")
    fetch_metadata(REPO_ROOT, apps)
    print("Done.")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    repo_url = repository_url(REPO_ROOT, args.repo_url)
    apps = load_apps(REPO_ROOT)
    cache = load_cache(REPO_ROOT)
    templates = build_templates(apps, cache, repo_url=repo_url)
    jsonschema.validate(templates, load_schema(REPO_ROOT))
    from .build_site import build_site
    stage = Path(tempfile.mkdtemp(prefix=".gallery-build-", dir=REPO_ROOT)).resolve()
    preserve_stage = False
    try:
        (stage / "templates.json").write_text(json.dumps(templates, indent=2) + "\n", encoding="utf-8", newline="\n")
        (stage / "repository.json").write_text(json.dumps({"url": repo_url}, indent=2) + "\n", encoding="utf-8", newline="\n")
        build_site(REPO_ROOT, apps, cache, repo_url=repo_url, output_dir=stage / "docs")
        publish_outputs(REPO_ROOT, stage)
    except PublishError as exc:
        preserve_stage = exc.preserve_stage
        raise
    finally:
        if not preserve_stage and stage.parent == REPO_ROOT.resolve():
            shutil.rmtree(stage)
    print(f"Wrote {REPO_ROOT / 'templates.json'} ({len(templates['templates'])} templates)")
    print(f"Wrote site to {REPO_ROOT / 'docs'}")
    return 0


def cmd_pin_stacks(args: argparse.Namespace) -> int:
    apps = load_apps(REPO_ROOT)
    entries = [(app.repository["url"], app.repository["stackfile"]) for app in apps if app.repository]
    wanted = third_party_stackfiles(entries, repository_url(REPO_ROOT))
    print(f"Pinning {sum(len(group['stackfiles']) for group in wanted.values())} stackfiles from {len(wanted)} repositories...")
    pin_stacks(REPO_ROOT, wanted, update=args.update)
    print(f"Wrote {REPO_ROOT / LOCK_PATH}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    validate_templates(REPO_ROOT)
    validate_stack_pins(REPO_ROOT)
    print("templates.json is valid and every third-party stackfile is pinned.")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    if not is_valid_slug(args.slug):
        raise AppValidationError("slug must contain lowercase letters and numbers separated by hyphens")
    apps_dir = REPO_ROOT / "apps"
    apps_dir.mkdir(parents=True, exist_ok=True)
    out_path = apps_dir / f"{args.slug}.yaml"
    compose_line = ""
    if args.type == "compose":
        compose_line = f"compose: stacks/{args.slug}/docker-compose.yml\n"

    content = NEW_APP_TEMPLATE.format(
        title=args.slug.replace("-", " ").title(),
        slug=args.slug,
        type=args.type,
        compose_line=compose_line,
    )
    try:
        with out_path.open("x", encoding="utf-8", newline="\n") as f:
            f.write(content)
    except FileExistsError:
        print(f"ERROR: {out_path} already exists", file=sys.stderr)
        return 1
    print(f"Created {out_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gallery")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch-metadata", help="refresh Docker Hub metadata cache")
    p_fetch.set_defaults(func=cmd_fetch_metadata)

    p_build = sub.add_parser("build", help="build templates.json and the static site")
    p_build.add_argument("--repo-url", help="override repository.json URL for compose stack templates")
    p_build.set_defaults(func=cmd_build)

    p_validate = sub.add_parser("validate", help="validate templates.json against the Portainer v3 schema")
    p_validate.set_defaults(func=cmd_validate)

    p_pin = sub.add_parser("pin-stacks", help="pin third-party stackfiles to a commit and SHA-256 in stacks.lock.json")
    p_pin.add_argument("--update", action="store_true",
                       help="move every repository to its current head (review the stackfiles first)")
    p_pin.set_defaults(func=cmd_pin_stacks)

    p_new = sub.add_parser("new", help="scaffold a new app definition")
    p_new.add_argument("slug", help="app slug, e.g. 'my-app'")
    p_new.add_argument("--type", choices=["container", "compose"], default="container")
    p_new.set_defaults(func=cmd_new)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (AppValidationError, TemplateBuildError, OSError, ValueError, RuntimeError, TemplateError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except jsonschema.exceptions.ValidationError as exc:
        print(f"ERROR: templates.json failed schema validation: {exc.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
