from __future__ import annotations

import re
import shutil
from dataclasses import dataclass


TRYCLOUDFLARE_URL_RE = re.compile(r"https://[A-Za-z0-9-]+\.trycloudflare\.com\b")


@dataclass(frozen=True)
class CloudflareQuickTunnelProvider:
    name: str = "cloudflare"
    log_prefix: str = "cloudflared"
    install_hint: str = (
        "cloudflared was not found on PATH. Install Cloudflare Tunnel from "
        "https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/ "
        "and try again."
    )

    def build_command(
        self,
        local_url: str,
        *,
        origin_tls_verify: bool = True,
        tunnel_log_level: str = "info",
    ) -> list[str]:
        command = ["cloudflared", "tunnel", "--url", local_url]
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
        return shutil.which("cloudflared") is not None
