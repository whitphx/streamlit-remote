from __future__ import annotations

from pathlib import Path
from typing import Literal, Protocol

from streamlit_remote.providers.cloudflare import CloudflareQuickTunnelProvider
from streamlit_remote.providers.ngrok import NgrokProvider
from streamlit_remote.providers.pinggy import PinggyProvider
from streamlit_remote.providers.zrok import ZrokProvider

TunnelLogLevel = Literal["info", "warn", "error", "off"]
PROVIDER_NAMES = ("cloudflare", "ngrok", "zrok", "pinggy")


class TunnelProvider(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def log_prefix(self) -> str: ...

    @property
    def install_hint(self) -> str: ...

    def build_command(
        self,
        local_url: str,
        *,
        origin_tls_verify: bool = True,
        tunnel_log_level: TunnelLogLevel = "info",
        traffic_policy_file: Path | None = None,
    ) -> list[str]: ...

    def parse_public_url(self, line: str) -> str | None: ...

    def normalize_log_line(self, line: str) -> str: ...

    def get_public_url(self) -> str | None: ...

    def is_available(self) -> bool: ...


def get_provider(name: str, executable: str | Path | None = None) -> TunnelProvider:
    if name == "cloudflare":
        return CloudflareQuickTunnelProvider(executable=executable or "cloudflared")

    if name == "ngrok":
        return NgrokProvider(executable=executable or "ngrok")

    if name == "zrok":
        return ZrokProvider(executable=executable or "zrok")

    if name == "pinggy":
        return PinggyProvider(executable=executable or "ssh")

    raise ValueError(f"Unsupported provider: {name}")
