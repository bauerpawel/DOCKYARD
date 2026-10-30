# Formbricks upstream configuration

The embedded authorization bootstrap script, Cube configuration and Cube model come from
[Formbricks 6.1.2](https://github.com/formbricks/formbricks/tree/6.1.2/docker):

- `authzed-postgres-bootstrap.sh`
- `cube/cube.js`
- `cube/schema/FeedbackRecords.js`

Their contents are preserved in `configs.content`; dollar signs are doubled only to escape
Docker Compose interpolation. `LICENSE.upstream` contains the upstream license and copyright notice.
Application and companion images are pinned by SHA-256 in `docker-compose.yml`.
The stack includes startup migrations and authorization initialization for a fresh database.
