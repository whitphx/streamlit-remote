from __future__ import annotations

import re

TERMINAL_SEQUENCE_RE = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalize_terminal_line(line: str) -> str:
    line = TERMINAL_SEQUENCE_RE.sub("", line)
    return CONTROL_CHAR_RE.sub("", line).strip()
