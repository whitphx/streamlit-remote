from __future__ import annotations

import subprocess
import threading
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass
from os import environ
from typing import IO

LineHandler = Callable[[str], None]
LinePredicate = Callable[[str], bool]
LogWriter = Callable[[str, str], None]
LineTransformer = Callable[[str], str]


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
    write_log: LogWriter | None = None,
    transform_line: LineTransformer | None = None,
    split_on_carriage_return: bool = False,
    env: Mapping[str, str] | None = None,
) -> ManagedProcess:
    process_env = None
    if env is not None:
        process_env = environ.copy()
        process_env.update(env)

    process = subprocess.Popen(
        list(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=process_env,
    )

    def pump_output() -> None:
        if process.stdout is None:
            return

        lines = (
            _iter_output_lines(process.stdout)
            if split_on_carriage_return
            else _iter_newline_output_lines(process.stdout)
        )
        for line in lines:
            if transform_line is not None:
                line = transform_line(line)
            if should_print_line is None or should_print_line(line):
                if write_log is None:
                    print(f"[{prefix}] {line}", flush=True)
                else:
                    write_log(prefix, line)
            if on_line is not None:
                on_line(line)

    output_thread = threading.Thread(
        target=pump_output,
        name=f"streamlit-remote-{prefix}",
        daemon=True,
    )
    output_thread.start()
    return ManagedProcess(process=process, prefix=prefix, output_thread=output_thread)


def _iter_newline_output_lines(output: IO[str]) -> Iterator[str]:
    for raw_line in output:
        yield raw_line.rstrip("\r\n")


def _iter_output_lines(output: IO[str]) -> Iterator[str]:
    buffer: list[str] = []
    previous_was_carriage_return = False

    while True:
        char = output.read(1)
        if char == "":
            break

        if char == "\n":
            if previous_was_carriage_return:
                previous_was_carriage_return = False
                continue
            yield "".join(buffer)
            buffer.clear()
            continue

        if char == "\r":
            yield "".join(buffer)
            buffer.clear()
            previous_was_carriage_return = True
            continue

        previous_was_carriage_return = False
        buffer.append(char)

    if buffer:
        yield "".join(buffer)


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
