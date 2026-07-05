from __future__ import annotations

import re
import sys
import threading
from collections import deque
from typing import Protocol, TextIO

from rich.console import Console, RenderableType
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
STREAMLIT_SOURCE = "streamlit"


class RuntimeDisplay(Protocol):
    def start(self) -> None: ...

    def stop(self) -> None: ...

    def switch_to_plain(self) -> bool: ...

    def switch_to_rich(self) -> bool: ...

    def toggle_display(self) -> bool: ...

    def report_process_exit(self, source: str, returncode: int) -> None: ...

    def set_local_url(self, url: str) -> None: ...

    def set_remote_url(self, url: str) -> None: ...

    def set_status(self, component: str, status: str) -> None: ...

    def set_shortcuts_visible(self, visible: bool) -> None: ...

    def scroll_log_up(self) -> bool: ...

    def scroll_log_down(self) -> bool: ...

    def reset_log_scroll(self) -> bool: ...

    def streamlit_subprocess_columns(self) -> int | None: ...

    def info(self, message: str) -> None: ...

    def error(self, message: str) -> None: ...

    def log(self, source: str, line: str) -> None: ...


class PlainRuntimeDisplay(RuntimeDisplay):
    def __init__(self, output: TextIO = sys.stdout, error_output: TextIO = sys.stderr) -> None:
        self._output = output
        self._error_output = error_output

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass

    def switch_to_plain(self) -> bool:
        return False

    def switch_to_rich(self) -> bool:
        return False

    def toggle_display(self) -> bool:
        return False

    def report_process_exit(self, source: str, returncode: int) -> None:
        self.error(f"error: {source} exited with code {returncode}.")

    def set_local_url(self, url: str) -> None:
        self.info("Streamlit local URL:")
        self.info(f"  {url}")

    def set_remote_url(self, url: str) -> None:
        self.info("Remote HTTPS URL:")
        self.info(f"  {url}")

    def set_status(self, component: str, status: str) -> None:
        pass

    def set_shortcuts_visible(self, visible: bool) -> None:
        if visible:
            self.info("Runtime shortcuts:")
            self.info("  r: restart Streamlit while keeping the tunnel running")

    def scroll_log_up(self) -> bool:
        return False

    def scroll_log_down(self) -> bool:
        return False

    def reset_log_scroll(self) -> bool:
        return False

    def streamlit_subprocess_columns(self) -> int | None:
        return None

    def info(self, message: str) -> None:
        print(message, file=self._output, flush=True)

    def error(self, message: str) -> None:
        print(message, file=self._error_output, flush=True)

    def log(self, source: str, line: str) -> None:
        print(f"[{source}] {line}", file=self._output, flush=True)


