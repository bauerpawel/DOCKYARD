# Contributing to DOCKYARD

Thanks for helping grow the catalog. This covers two cases:

- **Adding your own app** — you maintain a Docker image and want it in the gallery.
- **Adding an app you noticed is missing** — you found something useful elsewhere that isn't here yet.

Both follow the same process: add one YAML file under [`apps/`](apps/), then regenerate.

## Quick start

```bash
python -m gallery new my-app --type container   # or --type compose
```

This scaffolds `apps/my-app.yaml` with the required fields commented. Fill it in (see the field
reference below), then:

```bash
python -m gallery fetch-metadata   # optional - only needed if description: null and image is on Docker Hub
python -m gallery build            # -> templates.json + docs/
python -m gallery validate         # check templates.json against Portainer's v3 schema
pytest                             # run the test suite
```

Commit `apps/my-app.yaml` along with the regenerated `templates.json` and `docs/`, and open a PR.
(If you skip the regeneration step, `build.yml` will do it for you on push to `main` — but it won't
fetch fresh Docker Hub metadata for a brand-new image until the next monthly refresh, so set a manual
`description` if you want the entry to show up correctly right away.)

## Field reference

```yaml
name: My App                       # required - display title
slug: my-app                       # required - filename without .yaml, used as the Portainer container/stack name
category: Utilities                # required - pick from the existing list below; don't invent a new one
type: container                    # required - container | compose
image: namespace/my-app:latest     # required for type=container; also used for Docker Hub metadata lookup
compose: stacks/my-app/docker-compose.yml   # type=compose only, see "container vs compose" below
repository: {url: ..., stackfile: ...}      # type=compose only, alternative to compose: - see below
description: null                  # null = auto-fetch from Docker Hub, or write your own text
logo: https://.../my-app.png       # required - see "Sourcing a logo" below
website: https://github.com/...    # optional but strongly encouraged - see "Sourcing a website link" below
network: null                      # optional, container only - Docker network to attach to, e.g. host
command: null                      # optional, container only - override the container's command
privileged: null                   # optional, container only - true to run in privileged mode
ports: ["8080/tcp"]                # optional - container ports to expose
volumes:                           # optional
  - container: /data               # required - path inside the container
    bind: /host/path                 # optional - host path; omitted lets Portainer manage it
    readonly: true                   # optional
env:                                # optional
  - name: PASSWORD                 # required - the environment variable name
    label: Admin password            # optional - shown in the Portainer UI instead of the raw name
    description: ...                 # optional - tooltip text
    default: ...                     # optional
    preset: true                     # optional - true hides the field and silently applies default
    select:                          # optional - renders a dropdown instead of a text field
      - text: "false"
        value: "false"
        default: true
      - text: "true"
        value: "true"
```

Every app needs, at minimum, a `logo` and a resolvable `description` (manual or fetched) —
`gallery build` will refuse to produce an entry without one.

