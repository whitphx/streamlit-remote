from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from streamlit_remote import cli
from streamlit_remote.https import HttpsMaterial


def test_parse_args_accepts_streamlit_args_after_separator() -> None:
    namespace = cli.parse_args(["app.py", "--port", "9000", "--", "--server.headless", "true"])

    assert namespace.app == Path("app.py")
    assert namespace.port == 9000
    assert namespace.streamlit_args == ["--server.headless", "true"]
    assert namespace.toolbar_mode == "developer"
    assert not namespace.no_browser


def test_build_streamlit_command() -> None:
    command = cli.build_streamlit_command(
        Path("app.py"),
        "127.0.0.1",
        8501,
        ["--server.runOnSave", "true"],
    )

    assert command[1:] == [
        "-m",
        "streamlit",
        "run",
        "app.py",
        "--server.address",
        "127.0.0.1",
        "--server.port",
        "8501",
        "--server.headless",
        "true",
        "--client.toolbarMode",
        "developer",
        "--server.runOnSave",
        "true",
    ]


def test_build_streamlit_command_with_viewer_toolbar_mode() -> None:
    command = cli.build_streamlit_command(
        Path("app.py"),
        "127.0.0.1",
        8501,
        toolbar_mode="viewer",
    )

    assert "--client.toolbarMode" in command
    assert command[command.index("--client.toolbarMode") + 1] == "viewer"


def test_streamlit_args_can_override_default_toolbar_mode() -> None:
    command = cli.build_streamlit_command(
        Path("app.py"),
        "127.0.0.1",
        8501,
        ["--client.toolbarMode", "auto"],
    )

    assert command[-2:] == ["--client.toolbarMode", "auto"]


def test_build_streamlit_command_with_https_material(tmp_path: Path) -> None:
    cert_file = tmp_path / "cert.pem"
    key_file = tmp_path / "key.pem"

    command = cli.build_streamlit_command(
        Path("app.py"),
        "127.0.0.1",
        8501,
        https_material=HttpsMaterial(cert_file=cert_file, key_file=key_file),
    )

    assert "--server.sslCertFile" in command
    assert str(cert_file) in command
    assert "--server.sslKeyFile" in command
    assert str(key_file) in command
    assert command.count("--server.headless") == 1
    assert command.count("--client.toolbarMode") == 1