class RichRuntimeDisplay(RuntimeDisplay):
    _MIN_LOG_PANEL_HEIGHT = 3
    _SHORTCUTS_PANEL_HEIGHT = 3
    _PANEL_FRAME_ROWS = 2
    _PANEL_HORIZONTAL_OVERHEAD = 4
    _LOG_SOURCE_WIDTH = 11
    _LOG_SOURCE_SEPARATOR_WIDTH = 1
    _RICH_TRACEBACK_CHARS = frozenset("╭╮╰╯│─")

    def __init__(
        self,
        console: Console | None = None,
        max_log_lines: int = 120,
    ) -> None:
        self._console = console or Console()
        self._logs: deque[tuple[str, str]] = deque(maxlen=max_log_lines)
        self._statuses: dict[str, str] = {}
        self._local_url: str | None = None
        self._remote_url: str | None = None
        self._shortcuts_visible = False
        self._log_window_start: int | None = None
        self._log_ids: deque[int] = deque(maxlen=max_log_lines)
        self._next_log_id = 0
        self._live: Live | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        with self._lock:
            if self._live is not None:
                return
            self._live = Live(
                self._render(),
                console=self._console,
                refresh_per_second=8,
                screen=True,
                transient=False,
                vertical_overflow="crop",
            )
            self._live.start()

    def stop(self) -> None:
        with self._lock:
            if self._live is None:
                return
            self._live.stop()
            self._live = None

    def switch_to_plain(self) -> bool:
        return False

    def switch_to_rich(self) -> bool:
        return False

    def toggle_display(self) -> bool:
        return False

    def report_process_exit(self, source: str, returncode: int) -> None:
        pass

    def set_local_url(self, url: str) -> None:
        with self._lock:
            self._local_url = url
            self._refresh()

    def set_remote_url(self, url: str) -> None:
        with self._lock:
            self._remote_url = url
            self._refresh()

    def set_status(self, component: str, status: str) -> None:
        with self._lock:
            self._statuses[component] = status
            self._refresh()

    def set_shortcuts_visible(self, visible: bool) -> None:
        with self._lock:
            self._shortcuts_visible = visible
            self._refresh()

    def scroll_log_up(self) -> bool:
        with self._lock:
            return self._scroll_log(1)

    def scroll_log_down(self) -> bool:
        with self._lock:
            return self._scroll_log(-1)

    def reset_log_scroll(self) -> bool:
        with self._lock:
            if self._log_window_start is None:
                return False
            self._log_window_start = None
            self._refresh()
            return True

    def streamlit_subprocess_columns(self) -> int | None:
        # Streamlit formats Rich tracebacks before we can render them without a
        # source prefix, so give it the prefix-less log panel width.
        return self._log_panel_content_width()

    def info(self, message: str) -> None:
        self.log("st-remote", message)

    def error(self, message: str) -> None:
        self.log("error", message)

    def log(self, source: str, line: str) -> None:
        with self._lock:
            anchor = self._log_window_anchor()
            self._logs.append((source, line))
            self._log_ids.append(self._next_log_id)
            self._next_log_id += 1
            if anchor is not None:
                self._log_window_start = self._find_log_window_anchor(anchor) or 0
            self._refresh()

    def set_state(
        self,
        *,
        local_url: str | None,
        remote_url: str | None,
        statuses: dict[str, str],
        shortcuts_visible: bool,
        logs: list[tuple[str, str]],
    ) -> None:
        with self._lock:
            self._local_url = local_url
            self._remote_url = remote_url
            self._statuses = statuses.copy()
            self._shortcuts_visible = shortcuts_visible
            self._logs.clear()
            self._logs.extend(logs)
            self._log_ids.clear()
            self._log_ids.extend(range(len(logs)))
            self._next_log_id = len(logs)
            self._log_window_start = None
            self._refresh()

    def _refresh(self) -> None:
        if self._live is not None:
            self._live.update(self._render())

    def _render(self) -> RenderableType:
        status_height, log_height, shortcuts_height = self._layout_heights()
        layout = Layout()
        layout.split_column(
            Layout(
                self._render_status_panel(height=status_height),
                size=status_height,
            ),
            Layout(
                self._render_log_panel(height=log_height),
                size=log_height,
            ),
            Layout(
                self._render_shortcuts_panel(height=shortcuts_height),
                size=shortcuts_height,
            ),
        )
        return layout

    def _layout_heights(self) -> tuple[int, int, int]:
        terminal_height = max(
            self._MIN_LOG_PANEL_HEIGHT + self._SHORTCUTS_PANEL_HEIGHT + 3,
            self._console.size.height,
        )
        max_status_height = (
            terminal_height - self._SHORTCUTS_PANEL_HEIGHT - self._MIN_LOG_PANEL_HEIGHT
        )
        status_height = min(max(4, len(self._statuses) + 4), max_status_height)
        log_height = terminal_height - status_height - self._SHORTCUTS_PANEL_HEIGHT
        return status_height, log_height, self._SHORTCUTS_PANEL_HEIGHT

    def _render_status_panel(self, *, height: int | None = None) -> Panel:
        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold")
        table.add_column()
        table.add_row("Local", self._local_url or "pending")
        table.add_row("Remote", self._remote_url or "pending")
        for component, status in self._statuses.items():
            table.add_row(component, status)
        return Panel(table, title="streamlit-remote", border_style="cyan", height=height)

    def _render_log_panel(self, *, height: int | None = None) -> Panel:
        panel_height = height or self._layout_heights()[1]
        if not self._logs:
            return Panel(
                Text("Waiting for logs...", style="dim"),
                title="Logs",
                height=panel_height,
            )

        lines = Text()
        visible_logs = self._visible_logs(panel_height=panel_height)
        raw_traceback_indexes = self._raw_streamlit_traceback_indexes(visible_logs)
        for index, (source, line) in enumerate(visible_logs):
            if index in raw_traceback_indexes:
                lines.append(self._format_raw_streamlit_traceback_line(line))
            else:
                lines.append(f"{source:>11} ", style=self._source_style(source))
                lines.append(self._format_log_line(line, width=self._log_line_width()))
            if index < len(visible_logs) - 1:
                lines.append("\n")
        return Panel(lines, title="Logs", height=panel_height)

    def _visible_logs(self, *, panel_height: int | None = None) -> list[tuple[str, str]]:
        log_panel_height = panel_height or self._layout_heights()[1]
        available_rows = max(1, log_panel_height - self._PANEL_FRAME_ROWS)
        logs = self._move_interleaved_logs_after_tracebacks(list(self._logs))
        return self._select_visible_logs(logs, available_rows=available_rows)

    def _select_visible_logs(
        self,
        logs: list[tuple[str, str]],
        *,
        available_rows: int,
    ) -> list[tuple[str, str]]:
        if len(logs) <= available_rows:
            return logs

        if self._log_window_start is not None:
            start = self._clamped_log_window_start(
                self._log_window_start,
                log_count=len(logs),
                available_rows=available_rows,
            )
            return logs[start : start + available_rows]

        traceback_spans = self._streamlit_traceback_spans(logs)
        traceback_span = traceback_spans[-1] if traceback_spans else None
        if traceback_span is None:
            return logs[-available_rows:]

        start, end = traceback_span
        if any(source == STREAMLIT_SOURCE for source, _ in logs[end:]):
            return logs[-available_rows:]

        traceback_logs = logs[start:end]
        if len(traceback_logs) >= available_rows:
            return traceback_logs[-available_rows:]

        following_rows = available_rows - len(traceback_logs)
        following_logs = logs[end:][-following_rows:] if following_rows else []
        selected_logs = [*traceback_logs, *following_logs]

        preceding_rows = available_rows - len(selected_logs)
        if preceding_rows:
            selected_logs = [*logs[:start][-preceding_rows:], *selected_logs]
        return selected_logs

    def _move_interleaved_logs_after_tracebacks(
        self,
        logs: list[tuple[str, str]],
    ) -> list[tuple[str, str]]:
        entries = [(index, log) for index, log in enumerate(logs)]
        return [log for _, log in self._move_interleaved_log_entries_after_tracebacks(entries)]

    def _scroll_log(self, rows: int) -> bool:
        logs = self._move_interleaved_logs_after_tracebacks(list(self._logs))
        available_rows = max(1, self._layout_heights()[1] - self._PANEL_FRAME_ROWS)
        if len(logs) <= available_rows:
            return False

        old_start = self._current_log_window_start(logs, available_rows=available_rows)
        new_start = self._clamped_log_window_start(
            old_start - rows,
            log_count=len(logs),
            available_rows=available_rows,
        )
        if new_start == old_start:
            return False
        self._log_window_start = new_start
        self._refresh()
        return True

    def _current_log_window_start(
        self,
        logs: list[tuple[str, str]],
        *,
        available_rows: int,
    ) -> int:
        if self._log_window_start is not None:
            return self._clamped_log_window_start(
                self._log_window_start,
                log_count=len(logs),
                available_rows=available_rows,
            )

        return self._default_log_window_start(logs, available_rows=available_rows)

    def _default_log_window_start(
        self,
        logs: list[tuple[str, str]],
        *,
        available_rows: int,
    ) -> int:
        if len(logs) <= available_rows:
            return 0

        traceback_spans = self._streamlit_traceback_spans(logs)
        traceback_span = traceback_spans[-1] if traceback_spans else None
        if traceback_span is None:
            return len(logs) - available_rows

        start, end = traceback_span
        if any(source == STREAMLIT_SOURCE for source, _ in logs[end:]):
            return len(logs) - available_rows

        traceback_rows = end - start
        if traceback_rows >= available_rows:
            return end - available_rows

        following_rows = available_rows - traceback_rows
        following_count = min(following_rows, len(logs) - end)
        preceding_rows = available_rows - traceback_rows - following_count
        if preceding_rows:
            return max(0, start - preceding_rows)
        return start

    def _clamped_log_window_start(
        self,
        start: int,
        *,
        log_count: int,
        available_rows: int,
    ) -> int:
        max_start = max(0, log_count - available_rows)
        return min(max(0, start), max_start)

    def _log_window_anchor(self) -> int | None:
        if self._log_window_start is None:
            return None

        entries = self._arranged_log_entries()
        if not entries:
            return None
        start = self._clamped_log_window_start(
            self._log_window_start,
            log_count=len(entries),
            available_rows=max(1, self._layout_heights()[1] - self._PANEL_FRAME_ROWS),
        )
        return entries[start][0]

    def _find_log_window_anchor(self, anchor: int) -> int | None:
        for index, (log_id, _) in enumerate(self._arranged_log_entries()):
            if log_id == anchor:
                return index
        return None

    def _arranged_log_entries(self) -> list[tuple[int, tuple[str, str]]]:
        return self._move_interleaved_log_entries_after_tracebacks(
            list(zip(self._log_ids, self._logs, strict=True))
        )

    def _move_interleaved_log_entries_after_tracebacks(
        self,
        entries: list[tuple[int, tuple[str, str]]],
    ) -> list[tuple[int, tuple[str, str]]]:
        arranged_entries: list[tuple[int, tuple[str, str]]] = []
        deferred_entries: list[tuple[int, tuple[str, str]]] = []
        in_streamlit_traceback = False

        for log_id, (source, line) in entries:
            if self._is_streamlit_traceback_marker(source, line):
                in_streamlit_traceback = True
                arranged_entries.append((log_id, (source, line)))
            elif in_streamlit_traceback and source != STREAMLIT_SOURCE:
                deferred_entries.append((log_id, (source, line)))
            else:
                arranged_entries.append((log_id, (source, line)))

        arranged_entries.extend(deferred_entries)
        return arranged_entries

    def _raw_streamlit_traceback_indexes(self, logs: list[tuple[str, str]]) -> set[int]:
        raw_indexes: set[int] = set()
        for start, end in self._streamlit_traceback_spans(logs):
            raw_indexes.update(range(start, end))
        return raw_indexes

    def _streamlit_traceback_spans(self, logs: list[tuple[str, str]]) -> list[tuple[int, int]]:
        marker_indexes = [
            index
            for index, (source, line) in enumerate(logs)
            if self._is_streamlit_traceback_marker(source, line)
        ]
        spans: list[tuple[int, int]] = []
        for marker_index in marker_indexes:
            start = marker_index
            while start > 0 and logs[start - 1][0] == STREAMLIT_SOURCE:
                start -= 1

            end = marker_index + 1
            while end < len(logs) and logs[end][0] == STREAMLIT_SOURCE:
                end += 1

            if spans and start <= spans[-1][1]:
                spans[-1] = (spans[-1][0], max(spans[-1][1], end))
            else:
                spans.append((start, end))
        return spans

    def _is_streamlit_traceback_marker(self, source: str, line: str) -> bool:
        if source != STREAMLIT_SOURCE:
            return False
        return any(char in _ANSI_ESCAPE_RE.sub("", line) for char in self._RICH_TRACEBACK_CHARS)

    def _format_raw_streamlit_traceback_line(self, line: str) -> Text:
        text = Text.from_ansi(line)
        plain = text.plain
        start = 0
        end = len(plain)

        leading_border_match = re.match(r"^\s*│ ?", plain)
        if leading_border_match is not None:
            start = leading_border_match.end()

        trailing_border_match = re.search(r"\s+│\s*$", plain)
        if trailing_border_match is not None and trailing_border_match.start() >= start:
            end = trailing_border_match.start()

        end = min(end, len(plain[:end].rstrip()))
        formatted_text = text[start:end]
        return self._format_raw_streamlit_traceback_text(formatted_text)

    def _format_raw_streamlit_traceback_text(self, text: Text) -> Text:
        width = self._log_panel_content_width()
        formatted_text = text.copy()
        if len(formatted_text.plain) > width:
            if width <= 3:
                formatted_text = Text("." * width)
            else:
                formatted_text = formatted_text[: width - 3]
                formatted_text.append("...")
        formatted_text.pad_right(width - len(formatted_text.plain))
        return formatted_text

    def _format_log_line(self, line: str, *, width: int) -> str:
        line = line.replace("\n", r"\n").replace("\r", r"\r")
        if len(line) <= width:
            return line
        if width <= 3:
            return "." * width
        return f"{line[: width - 3]}..."

    def _log_line_width(self) -> int:
        return max(
            1,
            self._log_panel_content_width()
            - self._LOG_SOURCE_WIDTH
            - self._LOG_SOURCE_SEPARATOR_WIDTH,
        )

    def _log_panel_content_width(self) -> int:
        return max(1, self._console.size.width - self._PANEL_HORIZONTAL_OVERHEAD)

    def _render_shortcuts_panel(self, *, height: int | None = None) -> Panel:
        if not self._shortcuts_visible:
            return Panel(
                Text("Ctrl+C stop all", style="bold"),
                title="Shortcuts",
                height=height,
            )

        shortcuts = Text()
        shortcuts.append("r", style="bold green")
        shortcuts.append(" restart  ")
        shortcuts.append("t", style="bold cyan")
        shortcuts.append(" display  ")
        shortcuts.append("j/k", style="bold yellow")
        shortcuts.append(" ↑/↓ C-n/p", style="yellow")
        shortcuts.append(" scroll  ")
        shortcuts.append("Esc", style="bold yellow")
        shortcuts.append(" latest  ")
        shortcuts.append("Ctrl+C", style="bold red")
        shortcuts.append(" stop")
        return Panel(shortcuts, title="Shortcuts", border_style="green", height=height)

    def _source_style(self, source: str) -> str:
        if source == STREAMLIT_SOURCE:
            return "blue"
        if source in {"cloudflared", "ngrok"}:
            return "magenta"
        if source == "error":
            return "red"
        return "cyan"


