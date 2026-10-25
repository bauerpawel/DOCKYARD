# App stack setup

The catalog uses pinned releases for Open WebUI, Ollama, Pocket ID, Pangolin and
Karakeep. Their stackfiles are self-contained: supply environment variables in
Portainer or in a local `.env`, then deploy the selected stack. Backrest and BentoPDF
are single-container templates in `apps/`.

Change web ports if deploying multiple applications that default to port 3000.
Keep secrets and persistent volumes across updates. No models are downloaded until
you select one. CPU operation is the default for both Ollama deployments.

## Open WebUI and Ollama

Set `WEBUI_SECRET_KEY` to the output of `openssl rand -hex 32`. The Open WebUI
stack connects to its own Ollama service at `http://ollama:11434`; the model API
is not published on the host. Open the UI on port 3000, create the first administrator
account on a trusted network, then download a model in the administrator settings.

The standalone Ollama stack exposes port 11434 on `127.0.0.1`. On the Docker host:

```sh
docker compose -f stacks/ollama/docker-compose.yml up -d
docker compose -f stacks/ollama/docker-compose.yml exec ollama ollama run llama3.2
```

For NVIDIA GPUs, install the [NVIDIA Container Toolkit](https://docs.ollama.com/docker)
on the host and add this reservation to the **ollama service** in the chosen stack:

```yaml
deploy:
  resources:
    reservations:
      devices:
        - driver: nvidia
          count: all
          capabilities: [gpu]
```

That gives Ollama's models GPU access. Open WebUI's own embedding and speech models
still use CPU. For AMD GPUs, follow the upstream Docker guide and choose a verified
ROCm image tag with the required device mappings.

[Open WebUI installation](https://docs.openwebui.com/getting-started/quick-start/).

## Pocket ID

Set `APP_URL` to the external HTTPS URL and `ENCRYPTION_KEY` to the output of
`openssl rand -base64 32`. Route HTTPS through your reverse proxy to port 1411
and visit `/setup` to create the administrator. Enable `TRUST_PROXY` only when
the backend is reachable exclusively through a trusted proxy. Back up the
`pocket-id-data` volume and retain the encryption key.

[Pocket ID installation](https://pocket-id.org/docs/setup/installation).

## Pangolin Community Edition

Requires Linux, Docker Compose 2.23.1+ (including the Compose version used by
Portainer), a public server and DNS pointing to it. Free TCP ports 80/443 and UDP
ports 51820/21820. Gerbil receives `NET_ADMIN` and `SYS_MODULE`; the MCP deployment
plan requires separate host-access approval.

Set these values without placeholder defaults:

- `PANGOLIN_BASE_DOMAIN`: parent domain, such as `example.com`.
- `PANGOLIN_DASHBOARD_DOMAIN`: dashboard hostname, such as `pangolin.example.com`.
- `PANGOLIN_SECRET`: 64 hexadecimal characters from `openssl rand -hex 32`.
- `LETSENCRYPT_EMAIL`: certificate registration email.

Domains must be plain DNS hostnames and the email must be a plain email address;
do not include quotes, schemes or paths. Compose interpolates these values into
three inline YAML configs, so no extra files need copying to the server.
Configuration changes belong in the stack and its environment variables; mounted
configs are read-only. Back up `pangolin-data` and `letsencrypt`, and retain the secret.

Read the one-time setup token from the Pangolin container logs, then visit
`https://<dashboard-hostname>/auth/initial-setup`. The Traefik administration API
is internal to the Gerbil network namespace; port 8080 is not published.
HTTPS backends use certificate verification; configure an exception explicitly
if a resource uses a self-signed certificate.

Configuration follows the upstream [manual installation](https://docs.pangolin.net/self-host/manual/docker-compose)
and [installer templates](https://github.com/fosrl/pangolin/tree/1.24.0/install/config)
(Pangolin is licensed under AGPL-3.0). The Badger plugin is pinned to v1.7.0.

## Karakeep and existing Hoarder deployments

For a new stack, set `NEXTAUTH_URL`, `NEXTAUTH_SECRET` and `MEILI_MASTER_KEY`.
Generate the two secrets separately with `openssl rand -hex 32`. The stack includes
Karakeep, Chrome and Meilisearch; only the web port is published. Optional
`OLLAMA_BASE_URL` or `OPENAI_API_KEY` enables an AI provider. With native Ollama,
leave `OPENAI_API_KEY` empty and set `INFERENCE_TEXT_MODEL` and
`INFERENCE_IMAGE_MODEL` to downloaded models (the image model must support vision).
For another compatible API, also set `OPENAI_BASE_URL`. Apply environment changes
by recreating the stack. See the [AI provider guide](https://docs.karakeep.app/configuration/different-ai-providers/).
Chrome's multi-platform release is pinned by digest.

The catalog now uses `karakeep` instead of the old `hoarder` slug. For an existing
Hoarder deployment, update its image in the existing stack to
`ghcr.io/karakeep-app/karakeep:0.33.2`, preserving the data volumes and both secrets.
Follow the [migration guide](https://docs.karakeep.app/administration/hoarder-to-karakeep-migration/)
and applicable release upgrade instructions. Upgrade an existing Meilisearch
database according to its supported migration path before changing its version.
Deploying this new template creates separate volumes; it does not migrate data.

## Backrest and BentoPDF

Backrest listens on port 9898. Create an account on first start and select `/userdata`
as the backup source. Its host directory defaults to `/srv/dockyard/backrest/source`
and is mounted read-only. Local repositories can use `/repos`; restore into a
writable destination or download files from snapshots. For rclone remotes, mount
your rclone config at `/root/.config/rclone`. [Upstream guide](https://github.com/garethgeorge/backrest).

BentoPDF's self-hosted build listens on container port 8080, mapped to host port
3000. It needs no database or document volume. For Office conversion, serve it
over HTTPS and preserve its COOP/COEP headers through the reverse proxy.
[Deployment guide](https://www.bentopdf.com/docs/self-hosting/docker).

## External stack configuration

The following external templates expose 60 additional environment fields in
Portainer. Every new field has a label and an explanation, with no preset or
default value. Fill values required by the selected deployment before starting
it; fields for unused integrations may remain empty as described below. Keep
existing database passwords and application keys when reusing persistent data.
Changing an environment value does not rotate a password stored in a database.

These fields cover missing Compose substitutions without defaults and explicit
required substitutions. They do not expose every optional upstream setting.
Templates retain their existing fields, including fields unused by some upstream
stacks. Review the referenced stackfile before deploying; the forms do not
prepare host directories, external resources, configuration files or build sources.

| Template | Added fields | Setup requirements |
| --- | --- | --- |
| Appwrite | `_APP_DB_ROOT_PASS`, `_APP_DB_SCHEMA`, `_APP_DB_USER`, `_APP_DB_PASS` | The MariaDB settings must match the credentials and database name used by every application service; see the limitation below. |
| Aurral | `LIDARR_API_KEY`, `LASTFM_API_KEY`, `AUTH_PASSWORD` | Configure a reachable Lidarr instance and authentication. The Last.fm key applies when using its recommendations; verify support for disabling it in the deployed release. |
| Authentik | `PG_PASS` | Required PostgreSQL password; the referenced stack also requires a separate `.env` file. |
| Budibase | `COUCH_DB_USER`, `COUCH_DB_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `INTERNAL_API_KEY`, `BUDIBASE_ENVIRONMENT`, `JWT_SECRET`, `REDIS_PASSWORD`, `BB_ADMIN_USER_EMAIL`, `BB_ADMIN_USER_PASSWORD`, `PLUGINS_DIR`, `MAIN_PORT` | Configure shared service credentials, a free web port and the mounted plugins path. The two administrator fields apply to account bootstrapping; interactive setup depends on the deployed release. |
| CrowdSec WEB UI | `CROWDSEC_PASSWORD` | Register the corresponding Local API account on the reachable CrowdSec instance separately. |
| Filerun | `DEPOT_DOMAIN_NAME` | Parent DNS domain for `filerun.<domain>`; prepare the expected Traefik setup, external Docker resources and host paths. |
| Ignition Gateway | `EDGE_ID` | Unique gateway name for the startup command, such as `ignition-gateway-01`; supply the existing license and administrator settings too. |
| Klaxon | `DEPOT_DOMAIN_NAME` | Parent DNS domain for `klaxon.<domain>`; prepare the expected Traefik setup, external Docker resources, host paths and email delivery. |
| Lidify | `MUSIC_PATH` | Existing absolute music directory on the Docker host, accessible to the relevant container users. |
| LynxPrompt | `DB_PASSWORD`, `SMTP_HOST`, `SMTP_FROM` | All three are explicitly required. Set the existing session secret and public URL fields too; sign-in links require working email delivery. SMTP authentication, when required, needs additional `SMTP_USER` and `SMTP_PASSWORD` values. |
| Mayan EDMS | `DEPOT_DOMAIN_NAME` | Parent DNS domain for `mayan.<domain>`; prepare the expected Traefik setup, external Docker resources and host paths, and review database credentials. |
| Neko | `NEKO_ROOMS_TRAEFIK_NETWORK`, `NEKO_ROOMS_TRAEFIK_ENTRYPOINT`, `NEKO_ROOMS_TRAEFIK_DOMAIN`, `NEKO_ROOMS_TRAEFIK_CERTRESOLVER` | Match the prepared Traefik network, HTTPS entrypoint, full hostname and certificate resolver. Additional configuration is needed as described below. |
| Nextcloud (stack) | `Timezone` | Set the same IANA time zone as the existing `TZ` field, for example `Europe/Warsaw`; this separate case-sensitive field configures MariaDB. |
| Petio | `Timezone` | Set the same IANA time zone as `TZ`; this separate case-sensitive field configures MongoDB. |
| Plane | `PGUSER`, `PGDATABASE`, `PGPASSWORD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` | Match the separately prepared environment files. The AWS-named fields configure the bundled MinIO service; additional source files are required. |
| SolidTime | `APP_URL`, `APP_KEY`, `DB_PASSWORD`, `SUPER_ADMINS`, `MAIL_HOST`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `PASSPORT_PRIVATE_KEY`, `PASSPORT_PUBLIC_KEY`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET`, `S3_ENDPOINT` | Supply the application URL, encryption key, database password and OAuth key pair. SMTP authentication and S3 values depend on the selected integrations; see below. |
| Tdarr | `PUID`, `PGID` | Numeric host user and group IDs with access to media and configuration directories. |
| Teleport | `CONTAINERHOME` | Absolute container path containing the referenced binaries and configuration; these files must be prepared separately. |
| TRIP | `TRIP_SECRET_KEY`, `TRIP_OIDC_ISSUER`, `TRIP_OIDC_CLIENT_ID`, `TRIP_OIDC_CLIENT_SECRET` | Set a private application secret. Configure the OIDC fields together when enabling OIDC, including an external callback URL registered with the identity provider. |

### External stack limitations

**Appwrite:** the referenced stack interpolates the four new fields into MariaDB
but still hardcodes database credentials in its Appwrite services. Setting new
database credentials in the form alone leaves those services inconsistent. Review
and reconcile the entire stack before deployment; arbitrary values in the form do
not repair the upstream file.

**Authentik:** the referenced stack loads a required `.env` file into PostgreSQL,
the server, worker and GeoIP updater. Prepare the release-specific Authentik and
GeoIP configuration separately; `PG_PASS` does not supply those files. Existing
`PUID`, `PGID` and `PORT` form fields are not referenced by this stack. Its published
ports instead use `AUTHENTIK_PORT_HTTP` and `AUTHENTIK_PORT_HTTPS`, which retain
their upstream defaults unless supplied separately.

**Plane:** the referenced file uses `build:` for application services and loads
both `.env` and `apiserver/.env`. It requires a matching source tree, Dockerfiles
and reviewed environment files. Supply consistent database, MinIO and bucket
settings across those files. Filling the five added fields alone cannot make the
referenced stack self-contained.

**Neko:** prepare the mounted Traefik configuration, users file, ACME storage and
dynamic configuration directory. The stack also passes through `TZ`,
`NEKO_ROOMS_EPR` and `NEKO_ROOMS_NAT1TO1`; supply these separately according to
the Neko Rooms setup guide. Router settings in the form must match the prepared
configuration and DNS. The four new fields alone do not create that setup.

**Teleport:** the referenced file is a multi-cluster example. Its services expect
`build/teleport` and `docker/*.yaml` under the container directory
`/root/go/src/github.com/gravitational/teleport`, backed by prepared host mounts.
The container's own `CONTAINERHOME` setting does not supply the Compose-time
substitution, so the form exposes it separately. Setting the path does not supply
the missing binaries or configuration files.

**SolidTime:** generate `APP_KEY` and the matching Passport key pair using
`php artisan self-host:generate-keys` from the deployed release. Paste each value
without its assignment or surrounding quotes, preserving the application's
`base64:` prefix and the Passport keys' generated newline escapes. Keep these
keys across updates. `SUPER_ADMINS` is a comma-separated list without spaces;
it grants privileges to matching verified accounts, without creating accounts or
enabling registration. For SMTP, set a reachable mail host and provide username
and password if authentication is required. The S3 fields may stay empty for
local storage; enabling S3 requires separate filesystem disk configuration, such
as `FILESYSTEM_DISK=s3` and, when appropriate, `PUBLIC_FILESYSTEM_DISK=s3`, plus
provider-specific region and endpoint settings.

External stack contents remain unchanged. The reviewed versions are recorded in
`stacks.lock.json` for MCP deployment plans. Portainer's repository references use
the external repository's default branch, so review upstream changes before
redeployment.
