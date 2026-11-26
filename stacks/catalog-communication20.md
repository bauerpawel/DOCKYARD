# Rocket.Chat–MediaWiki setup guide

These twenty templates use published images pinned to reviewed SHA-256 digests.
Registry manifests, official website titles, logos and documentation links were
checked on 2026-11-26. Rundeck's image requires Linux AMD64; the remaining
application images provide AMD64 and ARM64 manifests. No Docker engine was
available during verification: checks cover the generated feed, PHP MCP plans
and the Docker Compose configuration parser. Running services were not tested.

Supply every required variable before deployment. Generate separate passwords
and keep them with backups. Use hexadecimal secrets where a password appears in a
URL or configuration file. Passwords stored during first initialization do not
change when an environment variable is edited later. Use Compose 2.23.1 or newer
for inline configurations and run `docker compose config` before starting a stack.

Compose web listeners use host loopback; docker-mailserver publishes its mail
ports on all interfaces. Use an SSH tunnel or an HTTPS proxy on the Docker host
for remote access. Single-container templates use Portainer's port mapping
controls. WUD (Docker socket), Photoview (photo directory) and docker-mailserver
(certificate directory) require separate MCP host-access approval.

| Application | First start and persistent data | Official reference |
| --- | --- | --- |
| Rocket.Chat | Set the exact HTTPS `ROCKETCHAT_URL`. A one-shot job initiates the MongoDB 8.0 replica set `rs0` before the server starts. The setup wizard creates the administrator and may offer Cloud registration. Forward WebSockets. Back up MongoDB with `mongodump`. | [Docker Compose](https://docs.rocket.chat/docs/deploy-with-docker-docker-compose) |
| Element Web | Point `ELEMENT_HOMESERVER_URL` and `ELEMENT_SERVER_NAME` at an existing homeserver such as Synapse. Serve Element on its own HTTPS hostname. It stores no data. | [Install](https://github.com/element-hq/element-web/blob/develop/docs/install.md) |
| Collabora Online (CODE) | Set `aliasgroup1` to the WOPI host origin with its port and an admin console password. TLS terminates at the reverse proxy; forward WebSockets and enter the URL in the file platform. Admin console: `/browser/dist/admin/admin.html`. | [CODE](https://www.collaboraonline.com/code/) |
| Adminer | Stores nothing; signs in with database credentials typed in the page. Attach it to a database network to reach other stacks. Keep it private. | [Official image](https://hub.docker.com/_/adminer) |
| Radicale | A one-shot job writes a bcrypt `/data/users` file for the first user only when the file is missing or empty. Later password changes edit that file. Keep the data volume. | [Documentation](https://radicale.org/v3.html) |
| Kanidm | Choose the permanent `KANIDM_DOMAIN`. A one-shot job creates a self-signed TLS pair; the proxy must connect over HTTPS. Recover the initial passwords with the commands below. LDAPS is not published. | [Installing the server](https://kanidm.github.io/kanidm/stable/installing_the_server.html) |
| LocalAI | CPU image. Set `LOCALAI_API_KEY`; without it the API is anonymous. Install models in the web UI; backends download on first use and need several GB. | [Container](https://localai.io/basics/container/) |
| Grafana Loki | Single-binary Loki on filesystem storage with Grafana provisioned for it. The Loki API has no authentication and stays on loopback. Add retention before the volume grows. No log collector is included. | [Docker install](https://grafana.com/docs/loki/latest/setup/install/docker/) |
| Kiwix Serve | Put `.zim` files in `/srv/kiwix`, readable by UID 1001, before starting; the container exits without them. Restart after adding archives. | [Docker](https://github.com/kiwix/kiwix-tools/blob/main/docker/README.md) |
| Photoview | Set an existing photo directory readable by UID 999 and a hex database password. The first visit creates the administrator; enter `/photos` as the path. Thumbnails fill the home volume. | [Docker installation](https://photoview.github.io/en/docs/installation-docker/) |
| Gramps Web | Set `GRAMPSWEB_BASE_URL`. The wizard creates the owner; registration is off. The secret key is generated in the secret volume. Keep all volumes, especially tree, media, users and secret. | [Deployment](https://www.grampsweb.org/install_setup/deployment/) |
| SnappyMail | Read the generated admin password with the command below and change it at `/?admin`, then add mail domains. Keep `SECURE_COOKIES=true` behind HTTPS. | [Docker image](https://github.com/the-djmaze/snappymail/tree/master/.docker/release) |
| docker-mailserver | Needs a static public IP, matching reverse DNS, an MX record and inbound port 25. Obtain a certificate for `DMS_HOSTNAME` first. A one-shot job creates the first mailbox only when no account exists. Generate DKIM with the command below and publish DKIM, SPF and DMARC records. | [Usage](https://docker-mailserver.github.io/docker-mailserver/latest/usage/) |
| What's Up Docker | Signs in with the administrator seeded from `WUD_AUTH_ADMIN_USER` and `WUD_AUTH_ADMIN_PASSWORD`. It does not update containers unless you add a Docker trigger. | [Authentication](https://getwud.github.io/wud/docs/configuration/authentications/basic/) |
| Rundeck | AMD64 only. Inline `realm.properties` replaces the image's `admin/admin`. Keep `RUNDECK_STORAGE_PASSWORD`: key storage cannot be decrypted without it. Behind HTTPS set `RUNDECK_SERVER_FORWARDED=true`. The first start creates the schema and takes a few minutes. | [Docker](https://docs.rundeck.com/docs/administration/install/docker.html) |
| Restic REST Server | Create users with the command below. `--private-repos` is the default; add `--append-only` so clients cannot delete snapshots. | [Docker](https://github.com/restic/rest-server#docker) |
| OwnTracks Recorder | HTTP mode with MQTT off. The recorder has no authentication: publish it only through an authenticating HTTPS proxy and point the app at `/pub`. | [HTTP mode](https://github.com/owntracks/recorder#http-mode) |
| RSS-Bridge | Every feed URL needs `&token=` with `RSSBRIDGE_AUTHENTICATION_TOKEN`. All bridges are enabled; limit them with `RSSBRIDGE_SYSTEM_ENABLED_BRIDGES`. | [Installation](https://rss-bridge.github.io/rss-bridge/For_Hosts/Installation.html) |
| EspoCRM | Installs itself on the first start from the template values. The daemon service runs scheduled jobs. WebSocket notifications are not included. | [Docker installation](https://docs.espocrm.com/administration/docker/installation/) |
| MediaWiki | A one-shot job runs the installer on the first start and `update.php` on later starts. The admin password needs at least 10 characters. `LocalSettings.php` lives in the data volume; anonymous editing is allowed until you restrict it. | [Installing MediaWiki](https://www.mediawiki.org/wiki/Manual:Installing_MediaWiki) |

## Manual setup commands

Run these on the Docker host with the matching Compose project selected:

```sh
# Kanidm: print the initial passwords for both administrative accounts.
docker compose exec kanidm kanidmd recover-account admin
docker compose exec kanidm kanidmd recover-account idm_admin

# docker-mailserver: generate DKIM keys, then publish the printed DNS records.
docker compose exec mailserver setup config dkim

# SnappyMail: read the generated admin password.
docker exec CONTAINER cat /var/lib/snappymail/_data_/_default_/admin_password.txt

# Restic REST Server: create a user; the command prompts for the password.
docker exec -it CONTAINER create_user NAME
```
