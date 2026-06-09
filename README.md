# streamlit-remote

`streamlit-remote` runs a Streamlit app locally and can expose it through a temporary remote HTTPS URL.

The MVP supports Cloudflare Quick Tunnel. It is meant for development, demos, and temporary sharing, similar in spirit to Slidev's remote access workflow.

## Installation

```bash
pip install streamlit-remote
```

This package requires Python 3.10 or newer.

## Basic Usage

```bash
st-remote app.py
```

This starts Streamlit on `http://127.0.0.1:8501`, starts a Cloudflare Quick Tunnel to that local URL, prefixes logs from both child processes, and prints the public `trycloudflare.com` URL once Cloudflare reports it.

You can also use the alias:

```bash
streamlit-remote app.py
```

## Options

```bash
st-remote APP [--port 8501] [--host 127.0.0.1] [--provider cloudflare]
```

Useful options:

```bash
st-remote app.py --port 9000
st-remote app.py --host 0.0.0.0
st-remote app.py --no-remote
st-remote app.py --dry-run
st-remote app.py -- --server.headless true
```

Extra arguments after `--` are passed to `python -m streamlit run`.

## Cloudflare Tunnel Requirement

Cloudflare Quick Tunnel requires the `cloudflared` command to be installed and available on `PATH`.

Install instructions are available from Cloudflare:

https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/

`streamlit-remote` checks for `cloudflared` before starting the tunnel and prints an actionable error if it is missing. It does not install `cloudflared` automatically.

## HTTPS Serving vs Remote Access

The design treats HTTPS serving and remote access as separate concepts.

HTTPS serving means the user-facing URL uses HTTPS. Remote access means the app is reachable from outside your local machine.

Cloudflare Quick Tunnel usually provides both at once: Streamlit still runs locally over plain HTTP, while Cloudflare provides a public HTTPS URL that forwards to the local app.

Future modes can support these concerns independently, such as local HTTPS without remote access, remote access through another provider, or plain local Streamlit passthrough for debugging.

## Security

This exposes a local Streamlit app to the internet.

Do not use it for sensitive data unless you have proper authentication and access control in place. Cloudflare Quick Tunnel is best suited for development, demos, and temporary sharing.

## MVP Limitations

Only Cloudflare Quick Tunnel is currently supported.

The MVP does not include ngrok, local certificate generation, production Cloudflare named tunnels, authentication, password protection, reverse proxy management, or PyPI publishing automation.

## Roadmap

- ngrok provider
- local HTTPS with mkcert
- expanded provider abstraction
- optional auth and access-control integration

## Development

```bash
uv run pytest
```
