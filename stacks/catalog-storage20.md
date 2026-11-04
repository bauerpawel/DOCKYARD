# Garage–Workout.cool setup guide

These twenty templates use published images pinned to reviewed SHA-256 digests.
The registry manifests, official website titles and logo content were checked on
2026-11-03. All twenty application images provide Linux AMD64 and ARM64 variants;
Shoko describes ARM64 support as limited. No Docker engine was available during
catalog verification, so the checks cover feed generation, PHP MCP deployment
plans and the real Docker Compose configuration parser, not running services.

Supply every required setting before deployment. Generate independent passwords
and retain them with your backups. For passwords embedded in a database URL or
inline JSON, use the documented hexadecimal/alphanumeric format. Changing an
environment password after a database has initialized does not change the stored
database role password.

Local stacks use named volumes and have no missing build contexts, sibling
configuration files or `.env` file dependencies. Inline Compose configuration
requires Compose 2.23.1 or newer. Download the local stack into an isolated project
directory, supply its variables through Portainer or your local environment, and
run `docker compose config` before starting it.

Compose web/API ports are bound to `127.0.0.1`. Use an SSH tunnel or an HTTPS
reverse proxy on the Docker host for remote access; a proxy in a separate
container needs a deliberately configured route to the application. Blocky's DNS
listener can be moved to a selected LAN IP. The single-container Portainer
templates use Portainer's port mapping interface; choose appropriate host
bindings and configure HTTPS where required by the app notes.

