from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen


HTTPS_URL_RE = re.compile(r"https://[^\s]+")
AGENT_API_TUNNELS_URL = "http://127.0.0.1:4040/api/tunnels"


@dataclass(frozen=True)
class NgrokProvider:
    name: str = "ngrok"
    log_prefix: str = "ngrok"
    install_hint: str = (
        "ngrok was not found on PATH. Install ngrok from "
        "https://ngrok.com/download and configure your authtoken with "
        "`ngrok config add-authtoken TOKEN`."
    )

    def build_command(
        self,
        local_url: str,
        *,
        origin_tls_verify: bool = True,
        tunnel_log_level: str = "info",
    ) -> list[str]:
        if tunnel_log_level == "off":
            return ["ngrok", "http", local_url, "--log", "false"]

        return [
            "ngrok",
            "http",
            local_url,
            "--log",
            "stdout",
            "--log-format",
            "logfmt",
            "--log-level",
            tunnel_log_level,
        ]

    def parse_public_url(self, line: str) -> str | None:
        if "Forwarding" not in line:
            return None

        for candidate in HTTPS_URL_RE.findall(line):
            parsed = urlparse(candidate)
            if parsed.scheme == "https" and parsed.netloc:
                return candidate.rstrip(",")
        return None

    def get_public_url(self) -> str | None:
        try:
            with urlopen(AGENT_API_TUNNELS_URL, timeout=0.5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

        return parse_agent_api_public_url(payload)

    def is_available(self) -> bool:
        return shutil.which("ngrok") is not None


def parse_agent_api_public_url(payload: dict[str, Any]) -> str | None:
    tunnels = payload.get("tunnels")
    if not isinstance(tunnels, list):
        return None

    for tunnel in tunnels:
        if not isinstance(tunnel, dict):
            continue

        public_url = tunnel.get("public_url")
        if not isinstance(public_url, str):
            continue

        parsed = urlparse(public_url)
        if parsed.scheme == "https" and parsed.netloc:
            return public_url

    return None
