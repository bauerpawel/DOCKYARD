# Plane 1.4.2 with RustFS 1.0.4

This stack adapts Plane's official
[Community Edition release configuration](https://github.com/makeplane/plane/blob/v1.4.2/deployments/cli/community/docker-compose.yml).
All services use prebuilt images pinned by digest. There are no `build:` contexts,
missing Dockerfiles or `env_file` dependencies. PostgreSQL, Valkey, RabbitMQ and
RustFS are included. An external S3 account is not needed.

Set `PLANE_DOMAIN` to the public hostname and `WEB_URL` to the matching full
external URL, such as `https://plane.example.com`. The bundled HTTP proxy listens
on host port 8080 by default. Terminate HTTPS in your reverse proxy and forward
requests to that port, preserving the original host and scheme. Change
`PLANE_PORT` if that host port is already occupied.

Generate separate values with `openssl rand -hex 32` for `PGPASSWORD`,
`RABBITMQ_PASSWORD`, `PLANE_SECRET_KEY`, `LIVE_SERVER_SECRET_KEY` and
`AWS_SECRET_ACCESS_KEY`. Use a private RustFS account identifier for
`AWS_ACCESS_KEY_ID`, for example a separate `openssl rand -hex 10` value.
PostgreSQL and RabbitMQ passwords must be hexadecimal because they are embedded
in connection URLs. `PGUSER` and `PGDATABASE` accept letters, digits and underscores.

Supply these fields in Portainer, or put them in a private `.env` for local use:

```sh
docker compose --env-file .env -f stacks/plane/docker-compose.yml up -d
```

The database and queue must become healthy before migration. The migration and
bucket-initialization services must finish successfully before API and workers
start. The initial administrator/setup flow is available through the Plane admin
interface after startup; email settings can be configured there.

## Bundled object storage

The service is named `plane-minio` for compatibility with Plane's upstream proxy,
but runs RustFS 1.0.4. Plane, RustFS and the bucket initializer receive the same
`AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`. A private `uploads` bucket is
created automatically; change `AWS_S3_BUCKET_NAME` before initial deployment if
needed. Keep the storage region `us-east-1` for this local configuration.

RustFS runs as UID/GID 10001:10001. A one-shot helper prepares only the stack's
named data and log volumes for that account. The S3 API and management console
are not published on the host, and the console is disabled. File access goes
through Plane's application/proxy flow. Existing data and the credentials needed
to read it must be retained across updates.

If the Docker host injects HTTP proxy settings into containers, add the internal
service names to `NO_PROXY`/`no_proxy`, including `plane-minio`, `plane-db`,
`plane-redis`, `plane-mq`, `api` and `localhost`. Internal S3 and database traffic
must not be sent through an outbound HTTP proxy.

## Existing installations

This is a new installation, not an automatic upgrade of the old source-build
template. Follow the upstream database migration and backup procedure before
moving existing Plane data. Do not mount existing MinIO data files directly into
RustFS; migrate object data through the S3 API into the new bucket and preserve
the application/database references. Keep database credentials, the application
secret and the realtime secret when updating an existing deployment.

The Plane-derived Compose configuration carries the upstream AGPL-3.0 license in
`LICENSE.upstream`. RustFS images retain their Apache-2.0 license.
