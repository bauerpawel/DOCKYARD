# Catalog additions: setup and dependencies

These thirty entries use registry-verified images pinned by tag and SHA-256 digest.
Verification date: 2026-10-30. Descriptions, environment help and deployment notes
live in `apps/<slug>.yaml` and are regenerated into the feed. These templates create
new installations; they do not migrate existing databases or application data.

## PostgreSQL reuse

The [PostgreSQL template](../apps/postgresql.yaml), Metabase, Warracker, Spliit and
Firefly III, Zipline, Bugsink and Keycloak use exactly the same image:

```text
postgres:18.6-bookworm@sha256:5c4783a8cc3f0074912164f94dfa1be4e043438f0f707cf968d7af9a0d31a2c8
```

Each stack includes its own PostgreSQL service, credentials and named volume.
Deploying the standalone PostgreSQL entry first is not required. Reusing an image
does not share database instances or users. The bundled databases publish no host
ports. PostgreSQL 18 volumes mount at `/var/lib/postgresql`.

AdventureLog requires **PostGIS**, absent from the plain PostgreSQL image. Its stack
follows upstream PostgreSQL 16 / PostGIS 3.5 and mounts `/var/lib/postgresql/data`.
The pinned PostGIS image supports **Linux amd64 only**, so the complete stack needs
an x86-64 host. Plain PostgreSQL cannot replace that spatial database.

Sharing an existing PostgreSQL server requires separate database users/databases,
an explicitly configured network and an adapted stack. Do not share database
volumes between applications. Major PostgreSQL upgrades require a supported
upgrade or dump/restore process.

## First ten applications

