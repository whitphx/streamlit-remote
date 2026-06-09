from streamlit_remote.providers.ngrok import NgrokProvider, parse_agent_api_public_url


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
