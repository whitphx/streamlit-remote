from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from streamlit_remote.providers.executables import is_executable_available

TRYCLOUDFLARE_URL_RE = re.compile(r"https://[A-Za-z0-9-]+\.trycloudflare\.com\b")


@dataclass(frozen=True)
class CloudflareQuickTunnelProvider:
    name: str = "cloudflare"
    log_prefix: str = "cloudflared"
    executable: str | Path = "cloudflared"

    @property
    def install_hint(self) -> str:
        executable = str(self.executable)
        if executable == "cloudflared":
            return (
                "cloudflared was not found on PATH. Install Cloudflare Tunnel from "
                "https://developers.cloudflare.com/cloudflare-one/connections/"
                "connect-networks/downloads/ "
                "and try again."
            )
        return f"cloudflared was not found at configured path: {executable}"

    def build_command(
        self,
        local_url: str,
        *,
        origin_tls_verify: bool = True,
        tunnel_log_level: str = "info",
        traffic_policy_file: Path | None = None,
    ) -> list[str]:
        command = [str(self.executable), "tunnel", "--url", local_url]
        if not origin_tls_verify:
            command.append("--no-tls-verify")
        return command

    def parse_public_url(self, line: str) -> str | None:
        match = TRYCLOUDFLARE_URL_RE.search(line)
        if match is None:
            return None
        return match.group(0)

    def get_public_url(self) -> str | None:
        return None

    def is_available(self) -> bool:
        return is_executable_available(self.executable)
