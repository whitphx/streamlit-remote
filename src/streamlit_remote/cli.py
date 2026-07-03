from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shlex
import sys
import threading
import time
import webbrowser
from collections.abc import Callable, Sequence
from contextlib import suppress
from pathlib import Path
from typing import Any, TextIO

from streamlit_remote.https import (
    HttpsError,
    HttpsMaterial,
    planned_mkcert_material,
    planned_self_signed_material,
    prepare_https_material,
)
from streamlit_remote.process import (
    ManagedProcess,
    start_logged_process,
    terminate_processes,
)
from streamlit_remote.providers import get_provider
from streamlit_remote.providers.ngrok import (
    MANAGED_OAUTH_PROVIDERS,
    PreparedNgrokTrafficPolicy,
    planned_managed_oauth_policy,
    prepare_managed_oauth_policy,
)
from streamlit_remote.runtime_display import STREAMLIT_SOURCE, make_runtime_display
from streamlit_remote.server import LocalServerConfig, is_port_available, wait_until_listening


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="st-remote",
        description="Run a Streamlit app with optional remote HTTPS access.",
    )
    parser.add_argument("app", type=Path, metavar="APP", help="Streamlit app file path.")
    parser.add_argument("--port", type=int, default=8501, help="Local Streamlit port.")
    parser.add_argument("--host", default="localhost", help="Local Streamlit host.")
    parser.add_argument(
        "--provider",
        default="cloudflare",
        choices=["cloudflare", "ngrok", "zrok"],
        help="Remote tunnel provider.",
    )
    parser.add_argument(
        "--tunnel-log-level",
        default="info",
        choices=["info", "warn", "error", "off"],
        help="Tunnel provider log verbosity.",
    )
    parser.add_argument(
        "--cloudflared-binary",
        type=Path,
        help="Path to the cloudflared executable.",
    )
    parser.add_argument(
        "--ngrok-binary",
        type=Path,
        help="Path to the ngrok executable.",
    )
    parser.add_argument(
        "--zrok-binary",
        type=Path,
        help="Path to the zrok executable.",
    )
    parser.add_argument(
        "--https",
        dest="https_mode",
        default="off",
        choices=["off", "self-signed", "mkcert", "cert-files"],
        help="Local Streamlit HTTPS mode.",
    )
    parser.add_argument(
        "--ssl-cert-file",
        type=Path,
        help="Existing certificate file for `--https cert-files`.",
    )
    parser.add_argument(
        "--ssl-key-file",
        type=Path,
        help="Existing private key file for `--https cert-files`.",
    )
    parser.add_argument(
        "--cert-valid-days",
        type=int,
        default=30,
        help="Validity period for managed self-signed certificates.",
    )
    parser.add_argument(
        "--mkcert-binary",
        type=Path,
        help="Path to the mkcert executable.",
    )
    parser.add_argument(
        "--streamlit-arg",
        action="append",
        default=[],
        help="Extra argument passed to Streamlit. Can be repeated.",
    )
    parser.add_argument(
        "--toolbar-mode",
        default="developer",
        choices=["auto", "developer", "viewer", "minimal"],
        help="Streamlit toolbar mode. Defaults to developer.",
    )
    parser.add_argument(
        "--remote-auth",
        default="off",
        choices=["off", "oauth"],
        help="Remote tunnel authentication mode.",
    )
    parser.add_argument(
        "--oauth-provider",
        choices=MANAGED_OAUTH_PROVIDERS,
        help="Managed ngrok OAuth provider for `--remote-auth oauth`. Defaults to google.",
    )
    parser.add_argument(
        "--ngrok-traffic-policy-file",
        type=Path,
        help="Existing ngrok Traffic Policy file to attach to the remote tunnel.",
    )
    parser.add_argument(
        "--no-remote",
        action="store_true",
        help="Run Streamlit only without starting a remote tunnel.",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Do not open the local or remote URL in a browser.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print subprocess commands without running them.",
    )
    parser.add_argument(
        "--no-tui",
        action="store_true",
        help="Use plain log output instead of the interactive terminal display.",
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
    validate_cli_options(namespace)
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
    https_material: HttpsMaterial | None = None,
    toolbar_mode: str = "developer",
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.address",
        host,
        "--server.port",
        str(port),
        "--server.headless",
        "true",
        "--client.toolbarMode",
        toolbar_mode,
    ]

    if https_material is not None:
        command.extend(
            [
                "--server.sslCertFile",
                str(https_material.cert_file),
                "--server.sslKeyFile",
                str(https_material.key_file),
            ]
        )

    command.extend(streamlit_args)
    return command


