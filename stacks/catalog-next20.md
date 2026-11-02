# Setup for the next twenty applications

These entries add Readeck through GlitchTip to the catalog. Three are single-container
templates; seventeen use local, self-contained Compose files. Every image is pinned by
digest, including companion services. No external stackfile or build context is needed.

Supply the environment fields shown by Portainer before deploying. In a local Docker
deployment, put those values in a private `.env` and use the selected stackfile:

```sh
docker compose --env-file .env -f stacks/tududi/docker-compose.yml config
docker compose --env-file .env -f stacks/tududi/docker-compose.yml up -d
```

Generate a different value for every secret. Unless a field specifies another format,
`openssl rand -hex 32` is suitable. Database passwords embedded in URLs or inline XML
must use hexadecimal characters. Keep credentials and encryption keys with backups;
changing an environment variable does not rotate the password of an existing database.

Several web ports bind to `127.0.0.1`. Access them on the Docker host, through an SSH
tunnel, or through an existing reverse proxy running on that host. A proxy in another
container cannot use the host loopback binding: explicitly attach it to the application's
Docker network and route to the service's internal port. Match public URLs, hostnames,
ports and HTTPS settings to the address users actually open. Change conflicting ports
before deploying several applications together.

For MCP, use `local_secrets` and replace `CHANGEME` on the deploying machine. The server
recognizes LibreChat's `CREDS_IV`, LibreNMS's SNMP community and GlitchTip's `EMAIL_URL`
as secrets, so their contents do not need to be sent to MCP. AnythingLLM and LibreNMS
require separate `allow_privileged` approval for the capabilities described below.

| Application | Template / default host port | First start and persistent data |
| --- | --- | --- |
| Readeck | Container / 8000 | Set allowed browser hosts and create the first administrator. Keep `/readeck`, including SQLite and saved articles. |
| Tududi | Compose / 3002 | Supply admin email/password, session secret, integration encryption key and public URL. Keep database, uploads and backups. |
| Easy!Appointments | Compose / 8080 | Set `BASE_URL` and both database passwords. Complete the installation wizard before publishing access. Keep MariaDB and application storage. |
| OpenCloud | Compose / local 9200 | Set the public HTTPS origin and initial admin password; configure a reachable HTTPS reverse proxy. Keep configuration and data together. |
| Seafile CE | Compose / 8080 | Set hostname/protocol, initial admin, database/cache passwords and JWT key. Keep MariaDB and `/shared`. |
| Directus | Compose / 8055 | Supply public URL, initial admin, signing secret and PostgreSQL password. Keep PostgreSQL, uploads and extensions. |
| NocoBase | Compose / 13000 | Supply initial root email/password, application/encryption keys and PostgreSQL password. Keep PostgreSQL and application storage. |
| LibreChat | Compose / local 3080 | Set public URL, MongoDB password and four encryption/session values. Create accounts, then disable registration. Keep MongoDB and file/settings volumes. |
| AnythingLLM | Compose / local 3001 | Set the initial single-user password and signing secrets. Complete onboarding and configure model providers. Keep all three volumes, including `storage/runtime.env`. |
| Dify | Compose / local 8080 | Configure the public HTTP/websocket origins and all secrets. Visit `/install`, supply the installation password and create the administrator. See the Dify section below. |
| RSSHub | Container / 1200 | Set an access key and include it in feed subscriptions. Uses memory caching; browser-dependent routes need additional services. |
| CommaFeed | Container / 8082 | Initial login is `admin` / `admin`; change it immediately. The H2 database lives in `/commafeed/data`. |
| MySpeed | Compose / local 5216 | Finish onboarding, configure an access password and choose a measurement schedule. Keep `/myspeed/data`. |
| WhoDB | Compose / local 8080 | Set the session encryption key, then connect to reachable existing databases. The template does not deploy database servers or mount host files. |
| Wakapi | Compose / 3000 | Set public URL/password salt and register. Point editor plugins at `PUBLIC_URL/api`. Disable signup after onboarding; keep `/data`. |
| Traccar | Compose / local 8082; TCP/UDP 5055 | Set the PostgreSQL password, create the first administrator and register devices. Keep PostgreSQL and logs. Only the Traccar Client/OsmAnd device listener is published. |
| LibreNMS | Compose / local 8000 | Supply database/cache passwords and device SNMP community. Create the administrator in the setup wizard. Keep MariaDB and shared `/data`. |
| Zabbix | Compose / local 8080; TCP 10051 | Set the database password. Initial login is `Admin` / `zabbix`; change it immediately. Keep PostgreSQL. Configure monitored hosts and their credentials separately. |
| Onetime Secret | Compose / local 3000 | Set the root secret, Valkey password and public hostname. Keep the Valkey volume and root secret together. |
| GlitchTip | Compose / local 8000 | Set public URL, signing secret and database password. Create the first user, organization and project. Keep PostgreSQL and uploads. |

## First-run details

Tududi creates its initial administrator only when the database has no users. Its
`ENCRYPTION_KEY` must contain exactly 64 hexadecimal characters. Behind a reverse proxy,
configure `TUDUDI_TRUST_PROXY` for the actual proxy rather than leaving direct-access
settings in place. SMTP, OIDC, Telegram and AI integrations are configured separately.

