from __future__ import annotations

from pathlib import Path

import pytest

from streamlit_remote.providers.executables import is_executable_available


def test_explicit_symlink_to_executable_is_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = make_executable(tmp_path / "actual-ngrok")
    link = tmp_path / "ngrok"
    link.symlink_to(target)
    monkeypatch.setattr("streamlit_remote.providers.executables.shutil.which", lambda name: None)

    assert is_executable_available(link)


def test_path_lookup_symlink_to_executable_is_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = make_executable(tmp_path / "actual-cloudflared")
    link = tmp_path / "cloudflared"
    link.symlink_to(target)
    monkeypatch.setattr(
        "streamlit_remote.providers.executables.shutil.which",
        lambda name: str(link) if name == "cloudflared" else None,
    )

    assert is_executable_available("cloudflared")


def test_missing_symlink_target_is_not_available(tmp_path: Path) -> None:
    link = tmp_path / "ngrok"
    link.symlink_to(tmp_path / "missing-ngrok")

    assert not is_executable_available(link)


def make_executable(path: Path) -> Path:
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)
    return path
