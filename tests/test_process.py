from __future__ import annotations

from typing import Any

import pytest

from streamlit_remote import process


def test_start_logged_process_merges_environment_overrides(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    monkeypatch.setenv("STREAMLIT_REMOTE_TEST_ENV", "kept")

    class FakePopen:
        def __init__(self, command: list[str], **kwargs: Any) -> None:
            self.stdout: list[str] = []
            captured["command"] = command
            captured["kwargs"] = kwargs

    monkeypatch.setattr(process.subprocess, "Popen", FakePopen)

    handle = process.start_logged_process(
        ["streamlit"],
        "streamlit",
        env={"COLUMNS": "24"},
    )
    handle.output_thread.join(timeout=1)

    assert captured["command"] == ["streamlit"]
    assert captured["kwargs"]["env"]["STREAMLIT_REMOTE_TEST_ENV"] == "kept"
    assert captured["kwargs"]["env"]["COLUMNS"] == "24"
