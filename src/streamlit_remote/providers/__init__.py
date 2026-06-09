from __future__ import annotations

from typing import Literal, Protocol

from streamlit_remote.providers.cloudflare import CloudflareQuickTunnelProvider
from streamlit_remote.providers.ngrok import NgrokProvider


TunnelLogLevel = Literal["info", "warn", "error", "off"]


class TunnelProvider(Protocol):
    name: str
    log_prefix: str
    install_hint: str

    def build_command(
        self,
        local_url: str,
        *,
        origin_tls_verify: bool = True,
        tunnel_log_level: TunnelLogLevel = "info",
    ) -> list[str]: ...

    def parse_public_url(self, line: str) -> str | None: ...

    def get_public_url(self) -> str | None: ...

    def is_available(self) -> bool: ...


def get_provider(name: str) -> TunnelProvider:
    if name == "cloudflare":
        return CloudflareQuickTunnelProvider()

    if name == "ngrok":
        return NgrokProvider()

    raise ValueError(f"Unsupported provider: {name}")
