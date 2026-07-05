from streamlit_remote.server import LocalServerConfig, bracket_ipv6_host


def test_local_server_url_brackets_ipv6_host() -> None:
    assert LocalServerConfig(host="::1", port=8501).url == "http://[::1]:8501"


def test_bracket_ipv6_host_leaves_non_ipv6_hosts_unchanged() -> None:
    assert bracket_ipv6_host("localhost") == "localhost"
    assert bracket_ipv6_host("127.0.0.1") == "127.0.0.1"
    assert bracket_ipv6_host("[::1]") == "[::1]"
