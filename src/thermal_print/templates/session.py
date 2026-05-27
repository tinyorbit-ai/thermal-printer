"""session — print deterministic facts from a Claude Code session JSONL.

Pure data layer. The narrative summary lands in phase 5 via ``llm.py``;
this template just shows tokens, time, files, tools. If the session is
brand-new (no assistant turns yet), the empty-state visual prints
``(session just started)`` instead of a table of zeros.
"""

from __future__ import annotations

from typing import Any

from ..receipt import Receipt
from ..session import (
    SessionStats,
    find_session_file,
    format_duration,
    format_tokens,
    parse,
)

NAME = "session"


def render(ctx: dict[str, Any], r: Receipt) -> None:
    cwd = ctx.get("cwd")
    session_id = ctx.get("session_id")
    latest = bool(ctx.get("latest", False))

    if cwd is None:
        raise ValueError("ctx['cwd'] is required for the session template")

    jsonl_path = find_session_file(cwd, session_id=session_id, latest=latest)
    stats = parse(jsonl_path)

    r.logo("claude")
    r.header("SESSION")
    r.divider("=")

    if stats.assistant_turns == 0:
        r.text("(session just started)")
        r.spacer()
    else:
        r.row("Input", format_tokens(stats.input_tokens))
        r.row("Output", format_tokens(stats.output_tokens))
        r.row("Cached", format_tokens(stats.cached_input_tokens))
        r.row("Time", format_duration(stats.duration_s))
        r.row("Files", str(len(stats.files)))
        r.row("Tools", str(sum(stats.tools.values())))
        if stats.tools:
            r.spacer()
            top = sorted(stats.tools.items(), key=lambda kv: -kv[1])[:5]
            for name, count in top:
                r.row(name, str(count))

    r.divider("-")
    r.footer("thermal-print")
    r.serial()
    r.cut()
