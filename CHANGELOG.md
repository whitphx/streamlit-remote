# Changelog

<!-- scriv-insert-here -->

<a id='changelog-0.7.2'></a>
## 0.7.2 — 2026-07-03

### Fixed

- Preserve Streamlit Rich traceback frames in the TUI log panel by sizing the subprocess output for the panel and rendering preformatted traceback lines without per-line log prefixes.

<a id='changelog-0.7.1'></a>
## 0.7.1 — 2026-07-01

### Fixed

- Replayed recent logs in the normal terminal buffer when a child process exits with an error while the live terminal display is active.

<a id='changelog-0.7.0'></a>
## 0.7.0 — 2026-07-01

### Changed

- Changed interactive runtime shortcuts to work as single-key hotkeys, while keeping Enter-based commands as a fallback.

<a id='changelog-0.6.0'></a>
## 0.6.0 — 2026-07-01

### Added

- Added a live terminal display for interactive sessions, with `--no-tui` and `t` + Enter available for toggling between fancy and plain prefixed logs.

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
