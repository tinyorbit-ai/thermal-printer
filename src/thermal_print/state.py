"""Persistent state for thermal-printer.

Default location: ``~/.thermal-printer/state.json``. Tests must override
with the ``THERMAL_PRINT_STATE`` env var to keep the suite hermetic
(see ADR 0004 Consequences for why this lives on the filesystem at all).

Atomic write via temp file + :func:`os.replace`, so a crash mid-write
never leaves a half-written ``state.json``. Read tolerates missing /
corrupt files by returning an empty dict — a write right after will
recreate it clean.

The read-modify-write inside :func:`bump_serial` is **not** locked.
On a single-host single-user personal tool, two concurrent receipts
landing in the same millisecond is acceptable; the wiki captures this
in ADR 0004 (deferred per the hardening review).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

DEFAULT_DIR = Path.home() / ".thermal-printer"
DEFAULT_PATH = DEFAULT_DIR / "state.json"


def state_path() -> Path:
    """Resolve the active state file, honoring the env override."""
    override = os.environ.get("THERMAL_PRINT_STATE")
    return Path(override) if override else DEFAULT_PATH


def read() -> dict[str, Any]:
    """Return the parsed state, or ``{}`` if the file is missing/corrupt."""
    p = state_path()
    try:
        return json.loads(p.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def write(data: dict[str, Any]) -> None:
    """Atomically persist ``data`` to the state file. Lazily creates the
    parent directory."""
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True))
    os.replace(tmp, p)


def bump_serial() -> int:
    """Read the current serial, increment, persist, and return the new value."""
    data = read()
    n = int(data.get("serial", 0)) + 1
    data["serial"] = n
    write(data)
    return n
