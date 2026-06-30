from __future__ import annotations

from io import StringIO

from rich.console import Console

from streamlit_remote.runtime_display import (
    PlainRuntimeDisplay,
    RichRuntimeDisplay,
    SwitchableRuntimeDisplay,
    make_runtime_display,
)


def test_make_runtime_display_selects_plain_output() -> None:
    display = make_runtime_display(use_tui=False)

    assert isinstance(display, PlainRuntimeDisplay)


def test_make_runtime_display_selects_rich_output() -> None:
    display = make_runtime_display(use_tui=True)

    assert isinstance(display, SwitchableRuntimeDisplay)


def test_plain_runtime_display_writes_log_and_shortcut_help() -> None:
    output = StringIO()
    error_output = StringIO()
    display = PlainRuntimeDisplay(output=output, error_output=error_output)

    display.set_local_url("http://localhost:8501")
    display.set_remote_url("https://example.test")
    display.set_shortcuts_visible(True)
    display.log("streamlit", "ready")
    display.error("problem")

    assert "Streamlit local URL:" in output.getvalue()
    assert "https://example.test" in output.getvalue()
    assert "r + Enter" in output.getvalue()
    assert "[streamlit] ready" in output.getvalue()
    assert "problem" in error_output.getvalue()


def test_switchable_runtime_display_replays_recent_logs_in_plain_output() -> None:
    plain_output = StringIO()
    rich_display = RichRuntimeDisplay(console=Console(file=StringIO()))
    display = SwitchableRuntimeDisplay(
        rich_display,
        PlainRuntimeDisplay(output=plain_output, error_output=plain_output),
    )

    display.set_local_url("http://localhost:8501")
    display.set_remote_url("https://example.test")
    display.set_shortcuts_visible(True)
    display.log("streamlit", "ready")

    assert display.toggle_display()
    assert not display.switch_to_plain()
    display.log("ngrok", "future")
    assert display.toggle_display()
    assert not display.switch_to_rich()
    display.log("streamlit", "back in tui")

    rendered = plain_output.getvalue()
    assert "http://localhost:8501" in rendered
    assert "https://example.test" in rendered
    assert "r + Enter" in rendered
    assert "t + Enter" in rendered
    assert "Switched to plain log output. Recent logs:" in rendered
    assert "[streamlit] ready" in rendered
    assert "[ngrok] future" in rendered
    assert "back in tui" not in rendered
    assert list(rich_display._logs)[-1] == ("streamlit", "back in tui")


def test_rich_runtime_display_limits_visible_log_lines() -> None:
    output = StringIO()
    console = Console(file=output, width=80, height=16, force_terminal=True)
    display = RichRuntimeDisplay(console=console, max_log_lines=100)

    for index in range(20):
        display.log("streamlit", f"line-{index}")

    console.print(display._render_log_panel())
    rendered = output.getvalue()

    assert "line-19" in rendered
    assert "line-0" not in rendered


def test_rich_runtime_display_uses_terminal_height_for_layout() -> None:
    console = Console(file=StringIO(), width=80, height=16, force_terminal=True)
    display = RichRuntimeDisplay(console=console)

    status_height, log_height, shortcuts_height = display._layout_heights()

    assert status_height + log_height + shortcuts_height == 16
    assert log_height >= 3
    assert display._render_log_panel(height=log_height).height == log_height


def test_rich_runtime_display_uses_alternate_screen() -> None:
    console = Console(file=StringIO(), width=80, height=16, force_terminal=True)
    display = RichRuntimeDisplay(console=console)

    display.start()
    try:
        assert display._live is not None
        assert display._live._screen is True
        assert display._live.vertical_overflow == "crop"
    finally:
        display.stop()


def test_rich_runtime_display_truncates_long_log_lines() -> None:
    output = StringIO()
    console = Console(file=output, width=40, height=12, force_terminal=True)
    display = RichRuntimeDisplay(console=console)
    long_message = "x" * 120

    display.log("streamlit", long_message)

    console.print(display._render_log_panel())
    rendered = output.getvalue()

    assert "..." in rendered
    assert long_message not in rendered
