from __future__ import annotations

import argparse
import importlib.util
import shlex
import sys
import threading
from pathlib import Path
from typing import Sequence

from streamlit_remote.process import (
    ManagedProcess,
    start_logged_process,
    terminate_processes,
    wait_for_process_exit,
)
from streamlit_remote.providers import get_provider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="st-remote",
        description="Run a Streamlit app with optional remote HTTPS access.",
    )
    parser.add_argument("app", type=Path, metavar="APP", help="Streamlit app file path.")
    parser.add_argument("--port", type=int, default=8501, help="Local Streamlit port.")
    parser.add_argument("--host", default="127.0.0.1", help="Local Streamlit host.")
    parser.add_argument(
        "--provider",
        default="cloudflare",
        choices=["cloudflare"],
        help="Remote tunnel provider.",
    )
    parser.add_argument(
        "--streamlit-arg",
        action="append",
        default=[],
        help="Extra argument passed to Streamlit. Can be repeated.",
    )
    parser.add_argument(
        "--no-remote",
        action="store_true",
        help="Run Streamlit only without starting a remote tunnel.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print subprocess commands without running them.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print additional diagnostic information.",
    )
    return parser


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    cli_args, passthrough_args = split_streamlit_args(argv)
    namespace = build_parser().parse_args(cli_args)
    namespace.streamlit_args = [*namespace.streamlit_arg, *passthrough_args]
    return namespace


def split_streamlit_args(argv: Sequence[str]) -> tuple[list[str], list[str]]:
    args = list(argv)
    if "--" not in args:
        return args, []

    separator_index = args.index("--")
    return args[:separator_index], args[separator_index + 1 :]


def build_streamlit_command(
    app_path: Path,
    host: str,
    port: int,
    streamlit_args: Sequence[str] = (),
) -> list[str]:
    return [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        host,
        "--server.port",
        str(port),
        *streamlit_args,
    ]


def validate_app_path(app_path: Path) -> None:
    if not app_path.exists():
        raise CliError(f"Streamlit app not found: {app_path}")

    if not app_path.is_file():
        raise CliError(f"Streamlit app path is not a file: {app_path}")


def require_streamlit() -> None:
    if importlib.util.find_spec("streamlit") is None:
        raise CliError(
            "Streamlit is not installed. Install it with `pip install streamlit` "
            "or reinstall this package with its dependencies."
        )


def run_cli(argv: Sequence[str] | None = None) -> int:
    try:
        namespace = parse_args(sys.argv[1:] if argv is None else argv)
        return run(namespace)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def run(namespace: argparse.Namespace) -> int:
    validate_app_path(namespace.app)

    local_url = f"http://{namespace.host}:{namespace.port}"
    streamlit_command = build_streamlit_command(
        namespace.app,
        namespace.host,
        namespace.port,
        namespace.streamlit_args,
    )

    provider = None
    tunnel_command: list[str] | None = None
    if not namespace.no_remote:
        provider = get_provider(namespace.provider)
        tunnel_command = provider.build_command(local_url)

    if namespace.dry_run:
        print(f"Streamlit command:\n  {shlex.join(streamlit_command)}")
        if tunnel_command is None:
            print("Remote access: disabled")
        else:
            print(f"Tunnel command:\n  {shlex.join(tunnel_command)}")
        return 0

    require_streamlit()
    if provider is not None and not provider.is_available():
        raise CliError(
            "cloudflared was not found on PATH. Install Cloudflare Tunnel from "
            "https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/ "
            "and try again."
        )

    print("Streamlit local URL:")
    print(f"  {local_url}")
    if namespace.no_remote:
        print("\nRemote access: disabled")
    else:
        print("\nStarting remote tunnel...")

    remote_url_printed = threading.Event()

    def on_cloudflared_line(line: str) -> None:
        if provider is None or remote_url_printed.is_set():
            return

        public_url = provider.parse_public_url(line)
        if public_url is None:
            return

        remote_url_printed.set()
        print("\nStreamlit local URL:")
        print(f"  {local_url}")
        print("\nRemote HTTPS URL:")
        print(f"  {public_url}\n")

    handles: list[ManagedProcess] = []
    try:
        handles.append(start_logged_process(streamlit_command, "streamlit"))
        if tunnel_command is not None:
            handles.append(
                start_logged_process(
                    tunnel_command,
                    "cloudflared",
                    on_line=on_cloudflared_line,
                )
            )

        exited = wait_for_process_exit(handles)
        return exited.process.returncode if exited.process.returncode is not None else 1
    except KeyboardInterrupt:
        print("\nInterrupted. Shutting down child processes...", file=sys.stderr)
        return 130
    finally:
        terminate_processes(handles)


def main() -> None:
    raise SystemExit(run_cli())


class CliError(Exception):
    pass
