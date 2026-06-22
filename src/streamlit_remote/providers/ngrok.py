from __future__ import annotations

import json
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import urlopen

from streamlit_remote.providers.executables import is_executable_available

HTTPS_URL_RE = re.compile(r"https://[^\s]+")
AGENT_API_TUNNELS_URL = "http://127.0.0.1:4040/api/tunnels"
MANAGED_OAUTH_PROVIDERS = ("github", "gitlab", "google", "linkedin", "microsoft", "twitch")


@dataclass(frozen=True)
class NgrokProvider:
    name: str = "ngrok"
    log_prefix: str = "ngrok"
    executable: str | Path = "ngrok"

    @property
    def install_hint(self) -> str:
        executable = str(self.executable)
        if executable == "ngrok":
            return (
                "ngrok was not found on PATH. Install ngrok from "
                "https://ngrok.com/download and configure your authtoken with "
                "`ngrok config add-authtoken TOKEN`."
            )
        return f"ngrok was not found at configured path: {executable}"

    def build_command(
        self,
        local_url: str,
        *,
        origin_tls_verify: bool = True,
        tunnel_log_level: str = "info",
        traffic_policy_file: Path | None = None,
    ) -> list[str]:
        policy_args: list[str] = []
        if traffic_policy_file is not None:
            policy_args = ["--traffic-policy-file", str(traffic_policy_file)]

        if tunnel_log_level == "off":
            return [str(self.executable), "http", local_url, *policy_args, "--log", "false"]

        return [
            str(self.executable),
            "http",
            local_url,
            *policy_args,
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
        return is_executable_available(self.executable)


@dataclass
class PreparedNgrokTrafficPolicy:
    traffic_policy_file: Path
    _tempdir: tempfile.TemporaryDirectory[str] | None = None

    def cleanup(self) -> None:
        if self._tempdir is not None:
            self._tempdir.cleanup()


def prepare_managed_oauth_policy(oauth_provider: str) -> PreparedNgrokTrafficPolicy:
    tempdir = tempfile.TemporaryDirectory(prefix="streamlit-remote-ngrok-")
    policy_file = Path(tempdir.name) / "oauth-policy.yml"
    policy_file.write_text(build_managed_oauth_policy(oauth_provider), encoding="utf-8")
    return PreparedNgrokTrafficPolicy(traffic_policy_file=policy_file, _tempdir=tempdir)


def planned_managed_oauth_policy(oauth_provider: str) -> PreparedNgrokTrafficPolicy:
    return PreparedNgrokTrafficPolicy(
        traffic_policy_file=Path(f"<generated-ngrok-{oauth_provider}-oauth-policy.yml>")
    )


def build_managed_oauth_policy(oauth_provider: str) -> str:
    if oauth_provider not in MANAGED_OAUTH_PROVIDERS:
        raise ValueError(f"Unsupported ngrok managed OAuth provider: {oauth_provider}.")

    return (
        "on_http_request:\n"
        "  - actions:\n"
        "      - type: oauth\n"
        "        config:\n"
        f"          provider: {oauth_provider}\n"
    )


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
