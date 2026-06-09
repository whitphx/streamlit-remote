from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Callable, Sequence
from contextlib import suppress
from dataclasses import dataclass

LineHandler = Callable[[str], None]
LinePredicate = Callable[[str], bool]


@dataclass
class ManagedProcess:
    process: subprocess.Popen[str]
    prefix: str
    output_thread: threading.Thread


def start_logged_process(
    command: Sequence[str],
    prefix: str,
    on_line: LineHandler | None = None,
    should_print_line: LinePredicate | None = None,
) -> ManagedProcess:
    process = subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )

    def pump_output() -> None:
        if process.stdout is None:
            return

        for raw_line in process.stdout:
            line = raw_line.rstrip("\r\n")
            if should_print_line is None or should_print_line(line):
                print(f"[{prefix}] {line}", flush=True)
            if on_line is not None:
                on_line(line)

    output_thread = threading.Thread(
        target=pump_output,
        name=f"streamlit-remote-{prefix}",
        daemon=True,
    )
    output_thread.start()
    return ManagedProcess(process=process, prefix=prefix, output_thread=output_thread)


def wait_for_process_exit(
    handles: Sequence[ManagedProcess],
    poll_interval: float = 0.2,
) -> ManagedProcess:
    while True:
        for handle in handles:
            if handle.process.poll() is not None:
                return handle
        time.sleep(poll_interval)


def terminate_processes(
    handles: Sequence[ManagedProcess],
    terminate_timeout: float = 5.0,
    kill_timeout: float = 2.0,
) -> None:
    for handle in handles:
        if handle.process.poll() is None:
            handle.process.terminate()

    deadline = time.monotonic() + terminate_timeout
    for handle in handles:
        remaining = max(0.0, deadline - time.monotonic())
        try:
            handle.process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            if handle.process.poll() is None:
                handle.process.kill()

    for handle in handles:
        with suppress(subprocess.TimeoutExpired):
            handle.process.wait(timeout=kill_timeout)

    for handle in handles:
        handle.output_thread.join(timeout=kill_timeout)
