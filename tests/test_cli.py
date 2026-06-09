from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from streamlit_remote import cli


def test_parse_args_accepts_streamlit_args_after_separator() -> None:
    namespace = cli.parse_args(
        ["app.py", "--port", "9000", "--", "--server.headless", "true"]
    )

    assert namespace.app == Path("app.py")
    assert namespace.port == 9000
    assert namespace.streamlit_args == ["--server.headless", "true"]


def test_build_streamlit_command() -> None:
    command = cli.build_streamlit_command(
        Path("app.py"),
        "127.0.0.1",
        8501,
        ["--server.headless", "true"],
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
    ]


def test_run_cli_rejects_missing_app(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = cli.run_cli(["missing.py"])

    assert exit_code == 2
    assert "Streamlit app not found" in capsys.readouterr().err


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
    assert "cloudflared tunnel --url http://127.0.0.1:8501" in captured.out


def test_run_cli_reports_missing_cloudflared(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app_path = tmp_path / "app.py"
    app_path.write_text("import streamlit as st\n", encoding="utf-8")

    monkeypatch.setattr(cli, "require_streamlit", lambda: None)
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

    def build_command(self, local_url: str) -> list[str]:
        return ["cloudflared", "tunnel", "--url", local_url]

    def parse_public_url(self, line: str) -> str | None:
        return None

    def is_available(self) -> bool:
        return False
