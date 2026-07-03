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
    assert "r:" in output.getvalue()
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
    assert "r" in rendered
    assert "t:" in rendered
    assert "Switched to plain log output. Recent logs:" in rendered
    assert "[streamlit] ready" in rendered
    assert "[ngrok] future" in rendered
    assert "back in tui" not in rendered
    assert list(rich_display._logs)[-1] == ("streamlit", "back in tui")


def test_switchable_runtime_display_replays_logs_after_process_error() -> None:
    plain_output = StringIO()
    display = SwitchableRuntimeDisplay(
        RichRuntimeDisplay(console=Console(file=StringIO())),
        PlainRuntimeDisplay(output=plain_output, error_output=plain_output),
    )

    display.log("streamlit", "first line")
    display.log("streamlit", "failure detail")

    display.report_process_exit("streamlit", 2)

    rendered = plain_output.getvalue()
    assert "error: streamlit exited with code 2." in rendered
    assert "Recent logs:" in rendered
    assert "[streamlit] first line" in rendered
    assert "[streamlit] failure detail" in rendered


def test_switchable_runtime_display_does_not_replay_logs_after_plain_process_error() -> None:
    plain_output = StringIO()
    display = SwitchableRuntimeDisplay(
        RichRuntimeDisplay(console=Console(file=StringIO())),
        PlainRuntimeDisplay(output=plain_output, error_output=plain_output),
    )

    display.switch_to_plain()
    plain_output.truncate(0)
    plain_output.seek(0)
    display.log("streamlit", "already visible")
    display.report_process_exit("streamlit", 2)

    rendered = plain_output.getvalue()
    assert "[streamlit] already visible" in rendered
    assert "error: streamlit exited with code 2." in rendered
    assert "Recent logs:" not in rendered


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


def test_rich_runtime_display_scrolls_log_window() -> None:
    output = StringIO()
    console = Console(file=output, width=80, height=13, force_terminal=True)
    display = RichRuntimeDisplay(console=console, max_log_lines=100)

    for index in range(12):
        display.log("streamlit", f"line-{index}")

    assert display.scroll_log_up()
    console.print(display._render_log_panel())
    rendered = output.getvalue()

    assert "line-7" in rendered
    assert "line-11" not in rendered

    output.truncate(0)
    output.seek(0)
    assert display.scroll_log_down()
    console.print(display._render_log_panel())
    rendered = output.getvalue()

    assert "line-11" in rendered


def test_rich_runtime_display_preserves_scrolled_log_window_after_new_logs() -> None:
    output = StringIO()
    console = Console(file=output, width=80, height=13, force_terminal=True)
    display = RichRuntimeDisplay(console=console, max_log_lines=100)

    for index in range(12):
        display.log("streamlit", f"line-{index}")

    assert display.scroll_log_up()
    display.log("streamlit", "line-12")
    console.print(display._render_log_panel())
    rendered = output.getvalue()

    assert "line-7" in rendered
    assert "line-12" not in rendered


def test_rich_runtime_display_scrolls_from_traceback_pinned_window() -> None:
    console = Console(file=StringIO(), width=80, height=16, force_terminal=True)
    display = RichRuntimeDisplay(console=console, max_log_lines=200)

    display.log("streamlit", "")
    display.log("streamlit", "/app/example.py:8 in <module>")
    display.log("streamlit", "❱  8 │   raise RuntimeError(")
    display.log("streamlit", "─────────────────────────────────────────────────────")
    display.log("streamlit", "RuntimeError: boom")
    for index in range(100):
        display.log("cloudflared", f"precheck status=pass target={index}")

    pinned_logs = display._visible_logs()

    assert "RuntimeError: boom" in [line for _, line in pinned_logs]
    assert not display.scroll_log_up()
    assert display._visible_logs() == pinned_logs


def test_rich_runtime_display_preserves_deferred_tail_window_after_streamlit_log() -> None:
    console = Console(file=StringIO(), width=80, height=13, force_terminal=True)
    display = RichRuntimeDisplay(console=console, max_log_lines=100)

    display.log("streamlit", "")
    display.log("streamlit", "│ /app/example.py:8 in <module> │")
    display.log("streamlit", "❱  8 │ raise RuntimeError(")
    display.log("streamlit", "────────────────────")
    display.log("streamlit", "RuntimeError: boom")
    for index in range(8):
        display.log("cloudflared", f"tunnel msg {index}")
    for _ in range(5):
        assert display.scroll_log_down()

    visible_before = display._visible_logs()
    display.log("streamlit", "new Streamlit log")

    assert display._visible_logs() == visible_before


