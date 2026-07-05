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
        "localhost:8501",
    ]


def test_build_zrok_command_rewrites_any_address_host() -> None:
    provider = ZrokProvider()

    assert provider.build_command("http://0.0.0.0:8501") == [
        "zrok",
        "share",
        "public",
        "--headless",
        "127.0.0.1:8501",
    ]


def test_build_zrok_command_with_custom_binary() -> None:
    provider = ZrokProvider(executable=Path("/opt/zrok"))

    assert provider.build_command("http://127.0.0.1:8501") == [
        "/opt/zrok",
        "share",
        "public",
        "--headless",
        "127.0.0.1:8501",
    ]


def test_build_zrok_command_requires_port() -> None:
    provider = ZrokProvider()

    with pytest.raises(ValueError, match="must include a port"):
        provider.build_command("http://localhost")


def test_parse_zrok_public_url() -> None:
    provider = ZrokProvider()

    line = "access your zrok share at https://example-share.share.zrok.io"

    assert provider.parse_public_url(line) == "https://example-share.share.zrok.io"


def test_parse_zrok_public_url_strips_trailing_punctuation() -> None:
    provider = ZrokProvider()

    line = "share ready (https://example-share.share.zrok.io)."

    assert provider.parse_public_url(line) == "https://example-share.share.zrok.io"


def test_parse_zrok_public_url_with_ansi_styling() -> None:
    provider = ZrokProvider()

    line = "\x1b[32mhttps://example-share.share.zrok.io\x1b[0m"

    assert provider.parse_public_url(line) == "https://example-share.share.zrok.io"


def test_parse_zrok_public_url_with_terminal_hyperlink() -> None:
    provider = ZrokProvider()

    line = (
        "\x1b]8;;https://example-share.share.zrok.io\x1b\\"
        "https://example-share.share.zrok.io"
        "\x1b]8;;\x1b\\"
    )

    assert provider.parse_public_url(line) == "https://example-share.share.zrok.io"


def test_parse_zrok_public_url_from_terminal_hyperlink_target() -> None:
    provider = ZrokProvider()

    line = "\x1b]8;;https://example-share.share.zrok.io\x1b\\open share\x1b]8;;\x1b\\"

    assert provider.parse_public_url(line) == "https://example-share.share.zrok.io"


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
