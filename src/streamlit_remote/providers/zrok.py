from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from streamlit_remote.providers.executables import is_executable_available

ANSI_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
ANSI_OSC8_URL_RE = re.compile(r"\x1b\]8;[^;]*;([^\x07\x1b]*)(?:\x07|\x1b\\)")
ANSI_OSC_RE = re.compile(r"\x1b\][^\x07]*(?:\x07|\x1b\\)")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
HTTPS_URL_RE = re.compile(r"https://[^\s<>\]]+")
ZROK_SHARE_HOST_RE = re.compile(r"(?<![\w.-])([A-Za-z0-9-]+\.shares?\.zrok\.io)\b")


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
        if parsed.port is None:
            raise ValueError(f"Local URL must include a port for zrok: {local_url}")

        local_host = "127.0.0.1" if parsed.hostname in {"0.0.0.0", "::"} else parsed.hostname
        if local_host is None:
            raise ValueError(f"Local URL must include a host for zrok: {local_url}")

        return [
            str(self.executable),
            "share",
            "public",
            "--headless",
            f"{local_host}:{parsed.port}",
        ]

    def parse_public_url(self, line: str) -> str | None:
        clean_line = strip_terminal_sequences(line)
        for candidate in HTTPS_URL_RE.findall(clean_line):
            candidate = candidate.rstrip(".,;)")
            parsed = urlparse(candidate)
            if parsed.scheme == "https" and parsed.netloc:
                return candidate

        match = ZROK_SHARE_HOST_RE.search(clean_line)
        if match is not None:
            return f"https://{match.group(1)}"

        return None

    def get_public_url(self) -> str | None:
        return None

    def is_available(self) -> bool:
        return is_executable_available(self.executable)


def strip_terminal_sequences(text: str) -> str:
    with_osc8_urls = ANSI_OSC8_URL_RE.sub(r" \1 ", text)
    without_osc = ANSI_OSC_RE.sub("", with_osc8_urls)
    without_csi = ANSI_CSI_RE.sub("", without_osc)
    return CONTROL_CHARS_RE.sub("", without_csi)
