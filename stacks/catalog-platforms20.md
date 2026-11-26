# wg-easy–Endurain setup guide

These twenty templates use published images pinned to reviewed SHA-256 digests.
Registry manifests, official website titles, logos and documentation links were
checked on 2026-11-26. The pretix and Overleaf images require Linux AMD64; the
remaining images provide AMD64 and ARM64 manifests. No Docker engine was
available during verification: checks cover the generated feed, PHP MCP plans,
the Docker Compose configuration parser and parsing of the inline configuration
files. Running services were not tested.

Supply every required variable before deployment. Generate separate passwords
and keep them with backups. Use hexadecimal secrets where a password appears in a
URL or configuration file. Values stored during first initialization do not
change when an environment variable is edited later. Use Compose 2.23.1 or newer
for inline configurations and run `docker compose config` before starting a stack.

Compose web listeners use host loopback. wg-easy publishes its WireGuard UDP
port and OneDev its SSH port on all interfaces. Use an SSH tunnel or an HTTPS
proxy on the Docker host for remote access. Single-container templates use
Portainer's port mapping controls. wg-easy (`NET_ADMIN`), CrowdSec (host log
directory) and Coder (Docker socket) require separate MCP host-access approval.

| Application | First start and persistent data | Official reference |
| --- | --- | --- |
| wg-easy | Needs WireGuard in the host kernel (Linux 5.6+). Set `WG_HOST` and forward UDP `WG_PORT`. The first start skips the wizard and creates the administrator from the template; later changes are ignored. Set `WG_INSECURE=true` only to sign in over plain HTTP through a tunnel. IPv6 is disabled. Keep the config volume. | [Documentation](https://wg-easy.github.io/wg-easy/latest/) |
| CrowdSec | Reads `auth.log`, `syslog`, `secure` and `messages` from `CROWDSEC_LOG_DIR`; journald-only hosts need rsyslog or a journald acquisition. Detection only: install `crowdsec-firewall-bouncer` on the host with `api_url http://127.0.0.1:8080` and `CROWDSEC_BOUNCER_KEY`. Shares signals with the community API by default. | [Docker](https://docs.crowdsec.net/u/getting_started/installation/docker) |
| copyparty | One account with full rights on the files volume; anonymous access is off. WebDAV uses the same address. Mount a host folder at `/w` by editing the stack. | [Docker](https://github.com/9001/copyparty/tree/hovudstraum/scripts/docker) |
| Cloudreve | **The first registered account becomes the administrator**; register right after the first start. Aria2 offline downloads are not configured. Keep data and database volumes. | [Docker Compose](https://docs.cloudreve.org/en/overview/deploy/docker-compose) |
| Kutt | SQLite in `/var/lib/kutt`. Create the administrator on the first visit. Set `TRUST_PROXY=true` only behind a proxy. Add `MAIL_*` variables for password resets. | [Configuration](https://github.com/thedevs-network/kutt#configuration) |
| Coder | `CODER_ACCESS_URL` must be reachable by browsers and workspace containers. Set `CODER_DOCKER_GID` with the command below. Create the first administrator and add the Docker starter template. Telemetry is off. | [Docker](https://coder.com/docs/install/docker) |
| OneDev | The wizard creates the administrator and asks for the server URL. The Docker socket is not mounted; connect an agent for CI jobs. Git over SSH uses `ONEDEV_SSH_PORT`. | [Docker](https://docs.onedev.io/installation-guide/run-as-docker-container) |
| Flagsmith | Migrations run in a one-shot job. Create the first superuser at `/api/v1/users/config/init/` before anyone else can. Registration without an invitation is off; telemetry is off. | [Docker](https://docs.flagsmith.com/deployment-self-hosting/hosting-guides/docker) |
| Apache Kafka | Single KRaft node without authentication or TLS, so the client port stays on loopback and is advertised as `localhost`. Containers on the stack network use `kafka:19092`. Kafka UI requires a login. No replication. | [Official image](https://hub.docker.com/r/apache/kafka) |
| JupyterLab | Token login. `/home/jovyan` is persisted. Anyone with the token runs code in the container. | [Docker Stacks](https://jupyter-docker-stacks.readthedocs.io/en/latest/using/common.html) |
| Overleaf Community Edition | AMD64 only. A one-shot job initiates the MongoDB replica set. Create the first administrator at `/launchpad`. Compiles are not sandboxed; give accounts only to trusted users. Set `OVERLEAF_SECURE_COOKIE=true` once HTTPS works. Install extra TeX packages with `tlmgr` and repeat after upgrades. | [Installation](https://docs.overleaf.com/on-premises/installation) |
| Calibre-Web Automated | **Default login `admin`/`admin123`; change it immediately.** The library and ingest folders are under `/srv/calibre-web-automated`; ingested files are removed after processing. | [Quick install](https://github.com/crocodilestick/Calibre-Web-Automated#quick-install) |
| openHAB | Create the administrator on the first visit. Bridge networking limits discovery; add things by IP or configure host networking separately. USB adapters need device access. | [Docker](https://www.openhab.org/docs/installation/docker.html) |
| Misskey | `MK_URL` is permanent. The setup password protects the first administrator signup. A one-shot job gives the files volume to UID 991. Review registration before opening the instance. | [Docker](https://misskey-hub.net/en/docs/for-admin/install/guides/docker/) |
| pretix | AMD64 only. A one-shot job applies migrations and replaces the built-in `admin@localhost`/`admin` login while the default password is still set. Working SMTP is required. The cron service runs periodic tasks every 10 minutes. | [Docker](https://docs.pretix.eu/self-hosting/installation/docker_smallscale/) |
| InvenTree | The first start applies migrations, collects static files and creates the administrator. Caddy serves static files and checks access to media. Plugins are disabled. | [Docker](https://docs.inventree.org/en/stable/start/docker/) |
| Typesense | Every request needs the admin key in `X-TYPESENSE-API-KEY`; create scoped search-only keys for browsers. | [Install](https://typesense.org/docs/guide/install-typesense.html) |
| Jaeger | OTLP gRPC 4317, OTLP HTTP 4318 and UI 16686 stay on loopback without authentication. Traces are kept in Badger for `JAEGER_RETENTION`. Containers elsewhere need this stack's network. | [Getting started](https://www.jaegertracing.io/docs/latest/getting-started/) |
| Factorio Server | Forward UDP 34197. The first start creates `_autosave1`. Edit `/factorio/config/server-settings.json` for the name, password and visibility; public listing needs a factorio.com token. | [Image](https://github.com/factoriotools/factorio-docker#readme) |
| Endurain | `ENDURAIN_HOST` must match the browser address exactly. The first administrator is created with the setup token from the log (command below); passwords need 15+ characters. Keep both keys. | [Quick start](https://docs.endurain.com/getting-started/quick-start/) |

## Manual setup commands

Run these on the Docker host with the matching Compose project selected:

```sh
# Coder: find the group that owns the Docker socket for CODER_DOCKER_GID.
stat -c %g /var/run/docker.sock

# CrowdSec: inspect decisions and parser metrics.
docker compose exec crowdsec cscli decisions list
docker compose exec crowdsec cscli metrics

# Endurain: read the one-time setup token for the first administrator.
docker compose logs endurain | grep setup_token

# Overleaf: install additional TeX Live packages.
docker compose exec overleaf tlmgr install PACKAGE
```
