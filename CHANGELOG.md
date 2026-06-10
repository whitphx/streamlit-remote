# Changelog

<!-- scriv-insert-here -->

<a id='changelog-0.4.0'></a>
## 0.4.0 — 2026-06-10

### Added

- Added CLI options for specifying custom `cloudflared`, `ngrok`, and `mkcert` binary paths, originally merged in #10.

<a id='changelog-0.3.0'></a>
## 0.3.0 — 2026-06-10

### Added

- Added ngrok remote auth support with generated managed OAuth Traffic Policy files and custom Traffic Policy file passthrough.

### Chore

- Added Ruff, basedpyright, and pre-commit configuration for code quality checks.

<a id='changelog-0.2.0'></a>
## 0.2.0 — 2026-06-09

### Added

- Added managed mkcert support via `--https mkcert` for locally trusted Streamlit HTTPS.
