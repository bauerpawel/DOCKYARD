<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/static/dockyard-logo.svg">
    <img src="docs/static/dockyard-logo-light.svg" alt="Dockyard" width="360">
  </picture>
</p>

<p align="center">
A set of 600+ <a href="https://www.portainer.io/">Portainer</a> app templates (v3 format), plus a browsable static website ("Dockyard") for finding them.
</p>

Everything is generated from a single source of truth — one YAML file per app in [`apps/`](apps/) — by a small Python CLI. That CLI produces two things:

1. **`templates.json`** — paste its raw URL into Portainer's *Settings → App Templates → URL* to get one-click deploys for every app in the gallery.
2. **`docs/`** — the Dockyard website: cards with logo, description, category and links, searchable and filterable.

## Using the feed in Portainer

1. Open Portainer and go to **Settings → App Templates**.
2. Paste this URL into the **URL** field:
   ```
   https://cdn.jsdelivr.net/gh/bauerpawel/DOCKYARD@main/templates.json
   ```
3. Save.
4. Open **App Templates** in the sidebar (under an environment) — every app below is now one click away from deployment.

Requires a Portainer version that supports v3 app templates.

See [local app setup](stacks/README.md) for Open WebUI, Ollama, Backrest, Pocket ID,
BentoPDF, Pangolin and the Hoarder-to-Karakeep migration. These templates use pinned
images; supply required secrets and deployment settings before starting a stack.

