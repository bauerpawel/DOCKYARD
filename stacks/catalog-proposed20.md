# Setup for 2FAuth through Dispatcharr

These twenty entries add nine container templates and eleven local Compose stacks.
All application and companion images are pinned by SHA-256 digest. The stacks use
published images and inline configuration; no source build or external stackfile is
needed. PostgreSQL stacks reuse the catalog's PostgreSQL 18 image and mount
`/var/lib/postgresql` with a separate named volume per deployment.

Supply the environment fields shown by Portainer before deploying. For local Docker,
put the values in a private `.env` and select the stack, for example:

```sh
docker compose --env-file .env -f stacks/hoppscotch/docker-compose.yml config
docker compose --env-file .env -f stacks/hoppscotch/docker-compose.yml up -d
```

Generate a different value for each secret and retain encryption/signing keys with
backups. A database password embedded in a connection URL must be URL-safe: use
hexadecimal characters from `openssl rand -hex 32`. `APP_KEY` and
`DATA_ENCRYPTION_KEY` in this batch require exactly 32 ASCII characters; generate
those with `openssl rand -hex 16`. Sure's `SECRET_KEY_BASE` can be generated with
`openssl rand -hex 64`. Changing initialization variables does not rotate credentials
in an existing database volume.

Every Compose web listener in this batch binds to `127.0.0.1`. Access it on the
Docker host, through an SSH tunnel, or through an existing host reverse proxy.
For a proxy in another container, deliberately join the application's Docker network
and use its internal service/port; another container cannot use the host's loopback
binding. Set each browser URL to the actual origin users will open, and configure
HTTPS at the external proxy. Change conflicting host ports before deploying several
applications. Inline configs require Docker Compose 2.23.1+ (including Portainer's
Compose implementation).

MCP recognizes `DUFS_AUTH` and `DUMBDROP_PIN` as secrets. Supply their names using
`local_secrets` and replace `CHANGEME` on the deploying machine. A Dufs authentication
rule contains a username and password, and the DumbDrop PIN must be 4-10 digits.

