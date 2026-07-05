from __future__ import annotations

import socket
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class LocalServerConfig:
    host: str
    port: int
    scheme: str = "http"

    @property
    def url(self) -> str:
        return f"{self.scheme}://{bracket_ipv6_host(self.host)}:{self.port}"


def bracket_ipv6_host(host: str) -> str:
    if ":" in host and not host.startswith("["):
        return f"[{host}]"
    return host


def is_port_available(host: str, port: int) -> bool:
    try:
        with socket.create_server((host, port), reuse_port=False):
            return True
    except OSError:
        return False


def wait_until_listening(
    host: str,
    port: int,
    timeout: float = 20.0,
    interval: float = 0.2,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=interval):
                return True
        except OSError:
            time.sleep(interval)
    return False