| App | Storage and first start | Upstream reference |
| --- | --- | --- |
| Garage | Set a 64-hex RPC secret, an access key of `GK` plus 24 hex characters and an independent S3 secret. Starts with one private bucket, region `garage`, port 3900 and path-style requests. Back up metadata and objects together. Single-node storage has no redundancy. | [Docker and single-node setup](https://garagehq.deuxfleurs.fr/documentation/quick-start/) |
| SeaweedFS | One process runs master, volume server, filer and S3. Only authenticated S3 port 8333 is published. Both object data and the LevelDB filer index persist under `/data`. Set alphanumeric S3 credentials; internal HTTP/gRPC services must stay private. | [Docker deployment](https://github.com/seaweedfs/seaweedfs/tree/master/docker) |
| zot | The init service writes a bcrypt htpasswd file from the supplied username/password. Registry data persists separately. Use `docker login localhost:5000`; remote Docker clients require a trusted HTTPS endpoint. | [Authentication](https://zotregistry.dev/v2.1.20/articles/authn-authz/) |
| OpenBao | Normal server mode with persistent file storage. Run `docker compose exec openbao bao operator init`, store the shares/root token outside the server, and unseal with `bao operator unseal`. Unseal again after restarts. HTTP is local only; add TLS and adjust `api_addr` before remote use. Memory locking is disabled, so protect host memory and disable swap. | [Server configuration](https://openbao.org/docs/configuration/) |
| step-ca | Set the CA DNS names/IPs and a strong initialization password. The empty `/home/step` volume is initialized on first start. Bootstrap clients using the root fingerprint; this is a private CA. ACME requires an explicitly configured provisioner. | [Docker CA guide](https://smallstep.com/docs/tutorials/docker-tls-certificate-authority/) |
| Blocky | Local TCP/UDP port 53 and HTTP API port 4000. To serve the LAN, choose the host LAN IP and restrict DNS access to trusted networks. The API stays on loopback. Inline configuration defines DoH resolvers and the blocking list. | [Installation and configuration](https://0xerr0r.github.io/blocky/latest/installation/) |
| Roundcube | Supply existing TLS-capable IMAP/SMTP servers and a stable random 24-character `ROUNDCUBEMAIL_DES_KEY`. Login uses mailbox credentials. Persist SQLite metadata and any custom config; mail remains on the IMAP server. | [Official Docker image](https://github.com/roundcube/roundcubemail-docker) |
| NodeBB | Open the local installer on port 4567 and choose PostgreSQL: host `db`, database/user `nodebb`, supplied database password. Set the final public URL and create the administrator. Keep PostgreSQL, configuration, dependencies, uploads and build volumes. Startup requires Internet access for Node dependencies. | [Docker setup](https://docs.nodebb.org/installing/cloud/docker/) |
| Zulip | Configure a real DNS name, HTTPS reverse proxy, SMTP and six independent secrets. Requires at least 2 GB available RAM and regular Docker. Generate the organization link with the command below. Uses the upstream PostgreSQL 14 image; major upgrades need the documented migration procedure. | [Official Docker documentation](https://zulip.readthedocs.io/projects/docker/en/latest/) |
| SiYuan | Requires a strong workspace access password. Explicitly runs `serve --workspace=/siyuan/workspace`. Preserve the workspace. The reverse proxy must forward WebSockets and preserve the original Host header including any nonstandard port. | [Docker hosting](https://github.com/siyuan-note/siyuan#docker-hosting) |
| Flatnotes | Set the login password and a separate session secret. Password authentication is enabled. Keep `/data`, which contains Markdown notes and the search index. Match PUID/PGID to any existing files. | [Docker examples](https://github.com/dullage/flatnotes) |
| Etherpad | PostgreSQL plus persistent session state. Set separate database, admin and user passwords. All pads require login. Uses the legacy API-key authentication mode; online updater checks are disabled for the pinned image. | [Docker settings](https://docs.etherpad.org/docker.html) |
| Papra | Rootless image with database/documents under `/app/app-data`. Set the final URL and an authentication secret. Create the intended accounts, then turn registration off. Optional OCR, ingestion and LLM integrations need their own configuration. | [Docker setup](https://docs.papra.app/self-hosting/using-docker/) |
| PdfDing | Set the allowed hostname and signing secret. Access through HTTPS; secure cookies remain enabled. Signup is closed. Create an account with the management command below. Email verification is disabled for this private installation without SMTP. Back up database and media volumes. | [Docker setup](https://docs.pdfding.com/getting_started/docker/) and [admin users](https://docs.pdfding.com/guides/admin_users/) |
| CyberChef | Static browser application on container port 8080. No database or server-side data volume. Save recipes and output explicitly. | [Official image](https://github.com/gchq/CyberChef) |
| OmniTools | Static browser tools on container port 80. No account or database. Large media operations use the client browser's memory. | [Docker setup](https://github.com/iib0011/omni-tools) |
| Bytebase | Open the local setup wizard and create the first administrator. Embedded metadata persists under `/var/opt/bytebase`. The Compose init process handles child-process cleanup. Existing databases are added later; some governance features require a commercial license. | [Quick start](https://github.com/bytebase/bytebase) |
| Convex | Backend, HTTP actions and dashboard have separate ports. Set browser-visible origins, then generate an admin key with the command below. Keep `/convex/data`. The template does not deploy your own application frontend. The backend uses FSL-1.1-Apache-2.0. | [Self-hosting guide](https://github.com/convex/convex-backend/tree/main/self-hosted) |
| Shoko Server | Choose an existing absolute media directory and correct PUID/PGID. Configure the UI and AniDB account. Media is read-only; renaming/moving files is unavailable. MCP requires separate approval for reading this host directory. Keep `/home/shoko/.shoko`. | [Server installation](https://docs.shokoanime.com/getting-started/installing-shoko-server) |
| Workout.cool | Requires PostgreSQL, an authentication secret, SMTP and Google OAuth credentials. The upstream environment validator requires Google credentials even with password login. Register `/api/auth/callback/google` at the public URL. Migrations run before serving; turn sample-data import off after first setup. Retain the auth secret because it participates in password hashing. Review frontend build-time URL constraints when using a custom domain. | [Self-hosting](https://github.com/Snouzy/workout-cool/blob/main/docs/SELF-HOSTING.md) and [environment validation](https://github.com/Snouzy/workout-cool/blob/main/src/env.ts) |

## Initialization commands

Run these locally on the Docker host with the matching Compose project selected.
Never post generated admin keys, unseal shares or root tokens to the MCP server.

```sh
# OpenBao: initialize once, then unseal with the required shares.
docker compose exec openbao bao operator init
docker compose exec openbao bao operator unseal

# Zulip: generate the initial organization creation URL after startup completes.
docker compose exec zulip /sbin/entrypoint.sh app:managepy generate_realm_creation_link

# Convex: create an administrator key for the dashboard and local CLI.
docker compose exec backend ./generate_admin_key.sh
```

For PdfDing's container template, use the container name assigned by Portainer:

```sh
docker exec -it YOUR_PDFDING_CONTAINER python pdfding/manage.py createsuperuser
```

For step-ca, obtain the root certificate fingerprint inside its container:

```sh
docker exec YOUR_STEP_CA_CONTAINER step certificate fingerprint /home/step/certs/root_ca.crt
```

Use that fingerprint with `step ca bootstrap --ca-url https://YOUR_CA:9000
--fingerprint YOUR_FINGERPRINT` on each intended client. Protect and back up the CA
volume and keep its password separately.

## Configuration sources and licenses

The Zulip stack is adapted from the official
[compose.yaml](https://github.com/zulip/docker-zulip/blob/main/compose.yaml),
[override example](https://github.com/zulip/docker-zulip/blob/main/compose.override.yaml.example)
and [entrypoint](https://github.com/zulip/docker-zulip/blob/main/entrypoint.sh).
It uses the supported `SECRETS_` environment interface rather than separate
secret files, local HTTP ingress, no image build, and private companion services.
The upstream Apache 2.0 license is retained in `zulip/LICENSE.upstream`.

The Convex stack is adapted from the upstream
[self-hosted Compose configuration](https://github.com/convex/convex-backend/blob/main/self-hosted/docker/docker-compose.yml),
with local ports and an explicit persistent SQLite backend. The upstream license
is retained in `convex/LICENSE.upstream`. Review its permitted-use terms before
offering a competing commercial hosting service.

The Workout.cool startup command runs the migrations and optional exercise
import described by the upstream
[setup script](https://github.com/Snouzy/workout-cool/blob/main/scripts/setup.sh),
with immediate failure on migration errors. `NEXT_PUBLIC_*` values in a published
Next.js image can be compiled into frontend assets at build time; changing runtime
variables does not rebuild those assets. Use a correctly built upstream image
when a custom-domain frontend requires it, then review and pin its new digest.

Ordinary builds use the checked-in Docker metadata cache and do not move the
reviewed digests. Updates require reviewing upstream configuration changes and
verifying the replacement images again.