def validate_app_path(app_path: Path) -> None:
    if not app_path.exists():
        raise CliError(f"Streamlit app not found: {app_path}")

    if not app_path.is_file():
        raise CliError(f"Streamlit app path is not a file: {app_path}")


def validate_cli_options(namespace: argparse.Namespace) -> None:
    cert_files = [namespace.ssl_cert_file, namespace.ssl_key_file]
    if namespace.https_mode != "cert-files" and any(path is not None for path in cert_files):
        raise CliError(
            "`--ssl-cert-file` and `--ssl-key-file` can only be used with `--https cert-files`."
        )

    if namespace.no_remote and namespace.remote_auth != "off":
        raise CliError("`--remote-auth` requires remote access. Remove `--no-remote`.")

    if namespace.remote_auth != "off" and namespace.provider != "ngrok":
        raise CliError("`--remote-auth` is currently supported only with `--provider ngrok`.")

    if namespace.cloudflared_binary is not None:
        if namespace.no_remote:
            raise CliError("`--cloudflared-binary` requires remote access. Remove `--no-remote`.")
        if namespace.provider != "cloudflare":
            raise CliError("`--cloudflared-binary` can only be used with `--provider cloudflare`.")

    if namespace.ngrok_binary is not None:
        if namespace.no_remote:
            raise CliError("`--ngrok-binary` requires remote access. Remove `--no-remote`.")
        if namespace.provider != "ngrok":
            raise CliError("`--ngrok-binary` can only be used with `--provider ngrok`.")

    if namespace.zrok_binary is not None:
        if namespace.no_remote:
            raise CliError("`--zrok-binary` requires remote access. Remove `--no-remote`.")
        if namespace.provider != "zrok":
            raise CliError("`--zrok-binary` can only be used with `--provider zrok`.")

    if namespace.mkcert_binary is not None and namespace.https_mode != "mkcert":
        raise CliError("`--mkcert-binary` can only be used with `--https mkcert`.")

    if namespace.oauth_provider is not None and namespace.remote_auth != "oauth":
        raise CliError("`--oauth-provider` can only be used with `--remote-auth oauth`.")

    if namespace.ngrok_traffic_policy_file is not None:
        if namespace.no_remote:
            raise CliError(
                "`--ngrok-traffic-policy-file` requires remote access. Remove `--no-remote`."
            )
        if namespace.provider != "ngrok":
            raise CliError(
                "`--ngrok-traffic-policy-file` can only be used with `--provider ngrok`."
            )
        if namespace.remote_auth != "off":
            raise CliError("`--ngrok-traffic-policy-file` cannot be combined with `--remote-auth`.")
        if not namespace.ngrok_traffic_policy_file.exists():
            raise CliError(
                f"ngrok Traffic Policy file not found: {namespace.ngrok_traffic_policy_file}"
            )
        if not namespace.ngrok_traffic_policy_file.is_file():
            raise CliError(
                f"ngrok Traffic Policy path is not a file: {namespace.ngrok_traffic_policy_file}"
            )


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
    except (CliError, HttpsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def run(namespace: argparse.Namespace) -> int:
    validate_app_path(namespace.app)

    scheme = "https" if namespace.https_mode != "off" else "http"
    local_server = LocalServerConfig(
        host=namespace.host,
        port=namespace.port,
        scheme=scheme,
    )

    provider = None
    tunnel_command: list[str] | None = None
    traffic_policy: PreparedNgrokTrafficPolicy | None = None
    if not namespace.no_remote:
        tunnel_binary = selected_tunnel_binary(namespace)
        if tunnel_binary is None:
            provider = get_provider(namespace.provider)
        else:
            provider = get_provider(namespace.provider, executable=tunnel_binary)
        traffic_policy = prepare_cli_ngrok_traffic_policy(namespace, dry_run=True)
        tunnel_command = provider.build_command(
            local_server.url,
            origin_tls_verify=namespace.https_mode != "self-signed",
            tunnel_log_level=namespace.tunnel_log_level,
            traffic_policy_file=(
                traffic_policy.traffic_policy_file if traffic_policy is not None else None
            ),
        )

    if namespace.dry_run:
        https_material = prepare_cli_https_material(namespace)
        streamlit_command = build_streamlit_command(
            namespace.app,
            local_server.host,
            local_server.port,
            namespace.streamlit_args,
            https_material=https_material,
            toolbar_mode=namespace.toolbar_mode,
        )
        print(f"Streamlit command:\n  {shlex.join(streamlit_command)}")
        if tunnel_command is None:
            print("Remote access: disabled")
        else:
            print(f"Tunnel command:\n  {shlex.join(tunnel_command)}")
        if namespace.https_mode == "self-signed":
            print("HTTPS: managed self-signed certificate will be prepared at runtime")
        elif namespace.https_mode == "mkcert":
            print("HTTPS: mkcert certificate will be prepared at runtime")
        return 0

    require_streamlit()
    if not is_port_available(local_server.host, local_server.port):
        raise CliError(f"Port {local_server.port} is not available on {local_server.host}.")

    if provider is not None and not provider.is_available():
        raise CliError(provider.install_hint)

    https_material = prepare_cli_https_material(namespace)
    traffic_policy = prepare_cli_ngrok_traffic_policy(namespace, dry_run=False)
    streamlit_command = build_streamlit_command(
        namespace.app,
        local_server.host,
        local_server.port,
        namespace.streamlit_args,
        https_material=https_material,
        toolbar_mode=namespace.toolbar_mode,
    )
    if provider is not None:
        tunnel_command = provider.build_command(
            local_server.url,
            origin_tls_verify=namespace.https_mode != "self-signed",
            tunnel_log_level=namespace.tunnel_log_level,
            traffic_policy_file=(
                traffic_policy.traffic_policy_file if traffic_policy is not None else None
            ),
        )

    display = make_runtime_display(
        use_tui=sys.stdout.isatty() and not namespace.no_tui,
    )
    display.start()
    display.set_local_url(local_server.url)
    display.set_status("Streamlit", "starting")
    if namespace.no_remote:
        display.info("Remote access: disabled")
        if not namespace.no_browser:
            open_browser(local_server.url)
    else:
        if namespace.https_mode == "self-signed" and namespace.provider == "ngrok":
            display.info(
                "Note: ngrok already provides HTTPS for the public URL. "
                "Local self-signed HTTPS will be used only between ngrok and Streamlit."
            )
        assert provider is not None
        display.set_status(provider.log_prefix, "starting")
        display.info("Starting remote tunnel...")

    remote_url_printed = threading.Event()
    remote_url_lock = threading.Lock()

    def report_remote_url(public_url: str) -> None:
        with remote_url_lock:
            if remote_url_printed.is_set():
                return

            remote_url_printed.set()
            display.set_remote_url(public_url)
            if not namespace.no_browser:
                open_browser(public_url)

    def on_tunnel_line(line: str) -> None:
        if provider is None:
            return

        public_url = provider.parse_public_url(line)
        if public_url is not None:
            report_remote_url(public_url)

    def poll_provider_public_url() -> None:
        if provider is None:
            return

        while not remote_url_printed.is_set():
            public_url = provider.get_public_url()
            if public_url is not None:
                report_remote_url(public_url)
                return
            time.sleep(0.5)

    streamlit_handle: ManagedProcess | None = None
    tunnel_handle: ManagedProcess | None = None
    public_url_poll_thread: threading.Thread | None = None
    shortcut_stop_requested = threading.Event()
    restart_requested = threading.Event()
    display_toggle_requested = threading.Event()
    plain_output_requested = threading.Event()
    rich_output_requested = threading.Event()

    def start_streamlit_process() -> ManagedProcess:
        display.set_status("Streamlit", "starting")
        streamlit_env: dict[str, str] = {}
        streamlit_columns = display.streamlit_subprocess_columns()
        if streamlit_columns is not None:
            streamlit_env["COLUMNS"] = str(streamlit_columns)
        return start_logged_process(
            streamlit_command,
            STREAMLIT_SOURCE,
            write_log=display.log,
            env=streamlit_env or None,
        )

    def restart_streamlit_process(current_handle: ManagedProcess) -> ManagedProcess:
        display.set_status("Streamlit", "restarting")
        display.info("Restarting Streamlit...")
        terminate_processes([current_handle])
        next_handle = start_streamlit_process()
        if not wait_until_listening(local_server.host, local_server.port):
            display.set_status("Streamlit", "restart failed")
            display.error(
                f"error: Streamlit did not start listening on {local_server.url} after restart.",
            )
        else:
            display.set_status("Streamlit", "running")
        return next_handle

    try:
        streamlit_handle = start_streamlit_process()
        if tunnel_command is not None and not wait_until_listening(
            local_server.host,
            local_server.port,
        ):
            raise CliError(
                f"Streamlit did not start listening on {local_server.url} within the timeout."
            )
        display.set_status("Streamlit", "running")

        if tunnel_command is not None:
            assert provider is not None
            tunnel_handle = start_logged_process(
                tunnel_command,
                provider.log_prefix,
                on_line=on_tunnel_line,
                should_print_line=lambda line: should_print_tunnel_line(
                    line,
                    namespace.tunnel_log_level,
                ),
                write_log=display.log,
            )
            display.set_status(provider.log_prefix, "running")
            public_url_poll_thread = threading.Thread(
                target=poll_provider_public_url,
                name="streamlit-remote-public-url-poll",
                daemon=True,
            )
            public_url_poll_thread.start()

        shortcut_thread = start_restart_shortcut_listener(
            restart_requested,
            shortcut_stop_requested,
            display_toggle_requested=display_toggle_requested,
            plain_output_requested=plain_output_requested,
            rich_output_requested=rich_output_requested,
            scroll_log_up=display.scroll_log_up,
            scroll_log_down=display.scroll_log_down,
            reset_log_scroll=display.reset_log_scroll,
        )
        if shortcut_thread is not None:
            display.set_shortcuts_visible(True)

        def restart_and_track(current_handle: ManagedProcess) -> ManagedProcess:
            nonlocal streamlit_handle
            streamlit_handle = restart_streamlit_process(current_handle)
            return streamlit_handle

        def report_process_error(handle: ManagedProcess, returncode: int) -> None:
            display.report_process_exit(handle.prefix, returncode)

        return supervise_processes(
            streamlit_handle,
            tunnel_handle,
            restart_requested,
            restart_and_track,
            report_process_error=report_process_error,
            display_toggle_requested=display_toggle_requested,
            toggle_display=display.toggle_display,
            plain_output_requested=plain_output_requested,
            switch_to_plain=display.switch_to_plain,
            rich_output_requested=rich_output_requested,
            switch_to_rich=display.switch_to_rich,
        )
    except KeyboardInterrupt:
        display.error("Interrupted. Shutting down child processes...")
        return 130
    finally:
        shortcut_stop_requested.set()
        remote_url_printed.set()
        handles = [handle for handle in (streamlit_handle, tunnel_handle) if handle is not None]
        terminate_processes(handles)
        if public_url_poll_thread is not None:
            public_url_poll_thread.join(timeout=1.0)
        if traffic_policy is not None:
            traffic_policy.cleanup()
        display.stop()


def main() -> None:
    raise SystemExit(run_cli())


class CliError(Exception):
    pass


def start_restart_shortcut_listener(
    restart_requested: threading.Event,
    stop_requested: threading.Event,
    input_stream: TextIO | None = None,
    display_toggle_requested: threading.Event | None = None,
    plain_output_requested: threading.Event | None = None,
    rich_output_requested: threading.Event | None = None,
    scroll_log_up: Callable[[], bool] | None = None,
    scroll_log_down: Callable[[], bool] | None = None,
    reset_log_scroll: Callable[[], bool] | None = None,
) -> threading.Thread | None:
    stdin = sys.stdin if input_stream is None else input_stream
    if not stdin.isatty():
        return None

    def listen() -> None:
        if listen_for_cbreak_shortcuts(
            stdin,
            restart_requested,
            stop_requested,
            display_toggle_requested=display_toggle_requested,
            plain_output_requested=plain_output_requested,
            rich_output_requested=rich_output_requested,
            scroll_log_up=scroll_log_up,
            scroll_log_down=scroll_log_down,
            reset_log_scroll=reset_log_scroll,
        ):
            return

        listen_for_line_shortcuts(
            stdin,
            restart_requested,
            stop_requested,
            display_toggle_requested=display_toggle_requested,
            plain_output_requested=plain_output_requested,
            rich_output_requested=rich_output_requested,
            scroll_log_up=scroll_log_up,
            scroll_log_down=scroll_log_down,
            reset_log_scroll=reset_log_scroll,
        )

    thread = threading.Thread(
        target=listen,
        name="streamlit-remote-shortcuts",
        daemon=True,
    )
    thread.start()
    return thread


def listen_for_cbreak_shortcuts(
    stdin: TextIO,
    restart_requested: threading.Event,
    stop_requested: threading.Event,
    *,
    display_toggle_requested: threading.Event | None = None,
    plain_output_requested: threading.Event | None = None,
    rich_output_requested: threading.Event | None = None,
    scroll_log_up: Callable[[], bool] | None = None,
    scroll_log_down: Callable[[], bool] | None = None,
    reset_log_scroll: Callable[[], bool] | None = None,
) -> bool:
    try:
        import select
        import termios
        import tty

        fd = stdin.fileno()
        previous_terminal_settings = termios.tcgetattr(fd)
    except (ImportError, AttributeError, OSError):
        return False

    try:
        try:
            tty.setcbreak(fd)
        except OSError:
            termios.tcsetattr(fd, termios.TCSANOW, previous_terminal_settings)
            return False

        while not stop_requested.is_set():
            try:
                readable, _, _ = select.select([fd], [], [], 0.1)
            except OSError:
                return True
            if not readable:
                continue

            shortcut = read_cbreak_shortcut(stdin, fd=fd)
            if shortcut == "":
                return True
            dispatch_shortcut(
                shortcut,
                restart_requested,
                display_toggle_requested=display_toggle_requested,
                plain_output_requested=plain_output_requested,
                rich_output_requested=rich_output_requested,
                scroll_log_up=scroll_log_up,
                scroll_log_down=scroll_log_down,
                reset_log_scroll=reset_log_scroll,
            )
    finally:
        termios.tcsetattr(fd, termios.TCSANOW, previous_terminal_settings)

    return True


def listen_for_line_shortcuts(
    stdin: TextIO,
    restart_requested: threading.Event,
    stop_requested: threading.Event,
    *,
    display_toggle_requested: threading.Event | None = None,
    plain_output_requested: threading.Event | None = None,
    rich_output_requested: threading.Event | None = None,
    scroll_log_up: Callable[[], bool] | None = None,
    scroll_log_down: Callable[[], bool] | None = None,
    reset_log_scroll: Callable[[], bool] | None = None,
) -> None:
    while not stop_requested.is_set():
        try:
            line = stdin.readline()
        except OSError:
            return
        if line == "":
            return
        dispatch_shortcut(
            line,
            restart_requested,
            display_toggle_requested=display_toggle_requested,
            plain_output_requested=plain_output_requested,
            rich_output_requested=rich_output_requested,
            scroll_log_up=scroll_log_up,
            scroll_log_down=scroll_log_down,
            reset_log_scroll=reset_log_scroll,
        )


def dispatch_shortcut(
    shortcut: str,
    restart_requested: threading.Event,
    *,
    display_toggle_requested: threading.Event | None = None,
    plain_output_requested: threading.Event | None = None,
    rich_output_requested: threading.Event | None = None,
    scroll_log_up: Callable[[], bool] | None = None,
    scroll_log_down: Callable[[], bool] | None = None,
    reset_log_scroll: Callable[[], bool] | None = None,
) -> None:
    normalized = shortcut.strip().lower()
    if normalized in {"r", "restart"}:
        restart_requested.set()
    elif display_toggle_requested is not None and normalized in {"t", "toggle"}:
        display_toggle_requested.set()
    elif plain_output_requested is not None and normalized in {"p", "plain", "logs"}:
        plain_output_requested.set()
    elif rich_output_requested is not None and normalized in {"f", "fancy", "tui"}:
        rich_output_requested.set()
    elif scroll_log_up is not None and normalized in {
        "\x10",
        "\x1b[a",
        "\x1boa",
        "k",
        "up",
        "scroll up",
    }:
        scroll_log_up()
    elif scroll_log_down is not None and normalized in {
        "\x0e",
        "\x1b[b",
        "\x1bob",
        "j",
        "down",
        "scroll down",
    }:
        scroll_log_down()
    elif reset_log_scroll is not None and normalized in {"\x1b", "esc", "latest"}:
        reset_log_scroll()


def read_cbreak_shortcut(stdin: TextIO, *, fd: int | None = None) -> str:
    first_byte = read_cbreak_byte(stdin, fd=fd)
    if first_byte == b"":
        return ""

    if first_byte != b"\x1b":
        return first_byte.decode("utf-8", errors="replace")

    select_module: Any | None
    try:
        import select
    except ImportError:
        select_module = None
    else:
        select_module = select

    sequence = [first_byte]
    introducer = read_cbreak_byte(stdin, fd=fd, timeout=0.5, select_module=select_module)
    if introducer == b"":
        return "\x1b"
    sequence.append(introducer)

    if introducer == b"O":
        final = read_cbreak_byte(stdin, fd=fd, timeout=0.5, select_module=select_module)
        if final in {b"A", b"B"}:
            sequence.append(final)
            return b"".join(sequence).decode("ascii")
        return ""

    if introducer != b"[":
        return ""

    while len(sequence) < 6:
        next_byte = read_cbreak_byte(stdin, fd=fd, timeout=0.5, select_module=select_module)
        if next_byte == b"":
            return ""
        sequence.append(next_byte)
        if 0x40 <= next_byte[0] <= 0x7E:
            return b"".join(sequence).decode("ascii", errors="ignore")

    return ""


def read_cbreak_byte(
    stdin: TextIO,
    *,
    fd: int | None,
    timeout: float | None = None,
    select_module: Any | None = None,
) -> bytes:
    if fd is not None:
        if timeout is not None and select_module is not None:
            try:
                readable, _, _ = select_module.select([fd], [], [], timeout)
            except (AttributeError, OSError):
                return b""
            if not readable:
                return b""
        try:
            return os.read(fd, 1)
        except OSError:
            return b""

    try:
        char = stdin.read(1)
    except OSError:
        return b""
    return char.encode()


def supervise_processes(
    streamlit_handle: ManagedProcess,
    tunnel_handle: ManagedProcess | None,
    restart_requested: threading.Event,
    restart_streamlit: Callable[[ManagedProcess], ManagedProcess],
    poll_interval: float = 0.2,
    report_process_error: Callable[[ManagedProcess, int], None] | None = None,
    display_toggle_requested: threading.Event | None = None,
    toggle_display: Callable[[], bool] | None = None,
    plain_output_requested: threading.Event | None = None,
    switch_to_plain: Callable[[], bool] | None = None,
    rich_output_requested: threading.Event | None = None,
    switch_to_rich: Callable[[], bool] | None = None,
) -> int:
    current_streamlit_handle = streamlit_handle
    while True:
        if restart_requested.is_set():
            restart_requested.clear()
            current_streamlit_handle = restart_streamlit(current_streamlit_handle)
            continue

        if display_toggle_requested is not None and display_toggle_requested.is_set():
            display_toggle_requested.clear()
            if toggle_display is not None:
                toggle_display()
            continue

        if plain_output_requested is not None and plain_output_requested.is_set():
            plain_output_requested.clear()
            if switch_to_plain is not None:
                switch_to_plain()
            continue

        if rich_output_requested is not None and rich_output_requested.is_set():
            rich_output_requested.clear()
            if switch_to_rich is not None:
                switch_to_rich()
            continue

        if tunnel_handle is not None and tunnel_handle.process.poll() is not None:
            return report_process_returncode(tunnel_handle, report_process_error)

        if current_streamlit_handle.process.poll() is not None:
            return report_process_returncode(current_streamlit_handle, report_process_error)

        time.sleep(poll_interval)


def report_process_returncode(
    handle: ManagedProcess,
    report_process_error: Callable[[ManagedProcess, int], None] | None,
) -> int:
    returncode = handle.process.returncode if handle.process.returncode is not None else 1
    if returncode != 0 and report_process_error is not None:
        handle.output_thread.join(timeout=1.0)
        report_process_error(handle, returncode)
    return returncode


def prepare_cli_https_material(namespace: argparse.Namespace) -> HttpsMaterial | None:
    if namespace.dry_run and namespace.https_mode == "self-signed":
        return planned_self_signed_material(namespace.host)

    if namespace.dry_run and namespace.https_mode == "mkcert":
        return planned_mkcert_material(namespace.host)

    return prepare_https_material(
        mode=namespace.https_mode,
        host=namespace.host,
        cert_file=namespace.ssl_cert_file,
        key_file=namespace.ssl_key_file,
        valid_days=namespace.cert_valid_days,
        mkcert_binary=namespace.mkcert_binary or "mkcert",
    )


def selected_tunnel_binary(namespace: argparse.Namespace) -> Path | None:
    if namespace.provider == "cloudflare":
        return namespace.cloudflared_binary

    if namespace.provider == "ngrok":
        return namespace.ngrok_binary

    if namespace.provider == "zrok":
        return namespace.zrok_binary

    return None


def prepare_cli_ngrok_traffic_policy(
    namespace: argparse.Namespace,
    *,
    dry_run: bool,
) -> PreparedNgrokTrafficPolicy | None:
    if namespace.no_remote or namespace.provider != "ngrok":
        return None

    if namespace.ngrok_traffic_policy_file is not None:
        return PreparedNgrokTrafficPolicy(namespace.ngrok_traffic_policy_file)

    if namespace.remote_auth == "oauth":
        oauth_provider = namespace.oauth_provider or "google"
        if dry_run:
            return planned_managed_oauth_policy(oauth_provider)
        return prepare_managed_oauth_policy(oauth_provider)

    return None


def should_print_tunnel_line(line: str, tunnel_log_level: str) -> bool:
    if tunnel_log_level == "off":
        return False

    if tunnel_log_level == "info":
        return True

    severity = classify_tunnel_line(line)
    if tunnel_log_level == "warn":
        return severity in {"warn", "error"}

    if tunnel_log_level == "error":
        return severity == "error"

    return True


def classify_tunnel_line(line: str) -> str:
    try:
        payload = json.loads(line)
    except json.JSONDecodeError:
        payload = None

    if isinstance(payload, dict):
        level = payload.get("level")
        if isinstance(level, str):
            normalized_level = level.lower()
            if normalized_level in {"error", "fatal", "panic"}:
                return "error"
            if normalized_level in {"warn", "warning"}:
                return "warn"

    lowered = line.lower()
    if any(marker in lowered for marker in ("lvl=error", "lvl=crit", " err ", " error", "fatal")):
        return "error"

    if any(marker in lowered for marker in ("lvl=warn", " wrn ", " warn", "warning")):
        return "warn"

    return "info"


def open_browser(url: str) -> None:
    with suppress(Exception):
        webbrowser.open(url, new=2)
