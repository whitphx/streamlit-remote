from __future__ import annotations

import os
import shutil
from pathlib import Path


def is_executable_available(command: str | Path) -> bool:
    command_text = str(command)
    if os.path.dirname(command_text):
        return is_executable_file(Path(command_text))

    found = shutil.which(command_text)
    if found is None:
        return False

    return is_executable_file(Path(found))


def is_executable_file(path: Path) -> bool:
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return False

    return resolved.is_file() and os.access(resolved, os.X_OK)