The feed is served through [jsDelivr](https://www.jsdelivr.com/)'s CDN rather than raw.githubusercontent.com directly, for faster, more reliable loading worldwide. The scheduled workflows (below) purge jsDelivr's cache after every rebuild, so Portainer always sees the latest `templates.json` within seconds of a change landing on `main`.

## The website

Browse the same catalog at **https://dockyard.kim1.ovh** — search by name, filter by category, and click any app's name/logo/description to expand the full description. Each card links to the app's Docker Hub page and (where known) its own source/homepage.

The interface is available in English, Polish, German and French. It follows the browser's language, the switcher in the header changes it, and `?lang=pl` (or `de`, `fr`) links straight to a version. The strings live in `site_src/i18n.json`; app descriptions stay in English. The build also writes `robots.txt`, `sitemap.xml` and the search-engine metadata (canonical URL, `hreflang` alternates, Open Graph card, JSON-LD) for the domain named in `site_src/CNAME`.

## MCP server for AI agents

The catalog is also available to AI agents through an [MCP](https://modelcontextprotocol.io/) server:

```
https://dockyard.kim1.ovh/mcp
```

With it, Claude, Codex, Grok, Gemini CLI, Cursor, VS Code and other MCP clients can search the apps (`list_apps`), read an app's details (`get_app`) and prepare a deployment plan (`prepare_deploy`). The server only describes apps and builds the plan: it has no access to your Docker or Portainer, and the agent deploys on your machine after you confirm.

Add it to Claude Code with:

```bash
claude mcp add --scope user --transport http dockyard https://dockyard.kim1.ovh/mcp
```

For other clients, open the address in a browser. It shows setup instructions in English, Polish, German and French.

## Quick start

Requires Python 3.14+.

The fastest way to (re)build everything from `apps/` and `stacks/` — sets up `.venv` if needed, builds `templates.json` + `docs/`, and validates the result. This does **not** talk to Docker Hub (see [Keeping metadata fresh](#keeping-metadata-fresh) below):

```bash
run.bat                 # Windows
./run.sh                # Linux / macOS
```

Extra arguments are passed through to `gallery build`, e.g. `run.bat --repo-url https://github.com/bauerpawel/DOCKYARD`.

The default URL comes from `repository.json`. Forks should update that file or use `--repo-url`;
a successful build saves the override there so the feed, website and MCP agree on repository identity.
Placeholder `OWNER/REPO` URLs are rejected.

For manual/step-by-step control:

```bash
python -m venv .venv
.venv/Scripts/activate        # or: source .venv/bin/activate on Linux/macOS
pip install -e ".[dev]"

python -m gallery fetch-metadata   # refresh Docker Hub descriptions (cache/dockerhub.json)
python -m gallery build            # -> templates.json + docs/
python -m gallery validate         # check templates.json against Portainer's v3 schema
pytest                             # run the test suite
```

Open `docs/index.html` directly in a browser to preview the site locally.

Hosting metadata also comes from `site_src/`: edit `site_src/CNAME` for a custom domain,
or remove it for the default Pages domain. An optional `site_src/.nojekyll` is copied as well.
`site_src/MCP_URL` holds the address of the MCP server that the site advertises under the feed URL;
change it to your own server or remove the file to leave the note out.

Builds validate app YAML against `schema/app_schema.json` and the generated feed against the Portainer
schema before publishing. Rendering and asset copying happen in a temporary directory. A failed
publication restores the previous feed, site and repository configuration; a failed rollback preserves
the backup directory and reports its path.

The full integration suite also uses PHP 8.1+, Node.js 18+ and the Docker Compose CLI. Compose tests
run `config` only and require no Docker daemon or running containers.

### Security checks

Install the audit tool with `pip install -e ".[dev,audit]"`. In an activated virtual environment:

```bash
python -m pip freeze --exclude-editable > .venv/audit-requirements.txt
python -m pip_audit -r .venv/audit-requirements.txt --no-deps --disable-pip --strict --progress-spinner off
```

The snapshot includes installed transitive and development dependencies. CI installs Python packages from
`requirements/build.txt` and `requirements/dev.txt`, locked with hashes and a seven-day cooldown for new
releases; after changing dependencies in `pyproject.toml`, rerun the `uv pip compile` command in each file's
header. The CI checks run tests,
build/validation, and a dependency audit on pushes, pull requests, and every Monday. Dependabot checks
Python packages, Composer dependencies and pinned GitHub Actions weekly. See [SECURITY_AUDIT.md](SECURITY_AUDIT.md) for the
audit scope and findings.

The MCP YAML parser is bundled under `mcp/vendor/` with its licenses and `mcp/composer.lock`.
Run `composer audit --working-dir=mcp --locked --no-dev` to check PHP dependencies. To update them,
run `composer update --working-dir=mcp --no-dev` and commit the lockfile together with `mcp/vendor/`.

MCP plans run on the user's machine, so the server only hands out what it can verify. Stackfiles from
other repositories are served at the commit and SHA-256 pinned in `stacks.lock.json`; an upstream change
reaches plans only after review and `python -m gallery pin-stacks --update`. Compose is checked against
an allowlist: host paths outside the data directories, `build`, `external` resources, unknown keys and
variables the plan does not set need `allow_privileged`, and a stack that substitutes `PORTAINER_*` is
always blocked.

Local stacks under `stacks/` require nonempty passwords supplied through the app's environment fields
in Portainer or a local `.env` file. For MCP plans, use `local_secrets` and replace `CHANGEME` locally.
Keep the database password already used by an existing volume when redeploying; changing the `.env`
value alone does not rotate database credentials. n8n uses its owner account setup in the web UI,
not the removed `N8N_BASIC_AUTH_*` settings.

## Keeping metadata fresh

`gallery fetch-metadata` is the only command that talks to Docker Hub. It's deliberately kept out of `run.bat`/`run.sh`'s default flow so a routine rebuild never risks Docker Hub's anonymous rate limit - `gallery build` always reads whatever is already cached in `cache/dockerhub.json`.

Two scheduled GitHub Actions workflows handle both cadences automatically (see [`.github/workflows/`](.github/workflows/)):

- **`build.yml`** - runs on every push to `main` (so a newly added app template goes live right away, and any direct change to `templates.json` still gets its jsDelivr cache purged even if it didn't go through `apps/`/`stacks/`), plus every Saturday as a safety net. Rebuilds `templates.json` + `docs/`, commits if anything changed, and purges jsDelivr's cache for `templates.json` and `stacks.lock.json`. Also runnable on demand from the Actions tab.
- **`refresh-dockerhub.yml`** - on the 1st of each month (the closest calendar-cron equivalent to "every 30 days"), refreshes `cache/dockerhub.json`, rebuilds, and commits.

Both build with a read-only token and the hash-pinned packages in `requirements/build.txt`. A separate job
(`publish-generated.yml`) runs no Python packages, commits only the generated files and starts the tests
for the new commit.

Run `python -m gallery fetch-metadata` locally any time you want an out-of-band refresh.

## Adding a new app

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide (field reference, category list, and how to
source a trustworthy logo/website/image). Short version:

```bash
python -m gallery new my-app --type container   # or --type compose
```

This scaffolds `apps/my-app.yaml`. Fill in the fields:

```yaml
name: My App
slug: my-app
category: Utilities
type: container                    # container | compose
image: namespace/my-app:latest     # required - must be a real Docker Hub image
compose: null                      # required for type=compose instead, e.g. stacks/my-app/docker-compose.yml
description: null                  # null = auto-fetch from Docker Hub; or write your own text
logo: https://.../my-app.png       # required
website: https://github.com/...    # optional - the app's own site or source repo
network: null                      # optional, container only - Docker network to attach to, e.g. host
command: null                      # optional, container only - override the container's command
privileged: null                   # optional, container only - true to run in privileged mode
ports: ["8080/tcp"]
volumes: []
env: []
```

For `type: compose`, either:
- add `stacks/my-app/docker-compose.yml` to this repo and reference it with `compose: stacks/my-app/docker-compose.yml` (see the existing `stacks/*` folders — WordPress, Nextcloud, Gitea, Grafana+Prometheus, n8n and Ghost all pair a primary app with its database), **or**
- point at a stackfile that already exists elsewhere with `repository: {url: https://github.com/..., stackfile: path/to/docker-compose.yml}` instead of `compose:`.

A compose app needs `image` only if it also needs Docker Hub metadata lookup (i.e. no manual `description` is set); container apps always need `image`.

Then run `python -m gallery fetch-metadata && python -m gallery build && python -m gallery validate` and commit the results (including the regenerated `templates.json` and `docs/`) — or just push; the `build.yml` workflow will rebuild it for you (though it won't fetch fresh Docker Hub metadata for a brand-new image until the next monthly refresh, so set a manual `description` if you want it to show up immediately).

Every app needs, at minimum, a `logo` and a resolvable `description` (manual or fetched) — `build` will refuse to produce an entry without one.

## Reporting bugs and suggesting fixes

Found a broken template, a wrong/outdated `website` or `logo` link, a bad description, or anything else off? [Open an issue](https://github.com/bauerpawel/DOCKYARD/issues) — mention the app's slug (the YAML filename under `apps/`) so it's easy to find.

Want to fix it yourself?

1. Fork the repo and edit the relevant file — usually `apps/<slug>.yaml` for a single app, or `site_src/`/`src/gallery/` for the site or tooling.
2. Run `run.bat` / `./run.sh` and `pytest` to confirm everything still builds, validates, and passes.
3. Open a pull request.

## Project structure

```
apps/*.yaml                 # one file per app - the source of truth
stacks/<slug>/*.yml         # docker-compose files for type=compose apps
schema/templates_schema.json # vendored Portainer v3 JSON Schema, used by `validate`
src/gallery/                # the Python package (models, loader, Docker Hub client, builders, CLI)
site_src/                   # Jinja2 template, translations (i18n.json) + CSS/JS for the website
mcp/                        # PHP MCP server; guide/ holds the setup instructions it shows in a browser
docs/                       # generated website, served by GitHub Pages
cache/dockerhub.json        # cached Docker Hub metadata, refreshed by `fetch-metadata`
templates.json              # generated - the file Portainer actually fetches
tests/                      # pytest suite
requirements/               # hash-pinned CI dependencies, generated by `uv pip compile`
.github/workflows/          # scheduled rebuild + Docker Hub refresh (see above)
```

## One-time deployment setup

The site (`docs/`) is served by **GitHub Pages** directly from this repo — no separate hosting needed. Once this repo is pushed to `https://github.com/bauerpawel/DOCKYARD`:

1. In the repo's **Settings → Pages**, set source to branch `main`, folder `/docs`. The site then lives at `https://dockyard.kim1.ovh` and updates automatically whenever `docs/` changes on `main` — including the commits the scheduled workflows push.
2. That's it — the feed URL and website URL above already point at this repo.

For Apache/MCP hosting, copy the complete `mcp/` directory (including `vendor/` and `guide/`); see
[mcp/INSTRUKCJA.md](mcp/INSTRUKCJA.md). The server reads the feed from the jsDelivr CDN and caches it
for 15 minutes, so `templates.json` next to it is only a fallback; `repository.json` and `stacks/`
let it use local Compose files. Opening the server address in a browser shows how to add it to
Claude, Codex, Grok, Gemini CLI, Cursor and VS Code, in English, Polish, German or French
(`mcp/guide/`). The optional `deploy/refresh.php` updater installs a commit only after its `test` jobs pass in
GitHub Actions, then validates the release and stages all artifacts before replacement. A publication error rolls back prior replacements; Apache configuration and the MCP
cache remain in place. Backup paths are reported if rollback itself fails.

## License

MIT — see [LICENSE](LICENSE).
