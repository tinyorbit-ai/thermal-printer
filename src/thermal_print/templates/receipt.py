"""receipt — the full /receipt template.

Crab logo + project name + serial + deterministic stats from
:mod:`thermal_print.session` + a 3-5 line narrative from Anthropic Haiku.

The summary is a bonus; if :func:`llm.summarize` returns ``None`` (no API
key, timeout, 4xx/5xx, malformed response, or any other failure) the
summary block reads ``(summary unavailable)`` and the stats are
unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import llm
from .. import session as session_mod
from ..receipt import Receipt

NAME = "receipt"


def render(ctx: dict[str, Any], r: Receipt) -> None:
    cwd = ctx.get("cwd")
    session_id = ctx.get("session_id")
    latest = bool(ctx.get("latest", False))

    if cwd is None:
        raise ValueError("ctx['cwd'] is required for the receipt template")

    jsonl_path = session_mod.find_session_file(cwd, session_id=session_id, latest=latest)
    stats = session_mod.parse(jsonl_path)

    project_name = Path(cwd).name or "session"
    excerpt = llm.slice_transcript(jsonl_path)
    summary = llm.summarize(stats, excerpt)

    r.logo("crab")
    r.header(project_name.upper()[:Receipt.GRID_WIDTH])
    r.divider("=")

    if stats.assistant_turns == 0:
        # Defer to the empty-state visual — a brand-new session prints
        # an intentional placeholder, not a table of zeros.
        r.text("(session just started)")
        r.spacer()
    else:
        r.row("Input", session_mod.format_tokens(stats.input_tokens))
        r.row("Output", session_mod.format_tokens(stats.output_tokens))
        r.row("Cached", session_mod.format_tokens(stats.cached_input_tokens))
        r.row("Time", session_mod.format_duration(stats.duration_s))
        r.row("Files", str(len(stats.files)))
        r.row("Tools", str(sum(stats.tools.values())))
        r.divider("-")
        if summary:
            r.text(summary)
        else:
            r.text("(summary unavailable)")
        r.spacer()

    r.footer("thermal-print")
    r.serial()
    r.cut()
