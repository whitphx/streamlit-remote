from streamlit_remote.providers.cloudflare import CloudflareQuickTunnelProvider


def test_build_cloudflare_quick_tunnel_command() -> None:
    provider = CloudflareQuickTunnelProvider()

    assert provider.build_command("http://127.0.0.1:8501") == [
        "cloudflared",
        "tunnel",
        "--url",
        "http://127.0.0.1:8501",
    ]


def test_build_cloudflare_quick_tunnel_command_without_origin_tls_verify() -> None:
    provider = CloudflareQuickTunnelProvider()

    assert provider.build_command(
        "https://127.0.0.1:8501",
        origin_tls_verify=False,
    ) == [
        "cloudflared",
        "tunnel",
        "--url",
        "https://127.0.0.1:8501",
        "--no-tls-verify",
    ]


def test_parse_trycloudflare_url_from_representative_log_line() -> None:
    provider = CloudflareQuickTunnelProvider()

    line = "Your quick Tunnel has been created! Visit: https://plain-moon-42.trycloudflare.com"

    assert provider.parse_public_url(line) == "https://plain-moon-42.trycloudflare.com"


def test_parse_trycloudflare_url_from_noisy_log_line() -> None:
    provider = CloudflareQuickTunnelProvider()

    line = (
        "2026-06-09T12:00:00Z INF "
        "+--------------------------------------------------------------------------------------+ "
        "https://demo.trycloudflare.com"
    )

    assert provider.parse_public_url(line) == "https://demo.trycloudflare.com"


def test_parse_public_url_returns_none_for_unrelated_line() -> None:
    provider = CloudflareQuickTunnelProvider()

    assert provider.parse_public_url("INF Starting tunnel metrics server") is None
