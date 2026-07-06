from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from streamlit_remote.providers.executables import is_executable_available
from streamlit_remote.server import bracket_ipv6_host

ZROK_SHARE_HOST_RE = re.compile(r"(?<![\w.-])(?:https://)?([A-Za-z0-9-]+\.shares?\.zrok\.io)\b")


@dataclass(frozen=True)
class ZrokProvider:
    name: str = "zrok"
    log_prefix: str = "zrok"
    executable: str | Path = "zrok"

    @property
    def install_hint(self) -> str:
        executable = str(self.executable)
        if executable == "zrok":
            return (
                "zrok was not found on PATH. Install zrok from "
                "https://docs.zrok.io/ and enable your environment with `zrok enable`."
            )
        return f"zrok was not found at configured path: {executable}"

    def build_command(
        self,
        local_url: str,
        *,
        origin_tls_verify: bool = True,
        tunnel_log_level: str = "info",
        traffic_policy_file: Path | None = None,
    ) -> list[str]:
        parsed = urlparse(local_url)
        try:
            local_port = parsed.port
        except ValueError as exc:
            raise ValueError(f"Local URL must include a valid port for zrok: {local_url}") from exc

        if local_port is None:
            raise ValueError(f"Local URL must include a port for zrok: {local_url}")

        local_host = local_connect_host(parsed.hostname)
        if local_host is None:
            raise ValueError(f"Local URL must include a host for zrok: {local_url}")

        command = [str(self.executable), "share", "public", "--headless"]
        if not origin_tls_verify:
            command.append("--insecure")
        command.append(f"{parsed.scheme}://{bracket_ipv6_host(local_host)}:{local_port}")
        return command

    def parse_public_url(self, line: str) -> str | None:
        match = ZROK_SHARE_HOST_RE.search(line)
        if match is not None:
            return f"https://{match.group(1)}"

        return None

    def normalize_log_line(self, line: str) -> str:
        return line

    def get_public_url(self) -> str | None:
        return None

    def is_available(self) -> bool:
        return is_executable_available(self.executable)


def local_connect_host(host: str | None) -> str | None:
    if host == "0.0.0.0":
        return "127.0.0.1"
    if host == "::":
        return "::1"
    return host
