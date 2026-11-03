# Setup for Dockhand through Cleanuparr

This batch adds twenty applications: eighteen local Compose stacks and two container
templates. Application and companion images are pinned by SHA-256 digest. No source
build or external Compose repository is needed. Checkmk's reviewed image is AMD64-only;
the other application images have AMD64 and ARM64 manifests.

For Portainer, supply the environment fields shown by the template. For local Docker,
keep them in a private `.env` and select the stack, for example:

```sh
docker compose --env-file .env -f stacks/erpnext/docker-compose.yml config
docker compose --env-file .env -f stacks/erpnext/docker-compose.yml up -d
```

Use different credentials for each secret and retain encryption/signing keys with
backups. Passwords interpolated into a database/Redis URL or inline YAML must be
URL/YAML-safe: hexadecimal output from `openssl rand -hex 32` is suitable.
ZITADEL's master key must be exactly 32 ASCII characters (`openssl rand -hex 16`).
Typebot requires a 32-character encryption secret (`openssl rand -base64 24`).
Chatwoot's signing secret can be generated with `openssl rand -hex 64`.
Changing initialization variables does not rotate credentials in existing volumes.

Most management ports bind to `127.0.0.1`. Access those ports on the Docker host,
through an SSH tunnel or through an existing host reverse proxy. For a proxy in a
different container, deliberately join the application's network and route to its
internal service/port; another container cannot use the host loopback binding.
Match browser-facing URLs to DNS, HTTPS and the address users actually open.
Inline configs require Docker Compose 2.23.1+ in the deployment environment.

MCP requires separate `allow_privileged` approval for Dockhand's Docker socket,
phpIPAM's `NET_ADMIN`/`NET_RAW`, Music Assistant's host networking, and Borgmatic's
user-selected host-directory mount. Adding these templates does not connect to or
start any of those services. MCP recognizes `BORG_PASSPHRASE` as a secret: list it in
`local_secrets` and replace `CHANGEME` on the deploying machine.

