from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import pytest

from streamlit_remote import cli
from streamlit_remote.https import HttpsMaterial


def test_parse_args_accepts_streamlit_args_after_separator() -> None:
    namespace = cli.parse_args(
        ["app.py", "--port", "9000", "--", "--server.headless", "true"]
    )

    assert namespace.app == Path("app.py")
    assert namespace.port == 9000
    assert namespace.streamlit_args == ["--server.headless", "true"]
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
        "--server.runOnSave",
        "true",
    ]


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
    assert "cloudflared tunnel --url http://localhost:8501" in captured.out


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
