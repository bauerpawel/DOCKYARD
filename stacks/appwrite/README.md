# Appwrite 2.6.2

This is a new PostgreSQL installation adapted from the official
[2.6.2 Compose definition](https://github.com/appwrite/appwrite/blob/2.6.2/docker-compose.yml)
and its production variable defaults. Images are pinned by registry digest.
ClickHouse configuration and initialization are embedded as Compose configs;
there is no source checkout, extra configuration file or installer-generated
`.env` dependency. Docker Compose 2.23.1+ is required for inline configs.

Set `_APP_DOMAIN` to the public hostname without a scheme, path or port. Set a
private `_APP_DB_PASS` and generate a different value with `openssl rand -hex 32`
for each of `_APP_OPENSSL_KEY_V1`, `_APP_NOTIFICATIONS_TRACKING_SECRET`,
`_APP_EXECUTOR_SECRET`, `_APP_JOBS_SECRET`, `_APP_GEO_SECRET` and `_APP_USAGE_PASS`.
The ClickHouse password must remain hexadecimal because it appears in a URL.
Keep database credentials and all encryption/signing secrets across updates.

Portainer supplies these fields directly. For local Compose, put the same values
in a private `.env` and run:

```sh
docker compose --env-file .env -f stacks/appwrite/docker-compose.yml up -d
```

The HTTP and HTTPS host ports default to 8081 and 8443, with MQTT TLS on 8883 and
MQTT-over-WebSocket TLS on 8084. Configure public DNS and TLS routing separately.
Route the domain and the `functions.<domain>` and `sites.<domain>` wildcard names
to the appropriate listeners. Keep HTTPS enforcement enabled for public use;
disable it only for an intentional local HTTP test. When terminating TLS in an
external proxy, forward the original request scheme and use a trusted proxy path.
Set the optional SMTP fields when enabling mail delivery.

The API, realtime service, workers and scheduled tasks share the same PostgreSQL
account and encryption settings. The console is separate from the API. Optional
DocumentsDB, VectorsDB and embedding services stay disabled, matching the
production defaults; enabling those features requires their upstream services
and a separate configuration review.

Function runtimes require Docker socket access. The executor and orchestrator can
create containers; the executor also needs the shared temporary and build
storage mounts. Deploy this stack only on the intended Docker host. The explicit
`appwrite` and `runtimes` network names and `appwrite-builds` volume follow the
upstream runtime wiring: use one such installation per Docker host, or adapt all
matching network and volume settings together.

## Existing installations

This template does not migrate the old Appwrite 1.1.1/MariaDB stack. New named
volumes do not import the old `/portainer/Files/AppData/Config/appwrite` bind
mounts. Back up the old deployment and its encryption key, follow the
[upstream upgrade instructions](https://appwrite.io/docs/advanced/self-hosting/upgrade),
and review each supported version and database transition. Do not attach an old
MariaDB directory to PostgreSQL or generate a replacement key for existing data.

The upstream-derived configuration and ClickHouse initialization carry the
Appwrite BSD-3-Clause license in `LICENSE.upstream`.
