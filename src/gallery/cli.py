"""Command-line entry point: `python -m gallery <command>`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import jsonschema

from .build_templates import DEFAULT_REPO_URL, TemplateBuildError, build_templates
from .dockerhub import fetch_metadata, load_cache
from .loader import load_apps
from .models import AppValidationError
from .validate import validate_templates

REPO_ROOT = Path(__file__).resolve().parents[2]

NEW_APP_TEMPLATE = """\
name: {title}
slug: {slug}
category: Uncategorized
type: {type}                # container | compose
image: ""                   # e.g. namespace/repo:tag - required (also used for Docker Hub lookup)
{compose_line}description: null              # null = auto-fetch from Docker Hub, or set your own text
logo: ""                    # required - URL to a logo image
website: null                # optional - project's own site or source repo
network: null                 # optional - container | Docker network to attach to, e.g. host or a compose-created network
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
    apps = load_apps(REPO_ROOT)
    cache = load_cache(REPO_ROOT)
    templates = build_templates(apps, cache, repo_url=args.repo_url)

    out_path = REPO_ROOT / "templates.json"
    with out_path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(templates, f, indent=2)
        f.write("\n")
    print(f"Wrote {out_path} ({len(templates['templates'])} templates)")

    if args.repo_url == DEFAULT_REPO_URL:
        print(
            "NOTE: using placeholder repository URL for compose stacks. "
            "Pass --repo-url once this repo is published on GitHub."
        )

    from .build_site import build_site

    build_site(REPO_ROOT, apps, cache, repo_url=args.repo_url)
    print(f"Wrote site to {REPO_ROOT / 'docs'}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    validate_templates(REPO_ROOT)
    print("templates.json is valid.")
    return 0


def cmd_new(args: argparse.Namespace) -> int:
    apps_dir = REPO_ROOT / "apps"
    apps_dir.mkdir(parents=True, exist_ok=True)
    out_path = apps_dir / f"{args.slug}.yaml"
    if out_path.exists():
        print(f"ERROR: {out_path} already exists", file=sys.stderr)
        return 1

    compose_line = ""
    if args.type == "compose":
        compose_line = f"compose: stacks/{args.slug}/docker-compose.yml\n"

    content = NEW_APP_TEMPLATE.format(
        title=args.slug.replace("-", " ").title(),
        slug=args.slug,
        type=args.type,
        compose_line=compose_line,
    )
    out_path.write_text(content, encoding="utf-8", newline="\n")
    print(f"Created {out_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gallery")
    sub = parser.add_subparsers(dest="command", required=True)

    p_fetch = sub.add_parser("fetch-metadata", help="refresh Docker Hub metadata cache")
    p_fetch.set_defaults(func=cmd_fetch_metadata)

    p_build = sub.add_parser("build", help="build templates.json and the static site")
    p_build.add_argument("--repo-url", default=DEFAULT_REPO_URL, help="GitHub repo URL used for compose stack templates")
    p_build.set_defaults(func=cmd_build)

    p_validate = sub.add_parser("validate", help="validate templates.json against the Portainer v3 schema")
    p_validate.set_defaults(func=cmd_validate)

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
    except (AppValidationError, TemplateBuildError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except jsonschema.exceptions.ValidationError as exc:
        print(f"ERROR: templates.json failed schema validation: {exc.message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