class SwitchableRuntimeDisplay(RuntimeDisplay):
    def __init__(
        self,
        rich_display: RichRuntimeDisplay,
        plain_display: PlainRuntimeDisplay,
        max_replayed_logs: int = 120,
    ) -> None:
        self._rich_display = rich_display
        self._plain_display = plain_display
        self._active_display: RuntimeDisplay = rich_display
        self._logs: deque[tuple[str, str]] = deque(maxlen=max_replayed_logs)
        self._statuses: dict[str, str] = {}
        self._local_url: str | None = None
        self._remote_url: str | None = None
        self._shortcuts_visible = False
        self._started = False
        self._lock = threading.RLock()

    def start(self) -> None:
        with self._lock:
            if self._started:
                return
            self._started = True
            self._active_display.start()

    def stop(self) -> None:
        with self._lock:
            if not self._started:
                return
            self._active_display.stop()
            self._started = False

    def switch_to_plain(self) -> bool:
        with self._lock:
            if self._active_display is self._plain_display:
                return False

            was_started = self._started
            if was_started:
                self._rich_display.stop()
            self._active_display = self._plain_display
            if was_started:
                self._plain_display.start()

            if self._local_url is not None:
                self._plain_display.set_local_url(self._local_url)
            if self._remote_url is not None:
                self._plain_display.set_remote_url(self._remote_url)
            if self._shortcuts_visible:
                self._plain_display.set_shortcuts_visible(True)

            self._plain_display.info("Switched to plain log output. Recent logs:")
            self._plain_display.info("  t: return to terminal display")
            for source, line in self._logs:
                self._plain_display.log(source, line)
            return True

    def switch_to_rich(self) -> bool:
        with self._lock:
            if self._active_display is self._rich_display:
                return False

            self._rich_display.set_state(
                local_url=self._local_url,
                remote_url=self._remote_url,
                statuses=self._statuses,
                shortcuts_visible=self._shortcuts_visible,
                logs=list(self._logs),
            )

            was_started = self._started
            if was_started:
                self._plain_display.stop()
            self._active_display = self._rich_display
            if was_started:
                self._rich_display.start()
            return True

    def toggle_display(self) -> bool:
        with self._lock:
            if self._active_display is self._rich_display:
                return self.switch_to_plain()
            return self.switch_to_rich()

    def report_process_exit(self, source: str, returncode: int) -> None:
        with self._lock:
            if self._active_display is self._plain_display:
                self._plain_display.report_process_exit(source, returncode)
                return

            was_started = self._started
            if was_started:
                self._rich_display.stop()
            self._active_display = self._plain_display
            if was_started:
                self._plain_display.start()

            self._plain_display.report_process_exit(source, returncode)
            self._plain_display.info("Recent logs:")
            for log_source, line in self._logs:
                self._plain_display.log(log_source, line)

    def set_local_url(self, url: str) -> None:
        with self._lock:
            self._local_url = url
            self._active_display.set_local_url(url)

    def set_remote_url(self, url: str) -> None:
        with self._lock:
            self._remote_url = url
            self._active_display.set_remote_url(url)

    def set_status(self, component: str, status: str) -> None:
        with self._lock:
            self._statuses[component] = status
            self._active_display.set_status(component, status)

    def set_shortcuts_visible(self, visible: bool) -> None:
        with self._lock:
            self._shortcuts_visible = visible
            self._active_display.set_shortcuts_visible(visible)

    def scroll_log_up(self) -> bool:
        with self._lock:
            return self._active_display.scroll_log_up()

    def scroll_log_down(self) -> bool:
        with self._lock:
            return self._active_display.scroll_log_down()

    def reset_log_scroll(self) -> bool:
        with self._lock:
            return self._active_display.reset_log_scroll()

    def streamlit_subprocess_columns(self) -> int | None:
        with self._lock:
            return self._active_display.streamlit_subprocess_columns()

    def info(self, message: str) -> None:
        with self._lock:
            self._logs.append(("st-remote", message))
            self._active_display.info(message)

    def error(self, message: str) -> None:
        with self._lock:
            self._logs.append(("error", message))
            self._active_display.error(message)

    def log(self, source: str, line: str) -> None:
        with self._lock:
            self._logs.append((source, line))
            self._active_display.log(source, line)


def make_runtime_display(
    *,
    use_tui: bool,
    output: TextIO = sys.stdout,
    error_output: TextIO = sys.stderr,
) -> RuntimeDisplay:
    if use_tui:
        return SwitchableRuntimeDisplay(
            RichRuntimeDisplay(Console(file=output)),
            PlainRuntimeDisplay(output=output, error_output=error_output),
        )
    return PlainRuntimeDisplay(output=output, error_output=error_output)