| Application | Default host listeners | First start and persistent data |
| --- | --- | --- |
| [Dockhand](https://dockhand.pro/manual/) | Local 3010 | Create the initial administrator over a trusted connection. The mounted Docker socket grants control over the host. Preserve `/app/data`, including SQLite and managed stack files. BSL licensing applies; some enterprise features are paid. |
| [Zoraxy](https://github.com/tobychui/zoraxy/tree/main/docker) | Local admin 8002; public TCP 80/443 and UDP 443 | Create the administrator, configure proxy routes/DNS and certificate validation. Docker discovery/socket access is omitted. Preserve config/plugins and certificate material. Change conflicting HTTP/HTTPS ports before deployment. |
| [Checkmk Community](https://docs.checkmk.com/latest/en/introduction_docker.html) | Local web 8086; agent TCP 8000 | AMD64-only. Set `CMK_PASSWORD`, then visit `/cmk/` and log in as `cmkadmin`. Keep `/omd/sites`; temporary site files use UID/GID 1000 tmpfs. Configure monitored hosts/agents/SNMP separately. Restrict the agent receiver to intended systems. |
| [phpIPAM](https://github.com/phpipam-docker/phpipam-docker) | Local 8085 | Import the schema into the pre-created `phpipam` database/user on `db`, using `DB_PASSWORD`. Change `Admin` / `ipamadmin` immediately, then disable the installer. Both web and discovery worker have the upstream-required network capabilities. Preserve MariaDB and custom logos. |
| [VictoriaMetrics](https://docs.victoriametrics.com/victoriametrics/single-server-victoriametrics/) | Local 8428 | VMUI is at `/vmui/`; Prometheus remote-write endpoint is `/api/v1/write`. Connect collectors through a private network or authenticated proxy. No collector or API authentication is included. Retain metrics; retention defaults to three months. |
| [SonarQube Community Build](https://docs.sonarsource.com/sonarqube-community-build/server-installation/pre-installation/linux) | Local 9001 | Set PostgreSQL password and configure host kernel limits before startup. Change `admin` / `admin`. Install a project/CI scanner separately. Preserve PostgreSQL, analysis data and extensions. |
| [Apache Answer](https://answer.apache.org/docs/installation/) | TCP 9080 | Complete `/install` on a trusted network, select SQLite, set the site URL and create the administrator. Preserve `/data`. Add HTTPS/mail as needed. |
| [Chatwoot](https://www.chatwoot.com/deploy) | Local 3009 | Supply browser origin and database/cache/signing secrets. The preparation service runs `db:chatwoot_prepare` before web/Sidekiq. Create the initial account and disable public account signup. Add SMTP/channel credentials for email or external channels. Preserve PostgreSQL with pgvector, Redis and attachments. |
| [GLPI](https://github.com/glpi-project/docker-images) | Local 8087 | Supply database/user/root passwords and wait for automatic installation. Change `glpi` / `glpi` and change or disable every other default account. The image includes scheduled tasks. Keep MariaDB and `/var/glpi`, including configuration, files and marketplace data. |
| [Kanboard](https://docs.kanboard.org/v1/admin/docker/) | Local 8088 | Change `admin` / `admin`; configure mail/HTTPS if needed. Keep SQLite/attachments and plugin volumes. Web plugin installation is disabled. Upstream is in maintenance mode. |
| [Typebot](https://github.com/baptisteArno/typebot.io) | Local builder 3011; viewer 3012 | Requires separate browser hostnames for builder/viewer, real SMTP credentials, admin email and encryption/database/cache secrets. Different ports on one hostname do not isolate cookies. Builder startup migrates the database; viewer waits for it. S3 uploads/media are omitted and need external configuration. Preserve PostgreSQL, Redis and the encryption secret. See the bundled [upstream license](typebot/LICENSE.upstream). |
| [ERPNext](https://github.com/frappe/frappe_docker) | Local 3013 | Supply public URL, MariaDB root password, hexadecimal Redis password and initial Administrator password. Configuration and site creation gate backend/workers/scheduler startup. The internal site name is `frontend`; its external URL comes from `ERPNEXT_URL`. Preserve MariaDB, sites with encryption keys, Redis and logs. |
| [Owncast](https://owncast.online/docs/getting-started/install/container/) | Local web 8089; local RTMP 1935 | Visit `/admin`. Change `admin` / `abc123` and the separate `abc123` stream key before publishing access. Configure HTTPS and deliberately open RTMP or use a tunnel for remote encoders. Preserve `/app/data`. |
| [MediaMTX](https://mediamtx.org/docs/kickoff/install) | TCP 8554, 1936, 8888, 8889; UDP 8189 | Set a client-reachable server IP/DNS and independent hexadecimal credentials. Username `publisher` may publish; `viewer` may read/play back. RTSP uses TCP; HTTP APIs, SRT and recording are disabled. Browser WebRTC requires reachable media/NAT paths and compatible codecs. |
| [Music Assistant](https://www.music-assistant.io/installation/) | Host network / 8095 | Requires a supported 64-bit host, at least 2 GB RAM and speakers on the same layer-2 network. Complete initial authentication and add providers. Keep `/data`. No Docker socket, extra capabilities or SMB/NFS mounting privileges are granted. Add local music explicitly as a read-only mount if needed. |
| [GameVault](https://gamevau.lt/docs/server-docs/setup/docker-compose/) | Local 8090 | Supply PostgreSQL and initial administrator credentials. Add your own DRM-free installers to `/files`, or deliberately add an existing-library bind mount. Metadata provider credentials are separate. Preserve PostgreSQL, games, media and saves. |
| [Borgmatic](https://github.com/borgmatic-collective/docker-borgmatic) | None | Select an existing source directory and supply the repository passphrase. An idempotent one-shot initializer creates the encrypted local repository, then daily backups run at 02:00 by default. Keep repository/key/state volumes and passphrase. Test recovery and configure off-site storage separately. Live database files require database-aware dumps/hooks. |
| [ZITADEL](https://zitadel.com/docs/self-hosting/deploy/compose) | Local gateway 8091 | Requires DNS and an existing HTTPS reverse proxy. Set external domain/port, 32-character master key, PostgreSQL password, cookie secret and initial admin email/password. Visit `/ui/console` and sign in with that email. Keep PostgreSQL and the generated login-client token volume. The master key must remain unchanged. |
| [Profilarr](https://github.com/Dictionarry-Hub/profilarr) | Local 6868 | Requires Linux kernel 3.17+, compatible existing Radarr/Sonarr and their API credentials. Set the browser origin. Includes a private parser service for testing formats/profiles. Review changes before running sync/rename/upgrade jobs. Preserve `/config`. |
| [Cleanuparr](https://cleanuparr.github.io/docs/) | Local 11011 | Complete setup/authentication, then connect existing download/Arr services. Review removal rules before automation. No host downloads folder is mounted by default; add one deliberately only when needed. Preserve `/config`. |

## ERPNext initialization and upgrades

The MariaDB and both Redis services must be healthy before the configurator writes
the shared site configuration. The site-creation service then installs ERPNext,
sets the public URL and writes `sites/frontend/.dockyard-initialized` only after
successful completion. On later starts, that marker prevents creating the site again.
If a partial `site_config.json` exists without the marker, initialization fails visibly.
Inspect logs and the existing site/database before retrying; do not delete production
volumes to clear an initialization error.

This is a single-site deployment of the published Frappe/ERPNext image. It is not the
upstream disposable demo and has no shared `admin` database/application password.
Custom apps require a separately built/reviewed image. Set company, tax, localization,
email, backups and other production settings through ERPNext administration. Existing
sites need the upstream backup/migration procedure when changing image versions;
the initialization marker does not run upgrades or rotate existing passwords.

## ZITADEL routing

The local Caddy gateway routes `/ui/v2/login/` to the Login UI and all canonical
API/console routes to the API using h2c. `/api/` is a stripped-prefix alias and `/`
redirects to the login page. The external HTTPS proxy must preserve the public Host
header and support the HTTP/2 requirements of clients that use gRPC. TLS terminates
at that external proxy; the stack's internal gateway/API connection is cleartext h2c.

The API reads its master key from the environment using `--masterkeyFromEnv` and
generates the Login service account PAT into a named volume. The Login UI mounts that
volume read-only. Keep the PAT private, plan its rotation/expiration and preserve it
with the database and keys. The initial administrator password must satisfy the
default complexity policy and is changed at first login.

The batch was checked using public registry manifests, upstream installation sources,
the Compose config parser and MCP deployment-plan tests. Those checks do not start
the twenty applications or provide an end-to-end test of their integrations.
