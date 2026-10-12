# Repository Guidelines

## Project Structure & Module Organization

DOCKYARD generates a Portainer v3 template feed and a static app gallery.

- `apps/*.yaml`: canonical app definitions; Compose files live in `stacks/<slug>/docker-compose.yml`.
- `src/gallery/`: Python models, loaders, builders, Docker Hub client, and CLI; `tests/` contains pytest tests.
- `site_src/`: Jinja2 templates, `i18n.json` site translations (en, pl, de, fr), `MCP_URL` (MCP server address shown on the site), and CSS/JS/SVG assets; `brand/` contains branding images.
- `templates.json` and `docs/`: generated feed and website. Edit their sources and regenerate.
- `schema/`: Portainer JSON Schema; `cache/dockerhub.json`: cached metadata.
- `mcp/`: PHP MCP server, with `guide/<lang>.md` setup instructions it serves to browsers; `deploy/refresh.php`: deployment updater; `.github/workflows/`: automated rebuilds and metadata refreshes.

## Build, Test, and Development Commands

Use Python 3.10+ (CI uses 3.14). Run commands from the repository root with a virtual environment activated.

- `pip install -e ".[dev]"`: install the package and pytest.
- `run.bat` (Windows) or `./run.sh` (Linux/macOS): prepare the environment, build, and validate.
- `python -m gallery build`: regenerate `templates.json` and `docs/`.
- `python -m gallery validate`: check the feed against the schema.
- `python -m gallery new my-app --type container`: scaffold an app; use `compose` for multi-service stacks.
- `python -m gallery fetch-metadata`: explicitly refresh Docker Hub metadata; routine builds use the cache.
- `pytest`: run all tests; `pytest tests/test_loader.py` runs one module.

Preview the website by opening `docs/index.html`.

## Coding Style & Naming Conventions

Use four-space indentation for Python/PHP and two spaces for YAML, JavaScript, and CSS. Follow existing type hints, `snake_case` Python functions, and `PascalCase` classes. App filenames and slugs use lowercase hyphenated names, such as `my-app.yaml`. Reuse categories listed in `CONTRIBUTING.md`. No formatter or linter is configured; match surrounding code.

## Testing Guidelines

Name modules `tests/test_*.py` and functions `test_*`. Add regression tests for changed behavior. No numeric coverage threshold is configured. PHP integration tests require PHP on PATH; deployment tests also require ZipArchive and skip when unavailable. Run pytest, build, and validation before submitting.

## Commit & Pull Request Guidelines

History uses short imperative titles, such as `Add RustFS app template`; follow that style. Keep commits focused. PRs should describe the change, identify affected app slugs, link relevant issues, report checks, and include screenshots for visual changes. Commit regenerated outputs alongside source changes. Verify image references, logos, official website links, and external stackfiles using `CONTRIBUTING.md`; explain privileged container access in the app description.