| Application | Template / host port | Initial setup and data |
| --- | --- | --- |
| [2FAuth](https://docs.2fauth.app/) | Container / 8000 | Supply `APP_KEY` and browser `APP_URL`. Create the initial administrator, review registration, enable encryption of stored OTP secrets and preserve `/2fauth` plus the key. Bind mounts need UID/GID 1000. |
| [OliveTin](https://docs.olivetin.app/) | Compose / local 1337 | Includes an inline `date -u` action. Edit the stack config to define actions and authentication. Commands run inside the container; no host directories or Docker socket are mounted. |
| [Mazanoke](https://github.com/civilblur/mazanoke) | Container / 3474 | Serves a browser image optimizer. No database, account or persistent server data; images are processed on the browser device. |
| [Dufs](https://github.com/sigoden/dufs) | Container / 5001 | Supply `DUFS_AUTH`, e.g. `alice:YOUR_PASSWORD@/:rw`, without an anonymous rule. File operations are enabled inside `/data`; retain that volume. |
| [Hoppscotch](https://docs.hoppscotch.io/documentation/self-host/community-edition/install-and-build) | Compose / local 3000 | Supply browser and WebSocket origins, PostgreSQL password and 32-character encryption key. A one-shot Prisma migration gates startup. Visit `/admin` for initial onboarding and auth/mail setup, then `/` for the client. Retain PostgreSQL, `/data` signing keys and the encryption key. |
| [Rybbit](https://rybbit.com/docs/self-hosting) | Compose / local 3005 | Supply the browser origin and five separate secrets: PostgreSQL, ClickHouse admin, restricted ClickHouse query user, Redis and authentication signing key. Create the initial account/organization, then set `DISABLE_SIGNUP=true`. Back up PostgreSQL, ClickHouse and Redis. Allow several GB RAM. |
| [Sure](https://github.com/we-promise/sure/blob/main/docs/hosting/docker.md) | Compose / local 3006 | Supply database/cache passwords and Rails signing secret. Web startup prepares the database; the worker waits for healthy web. Create the initial account and restrict signups in Settings > Self-Hosting > Onboarding. Set both Rails SSL flags to true behind an HTTPS-terminating proxy. Preserve database, Redis and uploaded files. |
| [LibreTranslate](https://docs.libretranslate.com/guides/installation/) | Compose / local 5000 | Downloads `en,pl,de,fr` models on first start. Change `LT_LOAD_ONLY` to reduce downloads. Keep the model volume. No API authentication is configured; use an authenticated proxy for remote access. |
| [LanguageTool](https://github.com/meyayl/docker-languagetool) | Compose / local 8081 | Community image recommended by upstream. Configure an editor/extension to use `/v2`; the server has no editor UI or built-in login. `JAVA_XMX` sets maximum heap; reserve additional host RAM. Optional n-gram downloads are disabled. |
| [OpenList](https://doc.oplist.org/guide/installation/docker) | Container / 5244 | Read the initial admin password from logs, or run `./openlist admin random` inside the container. Configure storage providers and guest permissions. Preserve `/opt/openlist/data`; bind mounts need UID/GID 1001. |
| [Slink](https://docs.slinkapp.io/) | Container / 3004 | Set the exact browser `ORIGIN`. Sign up, then run `slink user:activate --email=YOUR_EMAIL` and `slink user:grant:role --email=YOUR_EMAIL ROLE_ADMIN` inside the container. Keep user approval enabled and preserve both data/image volumes. |
| [Jelu](https://bayang.github.io/jelu-web/) | Container / 11111 | Create the first user on a trusted network. Retain config, SQLite, cover images and imports. This tracks reading history rather than serving ebook files. |
| [DumbDrop](https://github.com/DumbWareio/DumbDrop) | Container / 3003 | Set a private 4-10 digit `DUMBDROP_PIN` and full `BASE_URL` with trailing slash. Keep `/app/uploads`. Public listing/deletion is disabled; use HTTPS and suitable proxy authentication for sensitive uploads. |
| [Bar Assistant](https://docs.barassistant.app/setup/) | Compose / local 3007 | Set browser origin, 32-character app key and independent search key. One gateway serves Salt Rim, `/bar/` API and `/search/` Meilisearch. Register, create a bar and restrict further registration if appropriate. Preserve the entire bar-data directory (SQLite, images, catalog) and search volume. Uses file cache/sessions; Redis is omitted. |
| [Ryot](https://docs.ryot.io/) | Compose / local 8001 | Supply browser origin, hexadecimal PostgreSQL password and admin token. Complete onboarding and configure metadata-provider API tokens as needed. Preserve PostgreSQL and the token. Optional Pro features and file/S3 storage require separate setup. |
| [LinkAce](https://www.linkace.org/docs/v2/setup/setup-with-docker/) | Compose / local 8084 | Set browser URL, 32-character app key and database/root/cache/search credentials. Run the four setup commands below. Preserve MariaDB, Redis, search and application storage. |
| [Paperless-AI](https://github.com/clusterzx/paperless-ai) | Compose / local 3008 | Complete the local setup wizard with an existing Paperless-ngx API URL/token and a model provider. Paperless-ngx, Ollama and models are not deployed. Preserve `/app/data`, which includes stored settings. |
| [FileFlows](https://fileflows.com/docs/installation/docker/) | Compose / local 19200 | CPU server plus internal worker. Complete onboarding and test flows on disposable files. Put media into the managed `/media` volume or deliberately add a source bind mount. Preserve data, logs and media; `/temp` is scratch. GPU passthrough is omitted. Some features are paid. |
| [Maintainerr](https://docs.maintainerr.info/) | Container / 6246 | Configure media-server and optional Radarr/Sonarr connections in the UI. Review rules and retention before enabling removal actions, which can delete media. Preserve `/opt/data`; bind mounts need UID/GID 1000. |
| [Dispatcharr](https://dispatcharr.github.io/Dispatcharr-Docs/installation/) | Container / 9191 | AIO image bundles PostgreSQL and Redis. Create the initial administrator from a private/local network, import authorized playlists/EPG, and retain `/data`. Keep both mapped ports and `DISPATCHARR_PORT` in sync. GPU passthrough is omitted. |

## LinkAce first start

With environment values supplied, run these commands in the LinkAce `app` container
(or its Portainer console). These are the upstream alternative to the web installer,
which otherwise expects a writable `.env` file:

```sh
php artisan migrate --force
php artisan search:setup
php artisan setup:complete
php artisan registeruser --admin
```

Complete the upstream post-installation checklist for cron, mail, search indexing,
visibility and backups. The image includes the web/PHP supervisor; it does not
schedule a host cron job for you.

These templates create new deployments. They do not upgrade or migrate existing
application volumes automatically. Image references and platform manifests were
checked against public registries; Compose/MCP checks validate deployment plans
without starting the twenty application stacks.
