from pathlib import Path

import pytest

from streamlit_remote.providers.ngrok import (
    MANAGED_OAUTH_PROVIDERS,
    NgrokProvider,
    build_managed_oauth_policy,
    parse_agent_api_public_url,
    prepare_managed_oauth_policy,
)


def test_build_ngrok_command_for_http_upstream() -> None:
    provider = NgrokProvider()

    assert provider.build_command("http://127.0.0.1:8501") == [
        "ngrok",
        "http",
        "http://127.0.0.1:8501",
        "--log",
        "stdout",
        "--log-format",
        "logfmt",
        "--log-level",
        "info",
    ]

    assert provider.build_command(
        "http://127.0.0.1:8501",
        origin_tls_verify=False,
    ) == [
        "ngrok",
        "http",
        "http://127.0.0.1:8501",
        "--log",
        "stdout",
        "--log-format",
        "logfmt",
        "--log-level",
        "info",
    ]

    assert provider.build_command(
        "http://127.0.0.1:8501",
        tunnel_log_level="warn",
    ) == [
        "ngrok",
        "http",
        "http://127.0.0.1:8501",
        "--log",
        "stdout",
        "--log-format",
        "logfmt",
        "--log-level",
        "warn",
    ]

    assert provider.build_command(
        "http://127.0.0.1:8501",
        tunnel_log_level="off",
    ) == [
        "ngrok",
        "http",
        "http://127.0.0.1:8501",
        "--log",
        "false",
    ]

    assert provider.build_command(
        "http://127.0.0.1:8501",
        traffic_policy_file=Path("policy.yml"),
    ) == [
        "ngrok",
        "http",
        "http://127.0.0.1:8501",
        "--traffic-policy-file",
        "policy.yml",
        "--log",
        "stdout",
        "--log-format",
        "logfmt",
        "--log-level",
        "info",
    ]


def test_build_ngrok_command_for_https_upstream() -> None:
    provider = NgrokProvider()

    assert provider.build_command("https://127.0.0.1:8501") == [
        "ngrok",
        "http",
        "https://127.0.0.1:8501",
        "--log",
        "stdout",
        "--log-format",
        "logfmt",
        "--log-level",
        "info",
    ]


def test_parse_ngrok_forwarding_url() -> None:
    provider = NgrokProvider()

    line = "Forwarding  https://abc-123.ngrok-free.app -> http://localhost:8501"

    assert provider.parse_public_url(line) == "https://abc-123.ngrok-free.app"


def test_parse_ngrok_custom_domain_url() -> None:
    provider = NgrokProvider()

    line = "Forwarding  https://demo.example.com -> http://localhost:8501"

    assert provider.parse_public_url(line) == "https://demo.example.com"


def test_parse_ngrok_ignores_non_forwarding_line() -> None:
    provider = NgrokProvider()

    assert provider.parse_public_url("Session Status online") is None


def test_parse_agent_api_public_url_returns_https_tunnel() -> None:
    assert (
        parse_agent_api_public_url(
            {
                "tunnels": [
                    {"public_url": "http://abc.ngrok-free.app"},
                    {"public_url": "https://abc.ngrok-free.app"},
                ]
            }
        )
        == "https://abc.ngrok-free.app"
    )


def test_parse_agent_api_public_url_returns_none_without_https_tunnel() -> None:
    assert parse_agent_api_public_url({"tunnels": [{"public_url": "http://abc"}]}) is None


@pytest.mark.parametrize("oauth_provider", MANAGED_OAUTH_PROVIDERS)
def test_build_managed_oauth_policy(oauth_provider: str) -> None:
    assert build_managed_oauth_policy(oauth_provider) == (
        "on_http_request:\n"
        "  - actions:\n"
        "      - type: oauth\n"
        "        config:\n"
        f"          provider: {oauth_provider}\n"
    )


def test_build_managed_oauth_policy_rejects_unknown_provider() -> None:
    with pytest.raises(ValueError, match="Unsupported ngrok managed OAuth provider"):
        build_managed_oauth_policy("unknown")


def test_prepare_managed_oauth_policy_creates_and_cleans_up_file() -> None:
    policy = prepare_managed_oauth_policy("google")
    policy_file = policy.traffic_policy_file

    assert policy_file.exists()
    assert "provider: google" in policy_file.read_text(encoding="utf-8")

    policy.cleanup()

    assert not policy_file.exists()
