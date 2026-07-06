from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from streamlit_remote.providers.executables import is_executable_available
from streamlit_remote.providers.terminal import normalize_terminal_line
from streamlit_remote.providers.zrok import local_connect_host
from streamlit_remote.server import bracket_ipv6_host

LOCALHOST_RUN_HOST = "localhost.run"
LOCALHOST_RUN_URL_RE = re.compile(r"https://[A-Za-z0-9-]+\.lhr\.life\b")


@dataclass(frozen=True)
class LocalhostRunProvider:
    name: str = "localhost-run"
    log_prefix: str = "localhost.run"
    executable: str | Path = "ssh"

    @property
    def install_hint(self) -> str:
        executable = str(self.executable)
        if executable == "ssh":
            return "ssh was not found on PATH. Install OpenSSH or pass `--localhost-run-binary`."
        return f"ssh was not found at configured path: {executable}"

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
            raise ValueError(
                f"Local URL must include a valid port for localhost.run: {local_url}"
            ) from exc

        if local_port is None:
            raise ValueError(f"Local URL must include a port for localhost.run: {local_url}")

        local_host = local_connect_host(parsed.hostname)
        if local_host is None:
            raise ValueError(f"Local URL must include a host for localhost.run: {local_url}")

        return [
            str(self.executable),
            "-T",
            "-o",
            "ExitOnForwardFailure=yes",
            "-o",
            "LogLevel=ERROR",
            "-o",
            "StrictHostKeyChecking=accept-new",
            "-R",
            f"80:{bracket_ipv6_host(local_host)}:{local_port}",
            LOCALHOST_RUN_HOST,
        ]

    def parse_public_url(self, line: str) -> str | None:
        line = self.normalize_log_line(line)
        match = LOCALHOST_RUN_URL_RE.search(line)
        if match is None:
            return None
        return match.group(0)

    def normalize_log_line(self, line: str) -> str:
        return normalize_terminal_line(line)

    def get_public_url(self) -> str | None:
        return None

    def is_available(self) -> bool:
        return is_executable_available(self.executable)
