from pathlib import Path

import pytest

from streamlit_remote.providers.zrok import ZrokProvider


def test_build_zrok_command() -> None:
    provider = ZrokProvider()

    assert provider.build_command("http://localhost:8501") == [
        "zrok",
        "share",
        "public",
        "--headless",
        "http://localhost:8501",
    ]


def test_build_zrok_command_rewrites_any_address_host() -> None:
    provider = ZrokProvider()

    assert provider.build_command("http://0.0.0.0:8501") == [
        "zrok",
        "share",
        "public",
        "--headless",
        "http://127.0.0.1:8501",
    ]


def test_build_zrok_command_rewrites_ipv6_any_address_host() -> None:
    provider = ZrokProvider()

    assert provider.build_command("http://[::]:8501") == [
        "zrok",
        "share",
        "public",
        "--headless",
        "http://[::1]:8501",
    ]


def test_build_zrok_command_with_custom_binary() -> None:
    provider = ZrokProvider(executable=Path("/opt/zrok"))

    assert provider.build_command("http://127.0.0.1:8501") == [
        "/opt/zrok",
        "share",
        "public",
        "--headless",
        "http://127.0.0.1:8501",
    ]


def test_build_zrok_command_for_https_upstream() -> None:
    provider = ZrokProvider()

    assert provider.build_command("https://127.0.0.1:8501") == [
        "zrok",
        "share",
        "public",
        "--headless",
        "https://127.0.0.1:8501",
    ]


def test_build_zrok_command_for_self_signed_https_upstream() -> None:
    provider = ZrokProvider()

    assert provider.build_command("https://127.0.0.1:8501", origin_tls_verify=False) == [
        "zrok",
        "share",
        "public",
        "--headless",
        "--insecure",
        "https://127.0.0.1:8501",
    ]


def test_build_zrok_command_brackets_ipv6_host() -> None:
    provider = ZrokProvider()

    assert provider.build_command("http://[::1]:8501") == [
        "zrok",
        "share",
        "public",
        "--headless",
        "http://[::1]:8501",
    ]


def test_build_zrok_command_requires_port() -> None:
    provider = ZrokProvider()

    with pytest.raises(ValueError, match="must include a port"):
        provider.build_command("http://localhost")


def test_parse_zrok_public_url() -> None:
    provider = ZrokProvider()

    line = "access your zrok share at https://example-share.shares.zrok.io"

    assert provider.parse_public_url(line) == "https://example-share.shares.zrok.io"


def test_parse_zrok_public_url_strips_trailing_punctuation() -> None:
    provider = ZrokProvider()

    line = '"msg":"share ready https://example-share.shares.zrok.io"}'

    assert provider.parse_public_url(line) == "https://example-share.shares.zrok.io"


def test_parse_zrok_public_url_ignores_unrelated_https_url() -> None:
    provider = ZrokProvider()

    line = (
        '{"msg":"see https://github.com/openziti/zrok/releases before using '
        'yy6211g7d8pk.shares.zrok.io"}'
    )

    assert provider.parse_public_url(line) == "https://yy6211g7d8pk.shares.zrok.io"


def test_parse_zrok_ignores_unrelated_https_url_without_share_host() -> None:
    provider = ZrokProvider()

    line = '{"msg":"see https://github.com/openziti/zrok/releases"}'

    assert provider.parse_public_url(line) is None


def test_parse_zrok_public_url_from_json_log_host() -> None:
    provider = ZrokProvider()

    line = (
        '{"time":"2026-07-05T19:16:06.302791+09:00","level":"INFO",'
        '"msg":"access your zrok share at the following endpoints:\\n '
        'yy6211g7d8pk.shares.zrok.io"}'
    )

    assert provider.parse_public_url(line) == "https://yy6211g7d8pk.shares.zrok.io"


def test_parse_zrok_ignores_non_https_line() -> None:
    provider = ZrokProvider()

    assert provider.parse_public_url("sharing target localhost:8501") is None
