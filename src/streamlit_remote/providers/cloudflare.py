from __future__ import annotations

import re
import shutil
from dataclasses import dataclass


TRYCLOUDFLARE_URL_RE = re.compile(r"https://[A-Za-z0-9-]+\.trycloudflare\.com\b")


@dataclass(frozen=True)
class CloudflareQuickTunnelProvider:
    name: str = "cloudflare"

    def build_command(self, local_url: str) -> list[str]:
        return ["cloudflared", "tunnel", "--url", local_url]

    def parse_public_url(self, line: str) -> str | None:
        match = TRYCLOUDFLARE_URL_RE.search(line)
        if match is None:
            return None
        return match.group(0)

    def is_available(self) -> bool:
        return shutil.which("cloudflared") is not None
