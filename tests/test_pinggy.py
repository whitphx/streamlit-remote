from pathlib import Path

import pytest

from streamlit_remote.providers.pinggy import PinggyProvider


def test_build_pinggy_command() -> None:
    provider = PinggyProvider()

    assert provider.build_command("http://localhost:8501") == [
        "ssh",
        "-T",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "LogLevel=ERROR",
        "-p",
        "443",
        "-R0:localhost:8501",
        "free.pinggy.io",
    ]


def test_build_pinggy_command_rewrites_any_address_host() -> None:
    provider = PinggyProvider()

    assert provider.build_command("http://0.0.0.0:8501") == [
        "ssh",
        "-T",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "LogLevel=ERROR",
        "-p",
        "443",
        "-R0:127.0.0.1:8501",
        "free.pinggy.io",
    ]


def test_build_pinggy_command_rewrites_ipv6_any_address_host() -> None:
    provider = PinggyProvider()

    assert provider.build_command("http://[::]:8501") == [
        "ssh",
        "-T",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "LogLevel=ERROR",
        "-p",
        "443",
        "-R0:[::1]:8501",
        "free.pinggy.io",
    ]


def test_build_pinggy_command_with_custom_binary() -> None:
    provider = PinggyProvider(executable=Path("/opt/ssh"))

    assert provider.build_command("http://127.0.0.1:8501") == [
        "/opt/ssh",
        "-T",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "LogLevel=ERROR",
        "-p",
        "443",
        "-R0:127.0.0.1:8501",
        "free.pinggy.io",
    ]


def test_build_pinggy_command_requires_port() -> None:
    provider = PinggyProvider()

    with pytest.raises(ValueError, match="must include a port"):
        provider.build_command("http://localhost")


def test_parse_pinggy_public_url() -> None:
    provider = PinggyProvider()

    line = "You can access your tunnel at https://example-123.free.pinggy.link"

    assert provider.parse_public_url(line) == "https://example-123.free.pinggy.link"


@pytest.mark.parametrize(
    "url",
    [
        "https://pciaj-219-120-90-243.free.pinggy.net",
        "https://vgdfc-219-120-90-243.run.pinggy-free.link",
    ],
)
def test_parse_pinggy_public_url_from_observed_hosts(url: str) -> None:
    provider = PinggyProvider()

    assert provider.parse_public_url(url) == url


def test_parse_pinggy_public_url_from_terminal_output() -> None:
    provider = PinggyProvider()

    line = "\x1b[2K\rYou can access your tunnel at https://example-123.free.pinggy.link"

    assert provider.parse_public_url(line) == "https://example-123.free.pinggy.link"


def test_parse_pinggy_ignores_unrelated_https_url() -> None:
    provider = PinggyProvider()

    assert provider.parse_public_url("Docs: https://pinggy.io/docs/") is None
    assert provider.parse_public_url("Upgrade: https://dashboard.pinggy.io") is None


def test_parse_pinggy_ignores_http_tunnel_urls() -> None:
    provider = PinggyProvider()

    assert provider.parse_public_url("http://pciaj-219-120-90-243.free.pinggy.net") is None
    assert provider.parse_public_url("http://vgdfc-219-120-90-243.run.pinggy-free.link") is None


def test_normalize_pinggy_log_line_strips_terminal_sequences() -> None:
    provider = PinggyProvider()

    assert provider.normalize_log_line("\x1b[2K\rready\x1b[0m") == "ready"
