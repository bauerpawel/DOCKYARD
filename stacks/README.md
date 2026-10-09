# Local app stacks

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