def test_rich_runtime_display_resets_log_scroll_to_latest() -> None:
    output = StringIO()
    console = Console(file=output, width=80, height=13, force_terminal=True)
    display = RichRuntimeDisplay(console=console, max_log_lines=100)

    for index in range(12):
        display.log("streamlit", f"line-{index}")

    assert display.scroll_log_up()
    assert display.reset_log_scroll()
    console.print(display._render_log_panel())
    rendered = output.getvalue()

    assert "line-11" in rendered


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


def test_rich_runtime_display_shortcuts_fit_width_80() -> None:
    output = StringIO()
    console = Console(file=output, width=80, height=16, force_terminal=True, color_system=None)
    display = RichRuntimeDisplay(console=console)

    display.set_shortcuts_visible(True)
    console.print(display._render_shortcuts_panel(height=3))
    rendered = output.getvalue()

    assert "Esc latest" in rendered
    assert "Ctrl+C stop" in rendered


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


def test_rich_runtime_display_preserves_streamlit_traceback_frame() -> None:
    output = StringIO()
    console = Console(file=output, width=60, height=12, force_terminal=True, color_system=None)
    display = RichRuntimeDisplay(console=console)

    display.log("streamlit", "")
    display.log("streamlit", "│ /app/example.py:8 in <module>                     │")
    display.log("cloudflared", "pass target=region1.v2.argotunnel.com")
    display.log("streamlit", "❱  8 │   raise RuntimeError(")
    display.log("streamlit", "─────────────────────────────────────────────────────")
    display.log("streamlit", "RuntimeError: boom")

    console.print(display._render_log_panel(height=8))
    rendered = output.getvalue()
    formatted_line = display._format_raw_streamlit_traceback_line(
        "│ \x1b[31m/app/example.py:8 in <module>\x1b[0m                     │"
    )

    assert "streamlit   /app/example.py" not in rendered
    assert "/app/example.py:8 in <module>" in rendered
    assert "in <module>                     │" not in rendered
    assert "❱  8 │   raise RuntimeError(" in rendered
    assert len(formatted_line.plain) == display._log_panel_content_width()
    assert formatted_line.plain.endswith(" ")
    assert formatted_line.spans
    assert rendered.index("RuntimeError: boom") < rendered.index("cloudflared")
    assert display._is_streamlit_traceback_marker("streamlit", "\x1b[31m│\x1b[0m /app")
    assert not display._is_streamlit_traceback_marker("streamlit", "❱ prompt")


def test_rich_runtime_display_keeps_traceback_visible_after_tunnel_log_burst() -> None:
    output = StringIO()
    console = Console(file=output, width=80, height=12, force_terminal=True, color_system=None)
    display = RichRuntimeDisplay(console=console)

    display.log("streamlit", "")
    display.log("streamlit", "/app/example.py:8 in <module>                     │")
    display.log("streamlit", "❱  8 │   raise RuntimeError(")
    display.log("streamlit", "─────────────────────────────────────────────────────")
    display.log("streamlit", "RuntimeError: boom")
    for index in range(20):
        display.log("cloudflared", f"precheck status=pass target=region{index}.example")

    console.print(display._render_log_panel(height=8))
    rendered = output.getvalue()

    assert "RuntimeError: boom" in rendered
    assert "streamlit   /app/example.py" not in rendered
    assert "precheck status=pass" in rendered


def test_rich_runtime_display_reports_streamlit_subprocess_width_for_log_panel() -> None:
    console = Console(file=StringIO(), width=40, height=12, force_terminal=True)
    display = RichRuntimeDisplay(console=console)

    assert display.streamlit_subprocess_columns() == 36


def test_switchable_runtime_display_reports_active_streamlit_subprocess_width() -> None:
    console = Console(file=StringIO(), width=40, height=12, force_terminal=True)
    display = SwitchableRuntimeDisplay(
        RichRuntimeDisplay(console=console),
        PlainRuntimeDisplay(output=StringIO(), error_output=StringIO()),
    )

    assert display.streamlit_subprocess_columns() == 36
    display.switch_to_plain()
    assert display.streamlit_subprocess_columns() is None
