"""Parse Claude Code session JSONL into deterministic facts.

The JSONL file is being appended to while ``/receipt`` reads it, so the
parser is **resilient** by design: malformed lines (including a partial
trailing line) are skipped without crashing.

The ``usage`` object lives on ``.message.usage`` on lines where
``type == "assistant"`` — never at the top level. Non-assistant line
types observed in real sessions (and exercised by the test fixture)
include ``user``, ``system``, ``file-history-snapshot``, ``attachment``,
``last-prompt``, and ``ai-title``. See ADR 0005.

Encoded-cwd resolution: Claude Code stores sessions under
``~/.claude/projects/<encoded-cwd>/<session-id>.jsonl``. The encoder is
not pure ``/``→``-`` — any non-``[a-zA-Z0-9-]`` character maps to ``-``.
Examples in the wild: ``/Users/USER/.dotconfig/...`` →
``-Users-USER--dotconfig-...`` (the ``.`` collapses with the ``/``).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

CLAUDE_PROJECTS_DIR = Path.home() / ".claude" / "projects"

# Tool input keys that name a file the assistant touched. Conservative —
# extend only when a new tool actually starts shipping file paths in
# input fields we care about.
_FILE_KEYS = ("file_path", "path", "notebook_path")


@dataclass
class SessionStats:
    """Deterministic facts extracted from one Claude Code session JSONL."""

    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    cached_creation_tokens: int = 0
    duration_s: float = 0.0
    files: list[str] = field(default_factory=list)
    tools: dict[str, int] = field(default_factory=dict)
    started_at: str | None = None
    model: str | None = None
    assistant_turns: int = 0


def encode_cwd(cwd: str) -> str:
    """Map a cwd path to Claude Code's encoded directory name.

    Claude Code replaces any character outside ``[a-zA-Z0-9-]`` with ``-``,
    which means ``/Users/USER/.dotconfig/...`` and ``/Users/USER_dotconfig/...``
    can collide. This is a known lossy edge case; see ADR 0005.
    """
    return re.sub(r"[^a-zA-Z0-9-]", "-", cwd)


def find_project_dir(cwd: str, base: Path | None = None) -> Path:
    """Resolve the encoded Claude Code project dir for ``cwd``.

    Listing-based (per the hardened plan) — encodes ``cwd`` and looks for
    the matching directory under :data:`CLAUDE_PROJECTS_DIR`.
    """
    base = base if base is not None else CLAUDE_PROJECTS_DIR
    encoded = encode_cwd(cwd)
    candidate = base / encoded
    if candidate.is_dir():
        return candidate
    raise FileNotFoundError(
        f"no Claude Code project dir for cwd={cwd!r} "
        f"(expected {candidate})"
    )


def find_session_file(
    cwd: str,
    *,
    session_id: str | None = None,
    latest: bool = False,
    base: Path | None = None,
) -> Path:
    """Resolve the JSONL file for a session.

    ``session_id`` is **required by default**. ``latest=True`` is an
    interactive escape hatch — ``/receipt`` always passes ``session_id``
    explicitly so the receipt's stats are tied to a known session.
    """
    project_dir = find_project_dir(cwd, base=base)

    if latest:
        candidates = sorted(
            project_dir.glob("*.jsonl"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if not candidates:
            raise FileNotFoundError(f"no JSONL files in {project_dir}")
        return candidates[0]

    if session_id is None:
        raise ValueError("session_id is required (or pass latest=True)")

    f = project_dir / f"{session_id}.jsonl"
    if not f.is_file():
        raise FileNotFoundError(f"no session file: {f}")
    return f


def parse(jsonl_path: Path) -> SessionStats:
    """Parse a JSONL file into :class:`SessionStats`.

    Tolerant — any line that fails ``json.loads`` is skipped (handles the
    partial trailing line case where Claude Code is mid-write).
    """
    stats = SessionStats()
    files: set[str] = set()
    first_ts: str | None = None
    last_ts: str | None = None

    with jsonl_path.open(encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                # Partial trailing write or otherwise malformed — skip.
                continue
            if not isinstance(d, dict):
                continue

            ts = d.get("timestamp")
            if isinstance(ts, str):
                if first_ts is None:
                    first_ts = ts
                last_ts = ts

            if d.get("type") != "assistant":
                continue

            stats.assistant_turns += 1

            msg = d.get("message") if isinstance(d.get("message"), dict) else {}
            usage = msg.get("usage") if isinstance(msg.get("usage"), dict) else {}
            stats.input_tokens += int(usage.get("input_tokens", 0) or 0)
            stats.output_tokens += int(usage.get("output_tokens", 0) or 0)
            stats.cached_input_tokens += int(usage.get("cache_read_input_tokens", 0) or 0)
            stats.cached_creation_tokens += int(usage.get("cache_creation_input_tokens", 0) or 0)

            model = msg.get("model")
            if isinstance(model, str):
                stats.model = model

            content = msg.get("content")
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    if block.get("type") != "tool_use":
                        continue
                    name = block.get("name") or "unknown"
                    stats.tools[name] = stats.tools.get(name, 0) + 1
                    inp = block.get("input")
                    if isinstance(inp, dict):
                        for k in _FILE_KEYS:
                            v = inp.get(k)
                            if isinstance(v, str):
                                files.add(v)

    stats.files = sorted(files)
    stats.started_at = first_ts

    if first_ts and last_ts:
        try:
            start = datetime.fromisoformat(first_ts.replace("Z", "+00:00"))
            end = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
            stats.duration_s = max(0.0, (end - start).total_seconds())
        except ValueError:
            pass

    return stats


def format_duration(seconds: float) -> str:
    """Human-friendly duration for the receipt: ``s`` / ``m`` / ``h…m``."""
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s // 60}m"
    h, m = divmod(s // 60, 60)
    return f"{h}h{m}m"


def format_tokens(n: int) -> str:
    """Comma-formatted token count: ``4221`` → ``4,221``."""
    return f"{int(n):,}"


__all__ = [
    "SessionStats",
    "encode_cwd",
    "find_project_dir",
    "find_session_file",
    "format_duration",
    "format_tokens",
    "parse",
]
