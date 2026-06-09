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
st-remote app.py --dry-run
st-remote app.py --https self-signed --no-remote
st-remote app.py --provider ngrok
st-remote app.py --provider ngrok --tunnel-log-level warn
st-remote app.py -- --server.headless true
```

Extra arguments after `--` are passed to `python -m streamlit run`.

`st-remote` starts Streamlit in headless mode so Streamlit does not open the local URL automatically. When remote access is enabled, `st-remote` opens the detected remote HTTPS URL instead. Use `--no-browser` to suppress browser opening.

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

Advanced users can pass existing certificate files:

```bash
st-remote app.py --https cert-files \
  --ssl-cert-file cert.pem \
  --ssl-key-file key.pem
```

## Remote Providers

### Cloudflare Tunnel

Cloudflare Quick Tunnel requires the `cloudflared` command to be installed and available on `PATH`.

Install instructions are available from Cloudflare:

https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

`streamlit-remote` checks for `cloudflared` before starting the tunnel and prints an actionable error if it is missing. It does not install `cloudflared` automatically.

### ngrok

ngrok requires the `ngrok` command to be installed and available on `PATH`.

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

Cloudflare Quick Tunnel and ngrok usually provide both at once: Streamlit can run locally over plain HTTP, while the provider gives you a public HTTPS URL that forwards to the local app.

Local self-signed HTTPS is different: Streamlit itself runs with HTTPS locally. You can use this without remote access, or combine it with a remote provider when you specifically want HTTPS between the tunnel agent and Streamlit.

Common combinations:

```text
--https off + --provider cloudflare
  Public HTTPS via Cloudflare, local HTTP Streamlit.

--https off + --provider ngrok
  Public HTTPS via ngrok, local HTTP Streamlit.

--https self-signed + --no-remote
  Local HTTPS Streamlit only.

--https self-signed + --provider ngrok
  Public HTTPS via ngrok, local HTTPS between ngrok and Streamlit.
```

For managed self-signed HTTPS with Cloudflare Tunnel, `streamlit-remote` also passes Cloudflare's origin TLS verification flag automatically so `cloudflared` can connect to the local self-signed Streamlit server.

## Security

This exposes a local Streamlit app to the internet.

Do not use it for sensitive data unless you have proper authentication and access control in place. Cloudflare Quick Tunnel and ngrok are best suited for development, demos, and temporary sharing.

Streamlit's built-in SSL configuration is useful for local testing, but it is not a replacement for a production HTTPS reverse proxy.

## Limitations

The current package does not include mkcert integration, production Cloudflare named tunnels, authentication, password protection, reverse proxy management, or PyPI publishing automation.

## Roadmap

- local HTTPS with mkcert
- optional auth and access-control integration

## Development

```bash
uv run pytest
```