OpenCloud initializes its configuration once. Its dedicated volume initializer sets
ownership for UID/GID 1000, then the service runs without root. `OC_URL` must resolve
and be reachable from browsers and OpenCloud itself. The stack serves internal HTTP;
the external proxy provides HTTPS. Collabora and SMTP are not bundled.

Seafile's first start uses the database root password to create its three databases
and application user. Do not remove the initialized database/configuration volumes or
change their passwords on an ordinary update. SeaDoc, notification, metadata and AI
extensions are explicitly disabled because their services are not bundled. Caddy and
Docker socket access are not included. Set public HTTPS only when the reverse proxy
actually terminates TLS.

NocoBase supplies custom initial root credentials rather than upstream's default
account. Preserve `ENCRYPTION_FIELD_KEY` permanently. Directus similarly creates its
administrator during database bootstrap; changing initial credentials later does not
reset an existing account. Review Directus's Sustainable Core License and NocoBase's
commercial plugin terms before using features that require a license.

LibreChat uses the official pinned `v0.8.8` image; upstream classifies that release as
a prerelease. Its encryption formats are `CREDS_KEY=$(openssl rand -hex 32)` and
`CREDS_IV=$(openssl rand -hex 16)`. JWT signing and refresh secrets must be distinct.
MongoDB uses authentication and is not published; x86-64 hosts need the CPU features
required by MongoDB, including AVX. Users enter their own model-provider keys. Optional
Meilisearch, RAG/vector search, code execution and the separate admin panel are omitted.

AnythingLLM's initial single-user password is `AUTH_TOKEN`. Provider settings saved by
the application persist in `runtime.env` inside its storage volume; startup links that
file to the application's `.env`. The stack includes upstream's `SYS_ADMIN` capability
for Chromium browser tooling. It does not mount host devices or the Docker socket.
Configure an external model/embedding provider during onboarding, or enable multi-user
mode and create its administrator before sharing access.

LibreNMS includes a web application and polling dispatcher sharing the same `/data`
volume. Both receive `NET_ADMIN` and `NET_RAW` as in the upstream deployment. Device
SNMP credentials must also be configured on the monitored devices. Syslog/trap receivers
and an SMTP relay are omitted. Zabbix does not include agents; limit port 10051 to the
intended clients and configure Zabbix TLS when using untrusted networks.

Onetime Secret uses the upstream simple authentication mode with persistent,
password-protected Valkey. `ONETIME_SSL=true` and `SESSION_COOKIE_SECURE=true` expect
public HTTPS. For trusted HTTP-only testing, change both to `false`. SMTP must be
configured before relying on account verification or email delivery. Full authentication,
MFA/SSO, queue workers and a bundled TLS proxy are not included.

GlitchTip runs its all-in-one role and uses PostgreSQL for task queues/cache. Its
database sets `max_locks_per_transaction=512` for partitioned tables. Self-registration
is disabled after the first user. With `EMAIL_URL` unset, `consolemail://` writes email
messages to container logs; configure an SMTP URL for real delivery and keep log access
private. An SMTP URL can contain a password and is handled as a local MCP secret.

## Dify

The local stack adapts the official Dify 1.18.0 topology into one Compose file. It keeps
the API, web, worker, scheduler, collaboration websocket service, plugin daemon, agent
backend, both sandboxes and both outbound proxies. Nginx exposes the single web port.
PostgreSQL, Redis and Weaviate remain private. Model inference is not included.

Use Docker Compose 2.23.1 or newer, including the Compose implementation embedded in
Portainer, because configuration files are embedded with `configs.content`. Upstream's
minimum is two CPU cores and 4 GiB RAM; reserve additional resources for indexing,
plugins, agents and concurrent workloads.

- Set `DIFY_URL` to the exact public origin without a trailing slash, such as
  `https://ai.example.com`.
- Set `DIFY_SOCKET_URL` to its websocket counterpart, such as `wss://ai.example.com`.
- Set the installation password and every encryption, database, cache, vector,
  plugin, code-sandbox and agent secret exposed by the template. Do not reuse values.
- Configure the existing HTTPS proxy to forward websocket upgrades and the original
  `X-Forwarded-Proto`. Visit `/install`, provide `INIT_PASSWORD` and create the admin.
- Configure model providers and their credentials in Dify after onboarding.

Only the API runs database migrations; the other API-image services wait for its
health check. PostgreSQL initialization creates the separate `dify_plugin` database.
All workers share the application storage volume. Plugin debugging ports are not
published. The code and agent sandboxes attach only to internal networks; outbound
HTTP requests go through the upstream Squid ACLs. Private destination addresses are
denied except the specific internal API/file and agent routes required upstream.

Back up PostgreSQL, Redis, Weaviate, app storage, plugin storage, sandbox dependency/
configuration data, and agent home/workspace volumes. Retain every encryption secret.
Changing the root application or agent encryption keys can invalidate stored data.

The proxy scripts and Nginx configuration derive from Dify 1.18.0. Its modified Apache
license is preserved in [dify/LICENSE.upstream](dify/LICENSE.upstream); its additional
conditions cover multi-tenant operation and frontend branding.

## Verification scope

Registry manifests, platform listings, website titles and logo bytes were checked
before adding these entries. Repository tests exercise feed generation, MCP descriptions,
local secret handling, approval requirements, required Compose values and the real
Docker Compose configuration parser. They do not start services or validate live
application onboarding, provider connectivity, SMTP, DNS or reverse proxies.
