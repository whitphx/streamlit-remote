from __future__ import annotations

from typing import Protocol

from streamlit_remote.providers.cloudflare import CloudflareQuickTunnelProvider


class TunnelProvider(Protocol):
    name: str

    def build_command(self, local_url: str) -> list[str]: ...

    def parse_public_url(self, line: str) -> str | None: ...

    def is_available(self) -> bool: ...


def get_provider(name: str) -> TunnelProvider:
    if name == "cloudflare":
        return CloudflareQuickTunnelProvider()

    raise ValueError(f"Unsupported provider: {name}")
