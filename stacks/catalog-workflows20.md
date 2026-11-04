# Spoolman–Temporal setup guide

These twenty templates use published images pinned to reviewed SHA-256 digests.
Registry manifests, image startup metadata, official website titles and logo
content were checked on 2026-11-04. Cal.diy's compatibility image and the Taiga
application images require Linux AMD64. The remaining application images provide
AMD64 and ARM64 manifests; individual CPU and host requirements still apply.
No Docker engine was available during verification: checks cover the generated
feed, PHP MCP plans, Docker Compose configuration and embedded script syntax.
Running services were not tested.

Supply every required variable before deployment. Generate separate passwords
and retain them with backups. Use hexadecimal secrets where a password appears
in a URL, JSON or configuration string. Database passwords stored during first
initialization do not change when an environment variable is edited later.
Use Compose 2.23.1 or newer for inline configurations, select an isolated project
directory and run `docker compose config` before starting a stack.

Compose listeners use host loopback except Lyrion's selected LAN address and
Scrypted's host networking. Use an SSH tunnel or an HTTPS proxy on the Docker
host for remote access. A proxy or client in another container needs an explicit
network route. Single-container templates use Portainer's port mapping controls.
Ports shown below are defaults and can conflict when multiple apps are deployed.

| Application | First start and persistent data | Official reference |
| --- | --- | --- |
| Spoolman | Open container port 8000, add vendors/filaments/spools and configure your printer integration. Preserve `/home/app/.local/share/spoolman`. There is no built-in authentication; use a trusted network or an authentication proxy. | [Installation](https://github.com/Donkie/Spoolman/wiki/Installation) |
| Cal.diy / Cal.com | **Compatibility template:** the `calcom/cal.diy` registry had no public tags when reviewed, so this uses published `calcom/cal.com:v5.6.19`, which predates the current Cal.diy tree. AMD64 only. Set the final HTTPS `CALCOM_URL`, SMTP, `NEXTAUTH_SECRET` and an exactly 32-character `CALENDSO_ENCRYPTION_KEY`. Startup replaces the compiled URL, applies migrations and seeds the app store. Complete the first-user wizard. Preserve PostgreSQL and both secrets. API v2 and Prisma Studio are omitted. | [Reviewed Docker packaging](https://github.com/calcom/docker/tree/8aca82269a1b3cb51187d0fc1a5e86f5dcbe6a3d) and [current Cal.diy docs](https://www.cal.diy/docker) |
| WeKan | Set the browser URL and separate MongoDB root/application passwords. The init script creates a limited application user; polling is enabled for the standalone MongoDB 7 backend. Create the first account before sharing access, then review registration settings. Keep database and `/data` attachment volumes. | [MongoDB 7 Compose](https://github.com/wekan/wekan/blob/main/docker-compose-mongodb-v7.yml) |
| Taiga | AMD64, a final HTTPS hostname and SMTP are required. The backend initializes migrations/static files before workers start. Create the administrator with the command below. Forward WebSockets as well as HTTP. Preserve PostgreSQL, media, static files and both RabbitMQ volumes. | [Production setup](https://docs.taiga.io/setup-production.html) |
| Fider | Set the final HTTPS URL, database password, signing secret and working SMTP. Email sign-in links complete first-site setup. Database migrations run on startup; PostgreSQL also stores attachments. | [Hosting](https://docs.fider.io/hosting-instance/) |
| Lemmy | Choose a permanent federation hostname served through HTTPS on port 443. Set SMTP and independent database, pict-rs and administrator credentials. JSON values must not contain quotes/backslashes. Initial site/admin settings apply only to an empty database. Preserve PostgreSQL, images and themes; review registration and federation before opening the site. | [Docker installation](https://join-lemmy.org/docs/administration/install_docker.html) |
| Movary | Supply your TMDB API key, open container port 8080 and create the initial administrator. Passwords require at least 15 characters. Startup handles SQLite migrations and background jobs. Keep `/app/storage`; optional SMTP enables password resets. | [Docker installation](https://docs.movary.org/install/docker/) |
| Lyrion Music Server | Select a real host LAN IP, an existing absolute music directory and appropriate PUID/PGID. Music is mounted read-only. Open port 9000, select `/music` in the wizard and enable authentication. TCP/UDP 3483 and CLI 9090 are restricted to the selected address; players may need the server IP entered manually. Keep config/playlists. MCP separately asks for approval to read the host directory. | [Official image](https://hub.docker.com/r/lmscommunity/lyrionmusicserver) |
| Komf | Connect an existing reachable Komga URL and account. The local API has no authentication; event processing is initially disabled. Manual metadata matching uses the supported browser integration. Configuration allows API updates only, without media mounts or ComicInfo writes. Keep `/config`. Kavita needs a separate configuration. | [Configuration](https://github.com/Snd-R/komf) |
| Recyclarr | Connect Sonarr v4 and its API key. The supplied daily job updates quality/file-size definitions only. Preview with the command below before expanding the configuration to profiles/formats or Radarr. Keep `/config`; no web port is exposed. Uses upstream tag `8`, because no `latest` tag is published. | [Docker installation](https://recyclarr.dev/guide/installation/docker/) |
| Scrypted | Requires Linux host networking and separate MCP host-access approval. Create the administrator at `https://HOST:10443` over a trusted LAN connection; the initial certificate is self-signed. Follow upstream Avahi conflict guidance. Keep `/server/volume`. Camera plugins, hardware devices, NVR storage and automatic updates are configured separately; some NVR features are paid. | [Installation](https://docs.scrypted.app/installation.html) |
| DbGate | Set `LOGIN` and a unique `PASSWORD`, then open container port 3000. Add existing database connections in the UI and preserve `/root/.dbgate`. Configure HTTPS before remote access. Custom shell scripting remains disabled by default; some features require a premium license. | [Environment settings](https://docs.dbgate.io/dbgate/customization/env-variables/index.html) |
| Apache CouchDB | Set administrator credentials, open `http://HOST:5984/_utils/` and complete **Setup → Configure as Single Node** to create system databases. Keep `/opt/couchdb/data`. Clustering, replication and TLS require additional configuration. | [Docker installation](https://docs.couchdb.org/en/stable/install/docker.html) |
| ClickHouse | Set the database user/password. HTTP 8123 and native-client 9000 are local only. Keep both data and logs. Verify the host CPU meets current image requirements; the official ARM64 image does not support Raspberry Pi 4. | [Docker setup](https://clickhouse.com/docs/get-started/setup/self-managed/docker) |
| QuestDB | Set independent HTTP and PostgreSQL-wire credentials. Use container ports 9000 and 8812; unauthenticated InfluxDB TCP ingestion is disabled. Preserve `/var/lib/questdb`. Add HTTPS before remote web access. | [Docker deployment](https://questdb.com/docs/deployment/docker/) |
| OpenSearch | Private evaluation stack with matching OpenSearch/Dashboards 3.9.0 images. Supply a strong admin password and a different Dashboards service password. The init job replaces default users with the supplied admin/service accounts once; preserve its marker volume with the data. Host `vm.max_map_count` must be at least 262144 and several GB RAM are needed. API 9200 and UI 5601 are local only. **Bundled demo CA/admin certificates must be replaced before remote or production use.** | [Docker installation](https://docs.opensearch.org/latest/install-and-configure/install-opensearch/docker/) |
| NATS | Set a long hexadecimal client token. Client 4222 and unauthenticated monitoring 8222 stay local. Preserve JetStream data; core NATS messages are transient unless clients explicitly use streams. One node provides no replication redundancy. Add TLS/accounts before remote use. | [Docker guide](https://docs.nats.io/running-a-nats-service/nats_docker) |
| Redpanda | Private single-broker development stack. Set the bootstrap admin password; SASL protects Kafka and the Admin API requires authentication. Console receives those credentials but has no separate browser login. Kafka 19092, Admin API 9644 and Console 8082 stay local. Advertised external Kafka address is `localhost`; remote clients need deliberate address/TLS changes. Preserve broker data. | [Docker quick start](https://docs.redpanda.com/current/get-started/quick-start/) |
| Prefect | Set the public UI URL and independent database, Redis and API passwords. Server, background services and a process worker share authenticated dependencies. UI/API 4200 are local; sign in as `admin` with the API password. The `local-pool` worker runs trusted submitted flow code without a Docker socket. Keep PostgreSQL, Redis and flows; install task-specific dependencies deliberately. | [Docker Compose guide](https://docs.prefect.io/v3/advanced/docker-compose) |
| Temporal | Private single-node server with separate persistence/visibility databases. Schema jobs finish before the server starts; a second job creates namespace `default` with 72-hour retention. Set the browser UI URL and database password. gRPC 7233 and UI 8089 are local and have no application authentication. Deploy SDK workers separately. Preserve PostgreSQL and follow the schema/server upgrade order. Configure TLS/authentication before remote use. | [Self-hosted deployment](https://docs.temporal.io/self-hosted-guide/deployment) |

## Manual setup commands

Run these on the Docker host with the matching Compose project selected:

```sh
# Taiga: create the administrator after the backend becomes healthy.
docker compose exec taiga-back python manage.py createsuperuser

# Recyclarr: inspect proposed Sonarr changes before a manual synchronization.
docker compose exec recyclarr recyclarr sync sonarr --preview
```

OpenSearch initializes its internal users only when the `security-state` marker
is absent. Change later passwords through the supported security tools/API and
update dependent configuration together. Preserve the marker with data backups.
Do not treat environment changes as password rotation.

## Configuration sources and licenses

Taiga's stack/gateway derive from [taiga-docker](https://github.com/taigaio/taiga-docker);
its MPL 2.0 license is retained in `taiga/LICENSE.upstream`. The Lemmy gateway is
adapted from [lemmy-ansible](https://github.com/LemmyNet/lemmy-ansible), with its
AGPL 3.0 license in `lemmy/LICENSE.upstream`. Cal.com's reviewed Docker packaging
license is in `cal-diy/LICENSE.upstream`; application and enterprise features have
their own licenses. Prefect's Apache 2.0 license is in `prefect/LICENSE.upstream`.
Temporal's MIT license is in `temporal/LICENSE.upstream`; schema/service setup
follows [temporal-server-operations](https://github.com/temporalio/temporal-server-operations).
