# Security Audit — 2026-10-08

## Scope and results

Reviewed the Python gallery builders/CLI, HTML rendering, PHP MCP server, deployment updater,
local Compose stacks, and GitHub Actions. Checked installed Python runtime/development dependencies
against the PyPI advisory database using pip-audit 2.10.1 and checked current releases on PyPI.

The original installed environment already had **zero known vulnerabilities**. The dependency
ranges nevertheless allowed older vulnerable transitive packages. A sample of permitted minimum
versions (`urllib3==1.26.0`, `idna==2.5`, `certifi==2023.5.7`) produced 30 scanner records, including
duplicates: **16 distinct advisory IDs across three packages**. This was an audit of permitted
versions, not evidence that those versions were installed.

After the changes, both the installed dependency snapshot and the checked minimum versions have
**zero known vulnerabilities**. Results are a dated snapshot of public advisories.

## Dependency changes

| Package | Previous requirement | Updated requirement |
| --- | --- | --- |
| PyYAML | >=6.0 | >=6.0.3 |
| Jinja2 | >=3.1.6 | unchanged |
| requests | >=2.33.0 | >=2.34.2 |
| jsonschema | >=4.20 | >=4.26.0 |
| pytest | >=9.0.3 | >=9.1.1 |
| urllib3 | unrestricted beyond Requests' requirement | >=2.8.0,<3 |
| idna | unrestricted beyond Requests' requirement | >=3.20,<4 |
| certifi | unrestricted beyond Requests' requirement | >=2026.7.22 |
| pip-audit | absent | >=2.10.1, optional audit extra |

The added transitive floors prevent known vulnerable releases from satisfying the project's
requirements. Representative advisories include urllib3's
[CVE-2026-97687](https://github.com/urllib3/urllib3/security/advisories/GHSA-8988-9cw3-xx77)
and [CVE-2026-97689](https://github.com/urllib3/urllib3/security/advisories/GHSA-vxq7-64xx-v4gw),
idna's [CVE-2026-45409](https://github.com/kjd/idna/security/advisories/GHSA-65pc-fj4g-8rjx),
and certifi's [CVE-2024-39689](https://github.com/certifi/python-certifi/security/advisories/GHSA-248v-346w-9cwc).

Updated local transitive packages: MarkupSafe 3.0.3 → 3.0.4, charset-normalizer 3.5.1 → 3.5.2,
iniconfig 2.3.0 → 2.3.1, and rpds-py 2026.6.3 → 2026.9.1. The remaining installed packages
reported no newer stable releases. The existing setuptools >=83 build floor was retained and audited.

## Code and configuration fixes

- Reject unsafe slugs before scaffolding and create app files exclusively to prevent overwrites.
- Validate URL protocols and credentials before building; filter app/cache links during HTML
  rendering while preserving embedded raster logos and Jinja's HTML escaping.
- Reject Compose paths outside the repository, including resolved symlinks, and malformed YAML roots.
- Bound MCP request reads to 64 KiB and return HTTP 413 for oversized bodies.
- Quote generated network keys and keep app titles on one YAML comment line.
- Restrict local MCP stack reads to YAML files under `stacks/`.
- Remove built-in passwords from all six local stacks and their canonical app definitions.
  Require nonempty values with `${VARIABLE:?message}`; MCP blocks plans without those values.
- Remove obsolete n8n Basic Auth settings. n8n uses owner account setup in its web UI;
  [the producer removed Basic Auth in 1.0](https://github.com/n8n-io/n8n-docs/blob/main/docs/deploy/host-n8n/configure-n8n/user-management.md).
- Pin GitHub Actions to verified release commits, add read-only PR/push/weekly test and audit jobs,
  and configure weekly Dependabot updates.

## Verification and limits

Local verification on Python 3.14.7: **98 tests passed; one symlink test skipped because Windows
does not permit symlink creation**. PHP integration tests, including HTTP size limits and deployment
tests with ZipArchive, ran successfully. Built all 635 templates and the site; schema validation
and `pip check` passed. CI is configured for Python 3.10 and 3.14; remote jobs have not run yet.

Container image layers and third-party stackfiles were not exhaustively scanned: Docker is not
installed here, and catalog tags such as `latest` identify mutable upstream artifacts. The zero-CVE
result applies to the checked Python dependencies, not to every application listed in the catalog
or to the production host's PHP/Apache packages.

For existing database volumes, keep the current password when redeploying. Editing `.env` alone
does not rotate stored database credentials. Follow the upstream application's rotation procedure.
Audit commands are documented in [README.md](README.md#security-checks).
