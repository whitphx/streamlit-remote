# Changelog

<!-- scriv-insert-here -->

<a id='changelog-0.5.0'></a>
## 0.5.0 — 2026-06-22

### Added

- Added an interactive `r` + Enter shortcut to restart only the Streamlit server while keeping the remote tunnel running.

<a id='changelog-0.4.1'></a>
## 0.4.1 — 2026-06-22

### Fixed

- Kept Streamlit developer toolbar controls enabled through remote proxy URLs by default, with a new `--toolbar-mode` option for choosing Streamlit's toolbar behavior.

- Fixed tunnel provider binary detection for symlinked `cloudflared` and `ngrok` commands.

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