`network`, `command` and `privileged` map directly to fields in Portainer's own template format
(verified against `portainer/portainer`'s `Template` struct, not just the vendored schema). Note that
Portainer templates have **no** `cap_add` or `devices` field at all — if your image needs a specific
Linux capability or a host device (e.g. `/dev/kvm`, `NET_ADMIN` for a VPN), the only lever available is
`privileged: true`, which grants broad host access as a side effect. Say so plainly in the `description`
if you set it, so users know what they're opting into.

### Picking a category

Use one of the existing categories — adding a new one fragments the site's filter list for a single app:

`Other`, `Media`, `Utilities`, `Communication`, `Networking`, `Productivity`, `Downloaders`, `Monitoring`,
`Development`, `Books & Documents`, `Gaming`, `Web`, `CMS`, `Automation`, `Cloud & Storage`,
`Business & Finance`, `Database`, `Remote Access`, `Security`, `3D Printing & Modeling`, `Dashboard`,
`Science & Learning`

### `type: container` vs `type: compose`

Use `container` for a single-container app. Use `compose` when it needs a companion service (a database,
a cache, a sidecar). For `compose`, either:

- add `stacks/my-app/docker-compose.yml` to this repo and reference it with
  `compose: stacks/my-app/docker-compose.yml` (see the existing `stacks/*` folders — WordPress, Nextcloud,
  Gitea, Grafana+Prometheus, n8n and Ghost all pair a primary app with its database), **or**
- point at a stackfile that already exists in another repo with
  `repository: {url: https://github.com/..., stackfile: path/to/docker-compose.yml}` instead of `compose:`.

If you use an external `repository:`, **open the actual stackfile first** and check every `image:` line
resolves and there's no `build:` directive with a missing context — a stackfile that builds from source
files not present in that repo will fail when Portainer clones it. This has bitten this catalog before
(see git history for the Documize and Medusa removals): don't just trust that a stackfile referenced
elsewhere still works.

A compose app needs `image` only if it also needs Docker Hub metadata lookup (i.e. no manual
`description` is set); container apps always need `image`.

## Sourcing a logo

Check, in order:

1. The project's own repo for a dedicated icon/logo file (root, `docs/`, `assets/`, `.github/`).
2. The [selfhst/icons](https://github.com/selfhst/icons) set (`https://cdn.jsdelivr.net/gh/selfhst/icons/png/<name>.png`) — a large curated icon collection already used throughout this repo.
3. The project's own official website (favicon or a proper `<link rel="icon">`/apple-touch-icon asset).

If none of those exist, use a clearly generic placeholder (a neutral icon from a non-branded set, not
another app's logo) and say so in the `description`, e.g. *"no official icon exists yet"*. Never reuse
a different, unrelated project's icon just because it's visually close.

## Sourcing a website link

`website` must be the app's **own** official page — its marketing site, docs site, or (for projects with
no dedicated site) its own GitHub/GitLab repo. It must **not** be:

- a shared template-aggregator repo (e.g. `xneo1/portainer_templates`, `pi-hosted/pi-hosted`,
  `mediadepot/templates`) — those host logos/stackfiles for many unrelated apps, not this one's own page
- a blog post, product-review site, job board, or forum thread that happens to embed the app's logo
- a generic CDN, avatar service, or image-hosting bucket unrelated to the project itself

Verify it: fetch the page and confirm its title actually names the app, not just that the URL returns
HTTP 200 — a live page at a plausible-looking domain is not proof it's the right one. This repo has
previously had apps whose logo/website pointed at review blogs, a job-listing CDN, and even an unrelated
company's internal asset bucket, purely because a domain "looked official" without being checked.

If you genuinely can't find an official page for an app (rare, but happens for very obscure or
abandoned projects), leave `website` off rather than guessing.

## Verifying the image itself

Before submitting, confirm the image reference actually resolves — a typo'd tag, a renamed Docker Hub
namespace, or an image the upstream project quietly moved to GHCR/another registry will all silently
break the template. A quick check:

```bash
curl -sI https://hub.docker.com/v2/repositories/<namespace>/<repo>/    # Docker Hub
```

(For GHCR or other registries, checking the project's own install docs for the current image reference
is more reliable than probing the registry API directly.)

## Reporting bugs and suggesting fixes

Found a broken template, a wrong/outdated `website` or `logo` link, a bad description, or anything else
off? [Open an issue](https://github.com/bauerpawel/DOCKYARD/issues) — mention the app's slug (the YAML
filename under `apps/`) so it's easy to find.

## Before opening a PR

1. `python -m gallery build` and `python -m gallery validate` both succeed.
2. `pytest` passes.
3. `templates.json` and `docs/` are regenerated and committed alongside your `apps/*.yaml` change (or
   left for `build.yml` to regenerate on merge).
4. `logo` and `website` (if set) both resolve, and `website` demonstrably belongs to this app, not a
   template aggregator, blog, or unrelated site.

## Project structure

```
apps/*.yaml                 # one file per app - the source of truth
stacks/<slug>/*.yml         # docker-compose files for type=compose apps
schema/templates_schema.json # vendored Portainer v3 JSON Schema, used by `validate`
src/gallery/                # the Python package (models, loader, Docker Hub client, builders, CLI)
site_src/                   # Jinja2 template + CSS/JS for the website
docs/                       # generated website, served by GitHub Pages
cache/dockerhub.json        # cached Docker Hub metadata, refreshed by `fetch-metadata`
templates.json              # generated - the file Portainer actually fetches
tests/                      # pytest suite
.github/workflows/          # scheduled rebuild + Docker Hub refresh
```

See [README.md](README.md) for how the feed and site are used, and how the scheduled rebuild/metadata
workflows fit together.
