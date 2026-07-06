from pathlib import Path

import pytest

from streamlit_remote.providers.localhost_run import LocalhostRunProvider


def test_build_localhost_run_command() -> None:
    provider = LocalhostRunProvider()

    assert provider.build_command("http://localhost:8501") == [
        "ssh",
        "-T",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "LogLevel=ERROR",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-R",
        "80:localhost:8501",
        "localhost.run",
    ]


def test_build_localhost_run_command_rewrites_any_address_host() -> None:
    provider = LocalhostRunProvider()

    assert provider.build_command("http://0.0.0.0:8501") == [
        "ssh",
        "-T",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "LogLevel=ERROR",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-R",
        "80:127.0.0.1:8501",
        "localhost.run",
    ]


def test_build_localhost_run_command_rewrites_ipv6_any_address_host() -> None:
    provider = LocalhostRunProvider()

    assert provider.build_command("http://[::]:8501") == [
        "ssh",
        "-T",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "LogLevel=ERROR",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-R",
        "80:[::1]:8501",
        "localhost.run",
    ]


def test_build_localhost_run_command_with_custom_binary() -> None:
    provider = LocalhostRunProvider(executable=Path("/opt/ssh"))

    assert provider.build_command("http://127.0.0.1:8501") == [
        "/opt/ssh",
        "-T",
        "-o",
        "ExitOnForwardFailure=yes",
        "-o",
        "LogLevel=ERROR",
        "-o",
        "StrictHostKeyChecking=accept-new",
        "-R",
        "80:127.0.0.1:8501",
        "localhost.run",
    ]


def test_build_localhost_run_command_requires_port() -> None:
    provider = LocalhostRunProvider()

    with pytest.raises(ValueError, match="must include a port"):
        provider.build_command("http://localhost")


def test_parse_localhost_run_public_url() -> None:
    provider = LocalhostRunProvider()

    line = "77a8dedff950e6.lhr.life tunneled with tls termination, https://77a8dedff950e6.lhr.life"

    assert provider.parse_public_url(line) == "https://77a8dedff950e6.lhr.life"


def test_parse_localhost_run_ignores_unrelated_https_url() -> None:
    provider = LocalhostRunProvider()

    assert provider.parse_public_url("Docs: https://localhost.run/docs/") is None
    assert provider.parse_public_url("Admin: https://admin.localhost.run/") is None


def test_normalize_localhost_run_log_line_strips_terminal_sequences() -> None:
    provider = LocalhostRunProvider()

    assert provider.normalize_log_line("\x1b[7m  \x1b[0m") == ""