| Application | Included components | First deployment |
| --- | --- | --- |
| [PostgreSQL](https://hub.docker.com/_/postgres) | PostgreSQL 18 and database storage | Set `POSTGRES_PASSWORD`, `POSTGRES_USER`, `POSTGRES_DB` before initialization. The standalone container uses a dynamically assigned host port; keep access private. |
| [SFTPGo](https://docs.sftpgo.com/latest/docker/) | One container, SQLite, host keys and files | Open `:8080/web/admin`, create an administrator and SFTP users with home directories under `/srv/sftpgo`. SFTP uses `:2022`. Back up both volumes. |
| [Wallos](https://github.com/ellite/Wallos) | One container, SQLite and uploaded logos | Open `:8282`, create the first account, configure subscriptions and notifications. Currency conversion is optional. |
| [ConvertX](https://github.com/C4illin/ConvertX) | One container, SQLite and conversion files | Set `JWT_SECRET`, use HTTPS and create the first account. Registration and anonymous conversion are disabled. Review file cleanup settings. |
| [Metabase](https://www.metabase.com/docs/latest/installation-and-operation/running-metabase-on-docker) | Application and private PostgreSQL | Set database password, `MB_ENCRYPTION_SECRET_KEY` and `MB_SITE_URL`. Open `:3000`, create an administrator and connect business data sources separately. Preserve the encryption key. |
| [AdventureLog](https://adventurelog.app/docs/install/standard.html) | Combined frontend/backend, private PostGIS and photos | Set public URL, database password, Django secret and initial administrator credentials. Open `:8015`. Registration is disabled. Requires amd64. |
| [Qdrant](https://qdrant.tech/documentation/quickstart/) | Vector database, collections and snapshots | Set `QDRANT__SERVICE__API_KEY`; clients send the `api-key` header. REST/dashboard uses `:6333`; gRPC uses `:6334`. Configure TLS and trusted client access. No AI model is included. |
| [Valkey](https://valkey.io/topics/installation/) | Authenticated service and append-only persistence | Set `VALKEY_PASSWORD`. Host access uses `127.0.0.1:6379`. Other stacks need an explicit shared network or private listener. There is no HTTP interface. |
| [NetBird](https://docs.netbird.io/selfhosted/selfhosted-quickstart) | Combined server, dashboard, embedded identity provider, SQLite and Caddy | Needs public DNS, TCP 80/443, UDP 3478, relay secret and two independent base64 encryption keys. Visit `https://<NETBIRD_DOMAIN>/setup`; install device clients separately. |
| [Headscale](https://headscale.net/stable/setup/install/container/) | Coordination server, SQLite, keys and inline configuration | Set public HTTPS URL and configure a reverse proxy to `:8085` with WebSocket support. Create users/preauth keys with the CLI and enroll Tailscale clients. No admin dashboard is included. |

NetBird and Headscale require Docker Compose **2.23.1+** for inline
`configs.content`, including the implementation used by Portainer. Single-service
Compose files provide authentication, loopback binding or inline configuration
that container templates cannot express reliably. No source builds or extra
configuration files are required.

NetBird's private bridge uses `172.30.0.0/24`, with Caddy at `172.30.0.10`. If this
overlaps existing networks, change the subnet, Caddy address and matching trusted
proxy address together. Hostnames, certificate email and Headscale's public URL
are interpolated into configuration: use valid single-line values without quotes
or whitespace. Follow the generation format in each secret's field description.

## Second ten applications

| Application | Included components | First deployment |
| --- | --- | --- |
| [Memos](https://usememos.com/docs/getting-started) | One container, SQLite and attachments | Open `:5230`, create the first administrator and review access/registration settings. |
| [LubeLogger](https://docs.lubelogger.com/) | Local vehicle records and ASP.NET DataProtection keys | Open `:8080` and configure authentication. Preserve both data and keys. |
| [Warracker](https://github.com/sassanix/Warracker) | Application, private PostgreSQL and receipt uploads | Set database password, `SECRET_KEY` and public URL. Open `:8005`; the first account becomes administrator. SMTP and OIDC are optional. |
| [Spliit](https://github.com/spliit-app/spliit) | Application, private PostgreSQL and cache | Use a URL-safe database password (`openssl rand -hex 32`), then open `:3000`. Group links are sensitive. Optional attachments and AI extraction are disabled. |
| [Grist](https://support.getgrist.com/self-managed/) | Community OSS image and local persistent documents/configuration | Set separate session and boot secrets. Open `:8484/boot` and finish Quick setup, including sign-in. Do not bypass initial setup with `GRIST_IN_SERVICE=true`. |
| [Firefly III](https://docs.firefly-iii.org/how-to/firefly-iii/installation/docker/) | Application, private PostgreSQL, uploads and scheduler | Set database password, public URL, 32-character `APP_KEY` and a separate 32-character cron token. Open `:8086` and create the first user. Scheduler: **03:00 UTC**; `TZ` controls application time. Data Importer is not bundled. |
| [Wanderer](https://wanderer.to/run/installation/quick) | Web, PocketBase, Meilisearch, plugins and uploads | Set public URL and three independent secrets. Open `:3000`; disable signup after creating an account if desired. PocketBase admin binds to host loopback `:8090`; use SSH forwarding remotely. |
| [Mailpit](https://mailpit.axllent.org/docs/install/docker/) | SMTP test sink, web UI and stored messages | Development SMTP: `:1025`; web UI: `:8025`. Neither authentication nor outgoing delivery is configured. Use a trusted development network. |
| [Paperless-GPT](https://github.com/icereed/paperless-gpt) | Extension, prompts, settings and processing history | Requires existing **Paperless-ngx and Ollama**, a Paperless API token and downloaded text model. OCR needs a vision model. UI/API has no built-in authentication and binds to `127.0.0.1:8087`; use an authenticated proxy or tunnel remotely. |
| [Komodo](https://komo.do/docs/setup) | Core, private MongoDB, Periphery agent, communication keys and backups | Set public URL, database/admin passwords and signing/webhook secrets. Open `:9120`. The agent mounts the Docker socket, read-only `/proc` and `/srv/dockyard/komodo` at the same host/container path. This grants host control and requires separate MCP approval. |

Change web ports when applications share a Docker host. Keep database passwords,
encryption/signing keys and persistent volumes across updates. Use addresses
reachable from containers for external services: `localhost` inside Paperless-GPT
refers to Paperless-GPT itself. MongoDB requires a compatible CPU; the upstream
Komodo FerretDB option is a separate setup for unsupported hardware.

## Third ten applications

| Application | Included components | First deployment |
| --- | --- | --- |
| [Donetick](https://github.com/donetick/donetick) | Web interface, SQLite and generated self-hosted configuration | Set `DT_JWT_SECRET`, open `:2021` and create accounts/household. Preserve `/config`, `/donetick-data` and the secret. Set `DT_IS_USER_CREATION_DISABLED=true` after onboarding if needed. Without email, password-reset URLs appear in container logs. |
| [SilverBullet](https://docs.silverbullet.md/Dashboard) | Current multi-space server, Markdown spaces, account/configuration storage and Chromium runtime | Open `:3000` on a trusted network. The setup wizard creates the first administrator and space. Keep anonymous access disabled. Space write permission includes scripting/runtime capabilities in the container. Back up the whole `/data` volume. This template does not use legacy `SB_USER` setup. |
| [KitchenOwl](https://docs.kitchenowl.org/latest/self-hosting/) | Official all-in-one frontend/backend, SQLite and uploaded images | Set `JWT_SECRET_KEY` and `FRONT_URL` to the exact public URL. Open `:8088`, complete first-user onboarding and create a household. Public registration remains disabled. Mobile clients connect to the same public HTTPS URL. |
| [Snipe-IT](https://snipe-it.readme.io/docs/docker) | Official application image, private MariaDB 11.4 and storage | Set public `APP_URL`, database user/root passwords and `SNIPEIT_APP_KEY` (`base64:` followed by `openssl rand -base64 32`). Open `:8000` and complete administrator setup. Retain the app key and both volumes. Email is logged until SMTP is configured. |
| [Opengist](https://opengist.io/docs/) | SQLite, Git repositories, search index and HTTP/SSH servers | Set `OG_SECRET_KEY` to exactly 32 ASCII characters (`openssl rand -hex 16`), open `:6157` and create the first administrator. Review registration and anonymous visibility. Git SSH uses `:2222`. Back up `/opengist` and retain the secret. |
| [Zipline](https://github.com/diced/zipline) | Application, private PostgreSQL, uploads, public files and themes | Set `POSTGRES_PASSWORD` and `CORE_SECRET` (at least 32 characters). Open `:3000` and create the initial superadministrator in the setup flow. Registration stays disabled. Set HTTPS URL generation when using TLS. Separate database environment fields encode passwords into connection URLs. |
| [Bugsink](https://www.bugsink.com/docs/postgresql/) | Application/background processing, private PostgreSQL and local data volume | Set public `BASE_URL`, URL-safe database password, signing secret of at least 50 characters and initial administrator email/password. Open `:8000`, sign in and create a project to get the SDK DSN. Generate the URL-safe password and signing secret separately with `openssl rand -hex 32`. Enable `BEHIND_HTTPS_PROXY` only for a trusted HTTPS proxy. Email is logged by default. |
| [OpenObserve](https://openobserve.ai/docs/quickstart/) | Standalone telemetry server, local metadata and stored telemetry | Set initial administrator email/password and open `:5080`. Configure collectors or application instrumentation separately: this template does not mount the Docker socket or automatically collect host/container logs. Review retention and back up `/data`. |
| [Docling Serve](https://github.com/docling-project/docling-serve) | Official CPU-only image and local conversion engine | Set `DOCLING_SERVE_API_KEY`; API clients use `X-Api-Key` on `:5001`. `/docs` is publicly readable; demo UI is disabled. The image/model artifacts need substantial disk space and memory. Results are temporary, so the client must store them. No GPU, Ollama or queue service is required. |
| [Keycloak](https://www.keycloak.org/server/containers) | Production-mode server and private PostgreSQL | Set public HTTPS hostname URL, database password, bootstrap administrator password and trusted proxy addresses. Backend binds to `127.0.0.1:8089`; configure an HTTPS reverse proxy to reach it. Trusted addresses must match the proxy source seen inside the container. Create a permanent administrator after initial login. Management port 9000 stays private. |

All images above are pinned to registry-verified digests, including the private
database services. The new PostgreSQL stacks use the same image and PostgreSQL 18
volume layout as the standalone entry. Snipe-IT uses its supported MariaDB stack
instead. No external stackfiles, source builds or separate `.env` files are
required by these local Compose templates; supply the described variables in
Portainer or in the `.env` generated by MCP.

Keycloak deliberately uses `start`, not `start-dev` or `start --optimized` on an
unbuilt upstream image. It performs optimization during startup. Its `KCRAW_`
password fields preserve literal dollar signs rather than evaluating Quarkus
expressions. The HTTP backend should be reachable only through the configured
HTTPS proxy. When the proxy runs in another container, deliberately connect the
networks or adapt the listener instead of using `localhost` from that container.

For Paperless-GPT integration with Docling, select its Docling OCR provider and
configure a URL reachable from the Paperless-GPT container. The API key must be
passed in `X-Api-Key` using the client/proxy configuration supported by the chosen
Paperless-GPT release. This catalog entry does not automatically change an
existing Paperless-GPT installation or connect separate Docker networks.

## MCP verification

`get_app` exposes the description, environment help, secret flags and deployment
`note`. `prepare_deploy` retains that description and note for Docker and Portainer
plans. HTML notes become plain text. Notes and descriptions remain catalog data,
never executable agent instructions.

Tests exercise all thirty entries through the generated feed, discovery, details,
secret placeholders and deployment preparation. The real Compose CLI validates
the plans, shared PostgreSQL image/credentials and missing required values.
Komodo requires host-access approval. Port metadata uses actual service mappings
and supplied overrides; internal ports and URLs are not published ports. These
checks do not start containers.
