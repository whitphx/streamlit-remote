# streamlit-remote

`streamlit-remote` runs a Streamlit app locally, can serve it over local HTTPS, and can expose it through a temporary remote HTTPS URL.

It supports Cloudflare Quick Tunnel, ngrok, and managed self-signed certificates for local HTTPS. It is meant for development, demos, and temporary sharing, similar in spirit to Slidev's remote access workflow.

## Installation

```bash
pip install streamlit-remote
```

This package requires Python 3.10 or newer.

## Basic Usage

```bash
st-remote app.py
```

This starts Streamlit on `http://localhost:8501`, starts a Cloudflare Quick Tunnel to that local URL, prefixes logs from both child processes, prints the public `trycloudflare.com` URL once Cloudflare reports it, and opens that remote URL in your browser.

You can also use the alias:

```bash
streamlit-remote app.py
```

## Options

```bash
st-remote APP [--port 8501] [--host localhost] [--https off] [--provider cloudflare]
```

Useful options:

```bash
st-remote app.py --port 9000
st-remote app.py --host 0.0.0.0
st-remote app.py --no-remote
st-remote app.py --no-browser
st-remote app.py --no-tui
st-remote app.py --dry-run
st-remote app.py --https self-signed --no-remote
st-remote app.py --https mkcert --no-remote
st-remote app.py --https mkcert --mkcert-binary /path/to/mkcert --no-remote
st-remote app.py --provider ngrok
st-remote app.py --provider zrok
st-remote app.py --cloudflared-binary /path/to/cloudflared
st-remote app.py --provider ngrok --ngrok-binary /path/to/ngrok
st-remote app.py --provider zrok --zrok-binary /path/to/zrok
st-remote app.py --provider ngrok --tunnel-log-level warn
st-remote app.py --provider ngrok --remote-auth oauth --oauth-provider google
st-remote app.py --provider ngrok --ngrok-traffic-policy-file policy.yml
st-remote app.py --toolbar-mode viewer
st-remote app.py -- --server.headless true
```

Extra arguments after `--` are passed to `python -m streamlit run`.

`st-remote` starts Streamlit in headless mode so Streamlit does not open the local URL automatically. When remote access is enabled, `st-remote` opens the detected remote HTTPS URL instead. Use `--no-browser` to suppress browser opening.

`st-remote` also sets Streamlit's toolbar mode to `developer` by default so controls such as rerun and clear cache remain visible through remote proxy hostnames. Use `--toolbar-mode viewer` to hide those developer toolbar actions, or `--toolbar-mode auto` to use Streamlit's default hostname-sensitive behavior.

## Runtime Display and Shortcuts

In an interactive terminal, `st-remote` shows a live terminal display with local and remote URLs, process statuses, recent logs, and shortcut help. Use `--no-tui` to keep plain prefixed log output from startup.

Press `r` to restart only the Streamlit server while keeping the remote tunnel process running. This keeps the current tunnel session alive, so providers such as Cloudflare Quick Tunnel, ngrok, and zrok can continue serving the same public URL while Streamlit restarts behind it.

Press `t` to toggle between the live terminal display and plain prefixed log output. When switching to plain output, `st-remote` replays recent logs into the normal terminal buffer so you can copy older logs from terminal or tmux history. You can also press `p` to force plain output and `f` to force the live terminal display. In terminals where single-key input is unavailable, the Enter-based commands still work.

If Streamlit or the remote tunnel exits with an error while the live terminal display is active, `st-remote` returns to the normal terminal buffer and replays recent logs before exiting.

Use Ctrl+C to stop both Streamlit and the remote tunnel.

## Local HTTPS

By default, Streamlit runs locally over HTTP:

```bash
st-remote app.py --https off
```

For local HTTPS, use managed self-signed mode:

```bash
st-remote app.py --https self-signed --no-remote
```

`streamlit-remote` creates and reuses a local development certificate in its own cache directory, then passes Streamlit's `server.sslCertFile` and `server.sslKeyFile` options automatically. You do not need to choose filenames or manage generated certificate files.

Browsers generally do not trust self-signed certificates by default. You may see a certificate warning unless you manually trust the generated certificate. This mode is intended for local development and testing, not production.

For trusted local HTTPS, use mkcert:

```bash
st-remote app.py --https mkcert --no-remote
```

This requires the `mkcert` command to be installed and available on `PATH`. If it is
installed somewhere else, pass `--mkcert-binary /path/to/mkcert`.

Install instructions are available from mkcert:

https://github.com/FiloSottile/mkcert

`streamlit-remote` creates and reuses mkcert certificate files in its own cache directory, runs `mkcert -install` when it needs to generate them, and passes Streamlit's SSL options automatically.

Advanced users can pass existing certificate files:

```bash
st-remote app.py --https cert-files \
  --ssl-cert-file cert.pem \
  --ssl-key-file key.pem
```

## Remote Providers

### Cloudflare Tunnel

Cloudflare Quick Tunnel requires the `cloudflared` command to be installed and available on `PATH`. If it is installed somewhere else, pass `--cloudflared-binary /path/to/cloudflared`.

Install instructions are available from Cloudflare:

https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

`streamlit-remote` checks for `cloudflared` before starting the tunnel and prints an actionable error if it is missing. It does not install `cloudflared` automatically.

### ngrok

ngrok requires the `ngrok` command to be installed and available on `PATH`. If it is installed somewhere else, pass `--ngrok-binary /path/to/ngrok`.

Install instructions are available from ngrok:

https://ngrok.com/download

Configure your ngrok account token before use:

```bash
ngrok config add-authtoken TOKEN
```

Then run:

```bash
st-remote app.py --provider ngrok
```

ngrok provides HTTPS for the public URL while forwarding to your local Streamlit app. If you combine ngrok with local self-signed HTTPS:

```bash
st-remote app.py --provider ngrok --https self-signed
```

ngrok still provides HTTPS for the public URL. The self-signed certificate is used only between the local ngrok agent and Streamlit.

#### ngrok Remote Auth

For quick access control with ngrok, use managed OAuth:

```bash
st-remote app.py --provider ngrok --remote-auth oauth --oauth-provider google
```

Supported managed OAuth providers are `github`, `gitlab`, `google`, `linkedin`, `microsoft`, and `twitch`. `streamlit-remote` writes a temporary ngrok Traffic Policy file, starts ngrok with `--traffic-policy-file`, and removes the temporary file on shutdown.

Advanced users can provide their own ngrok Traffic Policy file:

```bash
st-remote app.py --provider ngrok --ngrok-traffic-policy-file policy.yml
```

This is useful for provider-specific policies such as OIDC, Basic Auth, IP restrictions, or custom OAuth configuration.

### zrok

zrok requires the `zrok` command to be installed and available on `PATH`. If it is installed somewhere else, pass `--zrok-binary /path/to/zrok`.

Install instructions are available from zrok:

https://docs.zrok.io/

Before first use, create or sign in to a zrok account and enable your environment:

```bash
zrok enable
```

Then run:

```bash
st-remote app.py --provider zrok
```

`streamlit-remote` starts zrok with `zrok share public --headless localhost:8501` and opens the HTTPS public share URL after zrok prints it. The `--headless` flag disables zrok's own terminal UI so it does not conflict with `st-remote`'s runtime display.

## Tunnel Logs

Tunnel provider logs are shown by default:

```bash
st-remote app.py --tunnel-log-level info
```

Use a quieter level to reduce provider noise while keeping Streamlit logs visible:

```bash
st-remote app.py --provider ngrok --tunnel-log-level warn
st-remote app.py --provider ngrok --tunnel-log-level error
st-remote app.py --provider ngrok --tunnel-log-level off
```

`off` suppresses printed tunnel logs but still captures provider output internally when needed to detect the remote URL. ngrok also uses its local agent API as a fallback for URL detection.

## HTTPS Serving vs Remote Access

The design treats HTTPS serving and remote access as separate concepts.

HTTPS serving means the user-facing URL uses HTTPS. Remote access means the app is reachable from outside your local machine.

Cloudflare Quick Tunnel, ngrok, and zrok usually provide both at once: Streamlit can run locally over plain HTTP, while the provider gives you a public HTTPS URL that forwards to the local app.

Local self-signed and mkcert HTTPS are different: Streamlit itself runs with HTTPS locally. You can use local HTTPS without remote access, or combine it with a remote provider when you specifically want HTTPS between the tunnel agent and Streamlit.

Common combinations:

```text
--https off + --provider cloudflare
  Public HTTPS via Cloudflare, local HTTP Streamlit.

--https off + --provider ngrok
  Public HTTPS via ngrok, local HTTP Streamlit.

--https off + --provider zrok
  Public HTTPS via zrok, local HTTP Streamlit.

--https self-signed + --no-remote
  Local HTTPS Streamlit only.

--https mkcert + --no-remote
  Local HTTPS Streamlit with a locally trusted mkcert certificate.

--https self-signed + --provider ngrok
  Public HTTPS via ngrok, local HTTPS between ngrok and Streamlit.
```

For managed self-signed HTTPS with Cloudflare Tunnel, `streamlit-remote` also passes Cloudflare's origin TLS verification flag automatically so `cloudflared` can connect to the local self-signed Streamlit server.

## Security

This exposes a local Streamlit app to the internet.

Do not use it for sensitive data unless you have proper authentication and access control in place. Cloudflare Quick Tunnel, ngrok, and zrok are best suited for development, demos, and temporary sharing.

ngrok remote auth can add provider-level access control before requests reach Streamlit. Cloudflare Quick Tunnel auth is not supported by this package; Cloudflare Access requires a configured Zero Trust application and is outside the current Quick Tunnel workflow.

Streamlit's built-in SSL configuration is useful for local testing, but it is not a replacement for a production HTTPS reverse proxy.

## Limitations

The current package does not include production Cloudflare named tunnels, Cloudflare Access integration, built-in password protection, or reverse proxy management.

## Roadmap

- Cloudflare named tunnel support
- Cloudflare Access integration
- more ngrok Traffic Policy helpers

## Development

```bash
uv run ruff format
uv run ruff check --fix
uv run basedpyright
uv run pytest
```

Install the local pre-commit hooks with:

```bash
uv run pre-commit install
```

Run all hooks manually with:

```bash
uv run pre-commit run --all-files
```

## Release Management

This project uses `scriv-release` for changelog-fragment based releases.

For user-visible changes, add a fragment:

```bash
uv run scriv create --edit
```

When fragments are merged to `main`, the release workflow opens or updates a changelog preview PR. Merging that preview PR tags the release. Tag pushes matching `v*` run the PyPI publish workflow through Trusted Publishing.

The release workflow expects a GitHub App configured through `RELEASE_APP_CLIENT_ID` and `RELEASE_APP_KEY` so release tags can trigger the downstream publish workflow.
