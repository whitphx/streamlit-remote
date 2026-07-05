from streamlit_remote.server import LocalServerConfig


def test_local_server_url_brackets_ipv6_host() -> None:
    assert LocalServerConfig(host="::1", port=8501).url == "http://[::1]:8501"