def test_run_cli_rejects_missing_app(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.run_cli(["missing.py"])

    assert exit_code == 2
    assert "Streamlit app not found" in capsys.readouterr().err


def test_run_cli_rejects_cert_file_option_outside_cert_files_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    exit_code = cli.run_cli(["app.py", "--ssl-cert-file", "cert.pem"])

    assert exit_code == 2
    assert "can only be used with `--https cert-files`" in capsys.readouterr().err


def test_run_cli_dry_run_prints_commands_without_dependency_checks(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    monkeypatch.setattr(cli, "require_streamlit", lambda: pytest.fail("unexpected check"))

    exit_code = cli.run_cli([str(app_path), "--dry-run"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Streamlit command:" in captured.out
    assert "--client.toolbarMode developer" in captured.out
    assert "cloudflared tunnel --url http://localhost:8501" in captured.out


def test_run_cli_dry_run_can_set_toolbar_mode(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    exit_code = cli.run_cli([str(app_path), "--dry-run", "--toolbar-mode", "minimal"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "--client.toolbarMode minimal" in captured.out


def test_run_cli_dry_run_uses_custom_cloudflared_binary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    cloudflared_binary = tmp_path / "bin" / "cloudflared"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    exit_code = cli.run_cli(
        [
            str(app_path),
            "--dry-run",
            "--cloudflared-binary",
            str(cloudflared_binary),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert f"{cloudflared_binary} tunnel --url http://localhost:8501" in captured.out


def test_run_cli_dry_run_prints_managed_https_ngrok_command(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    exit_code = cli.run_cli(
        [
            str(app_path),
            "--dry-run",
            "--https",
            "self-signed",
            "--provider",
            "ngrok",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "--server.sslCertFile" in captured.out
    assert "--server.sslKeyFile" in captured.out
    assert "ngrok http https://localhost:8501" in captured.out
    assert "--log-level info" in captured.out
    assert "managed self-signed certificate" in captured.out


def test_run_cli_dry_run_uses_custom_ngrok_binary(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    ngrok_binary = tmp_path / "bin" / "ngrok"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    exit_code = cli.run_cli(
        [
            str(app_path),
            "--dry-run",
            "--provider",
            "ngrok",
            "--ngrok-binary",
            str(ngrok_binary),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert f"{ngrok_binary} http http://localhost:8501" in captured.out


def test_run_cli_dry_run_prints_ngrok_off_log_command(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    exit_code = cli.run_cli(
        [
            str(app_path),
            "--dry-run",
            "--provider",
            "ngrok",
            "--tunnel-log-level",
            "off",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "ngrok http http://localhost:8501 --log false" in captured.out


def test_run_cli_dry_run_prints_ngrok_oauth_policy_command(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    exit_code = cli.run_cli(
        [
            str(app_path),
            "--dry-run",
            "--provider",
            "ngrok",
            "--remote-auth",
            "oauth",
            "--oauth-provider",
            "github",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "ngrok http http://localhost:8501" in captured.out
    assert "--traffic-policy-file '<generated-ngrok-github-oauth-policy.yml>'" in captured.out


def test_run_cli_dry_run_defaults_ngrok_oauth_provider_to_google(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    exit_code = cli.run_cli(
        [
            str(app_path),
            "--dry-run",
            "--provider",
            "ngrok",
            "--remote-auth",
            "oauth",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "--traffic-policy-file '<generated-ngrok-google-oauth-policy.yml>'" in captured.out


def test_run_cli_rejects_oauth_provider_without_remote_auth(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    exit_code = cli.run_cli(
        [
            str(app_path),
            "--provider",
            "ngrok",
            "--oauth-provider",
            "github",
        ]
    )

    assert exit_code == 2
    assert "`--oauth-provider` can only be used with `--remote-auth oauth`" in (
        capsys.readouterr().err
    )


def test_run_cli_dry_run_prints_ngrok_custom_policy_command(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    policy_path = tmp_path / "policy.yml"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")
    policy_path.write_text("on_http_request: []\n", encoding="utf-8")

    exit_code = cli.run_cli(
        [
            str(app_path),
            "--dry-run",
            "--provider",
            "ngrok",
            "--ngrok-traffic-policy-file",
            str(policy_path),
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert f"--traffic-policy-file {policy_path}" in captured.out


def test_run_cli_rejects_remote_auth_with_cloudflare(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    exit_code = cli.run_cli([str(app_path), "--remote-auth", "oauth"])

    assert exit_code == 2
    assert "supported only with `--provider ngrok`" in capsys.readouterr().err


def test_run_cli_rejects_ngrok_binary_with_cloudflare(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    exit_code = cli.run_cli([str(app_path), "--ngrok-binary", str(tmp_path / "ngrok")])

    assert exit_code == 2
    assert "`--ngrok-binary` can only be used with `--provider ngrok`" in (capsys.readouterr().err)


def test_run_cli_rejects_cloudflared_binary_with_ngrok(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    exit_code = cli.run_cli(
        [
            str(app_path),
            "--provider",
            "ngrok",
            "--cloudflared-binary",
            str(tmp_path / "cloudflared"),
        ]
    )

    assert exit_code == 2
    assert "`--cloudflared-binary` can only be used with `--provider cloudflare`" in (
        capsys.readouterr().err
    )


def test_run_cli_rejects_mkcert_binary_without_mkcert_https(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    exit_code = cli.run_cli([str(app_path), "--mkcert-binary", str(tmp_path / "mkcert")])

    assert exit_code == 2
    assert "`--mkcert-binary` can only be used with `--https mkcert`" in capsys.readouterr().err


def test_run_cli_rejects_remote_auth_without_remote(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    exit_code = cli.run_cli(
        [
            str(app_path),
            "--provider",
            "ngrok",
            "--remote-auth",
            "oauth",
            "--no-remote",
        ]
    )

    assert exit_code == 2
    assert "`--remote-auth` requires remote access" in capsys.readouterr().err


def test_run_cli_rejects_custom_policy_with_generated_auth(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    policy_path = tmp_path / "policy.yml"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")
    policy_path.write_text("on_http_request: []\n", encoding="utf-8")

    exit_code = cli.run_cli(
        [
            str(app_path),
            "--provider",
            "ngrok",
            "--remote-auth",
            "oauth",
            "--ngrok-traffic-policy-file",
            str(policy_path),
        ]
    )

    assert exit_code == 2
    assert "cannot be combined with `--remote-auth`" in capsys.readouterr().err


def test_run_cli_rejects_missing_custom_policy_file(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    exit_code = cli.run_cli(
        [
            str(app_path),
            "--provider",
            "ngrok",
            "--ngrok-traffic-policy-file",
            str(tmp_path / "missing.yml"),
        ]
    )

    assert exit_code == 2
    assert "ngrok Traffic Policy file not found" in capsys.readouterr().err


def test_run_cli_dry_run_prints_cloudflare_self_signed_origin_flag(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    exit_code = cli.run_cli([str(app_path), "--dry-run", "--https", "self-signed"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "cloudflared tunnel --url https://localhost:8501 --no-tls-verify" in captured.out


def test_run_cli_dry_run_prints_mkcert_https_command(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    exit_code = cli.run_cli([str(app_path), "--dry-run", "--https", "mkcert", "--no-remote"])

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "--server.sslCertFile" in captured.out
    assert "--server.sslKeyFile" in captured.out
    assert "mkcert certificate will be prepared at runtime" in captured.out
    assert "Remote access: disabled" in captured.out


def test_run_cli_reports_missing_cloudflared(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    monkeypatch.setattr(cli, "require_streamlit", lambda: None)
    monkeypatch.setattr(cli, "is_port_available", lambda host, port: True)
    monkeypatch.setattr(cli, "get_provider", lambda name: UnavailableProvider())

    exit_code = cli.run_cli([str(app_path)])

    assert exit_code == 2
    assert "cloudflared was not found on PATH" in capsys.readouterr().err


def test_require_streamlit_reports_missing_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli.importlib.util, "find_spec", lambda name: None)

    with pytest.raises(cli.CliError, match="Streamlit is not installed"):
        cli.require_streamlit()


@dataclass
class UnavailableProvider:
    name: str = "cloudflare"
    log_prefix: str = "cloudflared"
    install_hint: str = "cloudflared was not found on PATH."

    def build_command(
        self,
        local_url: str,
        *,
        origin_tls_verify: bool = True,
        tunnel_log_level: str = "info",
        traffic_policy_file: Path | None = None,
    ) -> list[str]:
        return ["cloudflared", "tunnel", "--url", local_url]

    def parse_public_url(self, line: str) -> str | None:
        return None

    def get_public_url(self) -> str | None:
        return None

    def is_available(self) -> bool:
        return False


def test_should_print_tunnel_line_filters_by_level() -> None:
    assert cli.should_print_tunnel_line("lvl=info msg=start", "info")
    assert not cli.should_print_tunnel_line("lvl=info msg=start", "warn")
    assert cli.should_print_tunnel_line("lvl=warn msg=problem", "warn")
    assert cli.should_print_tunnel_line("lvl=error msg=problem", "warn")
    assert not cli.should_print_tunnel_line("lvl=warn msg=problem", "error")
    assert cli.should_print_tunnel_line("lvl=error msg=problem", "error")
    assert not cli.should_print_tunnel_line("lvl=error msg=problem", "off")


def test_open_browser_uses_webbrowser(monkeypatch: pytest.MonkeyPatch) -> None:
    opened: list[tuple[str, int]] = []

    monkeypatch.setattr(
        cli.webbrowser,
        "open",
        lambda url, new=0: opened.append((url, new)),
    )

    cli.open_browser("https://example.test")

    assert opened == [("https://example.test", 2)]


def test_run_no_remote_opens_local_https_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")
    opened: list[str] = []

    monkeypatch.setattr(cli, "require_streamlit", lambda: None)
    monkeypatch.setattr(cli, "is_port_available", lambda host, port: True)
    monkeypatch.setattr(cli, "prepare_cli_https_material", lambda namespace: None)
    monkeypatch.setattr(cli, "open_browser", opened.append)
    monkeypatch.setattr(
        cli,
        "start_logged_process",
        lambda command, prefix, **kwargs: SimpleNamespace(
            process=SimpleNamespace(
                returncode=0,
                poll=lambda: 0,
                terminate=lambda: None,
                wait=lambda timeout=None: 0,
            ),
            prefix=prefix,
            output_thread=SimpleNamespace(join=lambda timeout=None: None),
        ),
    )

    namespace = cli.parse_args([str(app_path), "--https", "self-signed", "--no-remote"])
    exit_code = cli.run(namespace)

    assert exit_code == 0
    assert opened == ["https://localhost:8501"]


def test_run_no_remote_no_browser_does_not_open_local_url(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")
    opened: list[str] = []

    monkeypatch.setattr(cli, "require_streamlit", lambda: None)
    monkeypatch.setattr(cli, "is_port_available", lambda host, port: True)
    monkeypatch.setattr(cli, "prepare_cli_https_material", lambda namespace: None)
    monkeypatch.setattr(cli, "open_browser", opened.append)
    monkeypatch.setattr(
        cli,
        "start_logged_process",
        lambda command, prefix, **kwargs: SimpleNamespace(
            process=SimpleNamespace(
                returncode=0,
                poll=lambda: 0,
                terminate=lambda: None,
                wait=lambda timeout=None: 0,
            ),
            prefix=prefix,
            output_thread=SimpleNamespace(join=lambda timeout=None: None),
        ),
    )

    namespace = cli.parse_args(
        [str(app_path), "--https", "self-signed", "--no-remote", "--no-browser"]
    )
    exit_code = cli.run(namespace)

    assert exit_code == 0
    assert opened == []
