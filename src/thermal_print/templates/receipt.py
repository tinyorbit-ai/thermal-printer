"""receipt — the full /receipt template.

Claude logo + project name + serial + deterministic stats from
:mod:`thermal_print.session` (model, wall time, turn count, token
breakdown, cost, top tools, files touched) + a 3-5 line narrative
provided by the caller via ``--summary``.

The narrative is **not** generated here. The Claude Code slash command
at ``.claude/commands/receipt.md`` writes it in the parent agent's
context (where the full transcript already lives) and passes it via
argv. If no ``--summary`` is given the block reads
``(summary unavailable)`` and the stats are unchanged. See ADR 0006.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import session as session_mod
from ..receipt import Receipt

NAME = "receipt"

# How many top tools to surface as a breakdown. Each takes one row, so
# this trades vertical paper against detail. 4 fits comfortably on most
# sessions without dominating the receipt.
TOP_TOOLS = 4


def render(ctx: dict[str, Any], r: Receipt) -> None:
    cwd = ctx.get("cwd")
    session_id = ctx.get("session_id")
    latest = bool(ctx.get("latest", False))
    summary = ctx.get("summary")
    cost_override = ctx.get("cost_override")
    lines_added_override = ctx.get("lines_added_override")
    lines_removed_override = ctx.get("lines_removed_override")

    if cwd is None:
        raise ValueError("ctx['cwd'] is required for the receipt template")

    jsonl_path = session_mod.find_session_file(cwd, session_id=session_id, latest=latest)
    stats = session_mod.parse(jsonl_path)

    project_name = Path(cwd).name or "session"
    cost = cost_override if cost_override is not None else session_mod.compute_cost_usd(stats)
    lines_added = lines_added_override if lines_added_override is not None else stats.lines_added
    lines_removed = lines_removed_override if lines_removed_override is not None else stats.lines_removed
    model_short = session_mod.short_model_name(stats.model)

    r.logo("claude")
    r.header(project_name.upper()[: Receipt.GRID_WIDTH])
    r.divider("=")

    if stats.assistant_turns == 0:
        r.text("(session just started)")
        r.spacer()
    else:
        # Session shape — what model, how long, how many round-trips.
        r.row("Model", model_short)
        r.row("Wall time", session_mod.format_duration(stats.duration_s))
        r.row("Turns", str(stats.assistant_turns))
        r.divider("-")

        # Token economy — what went in, what came out, what was cached.
        r.row("Tokens in", session_mod.format_tokens(stats.input_tokens))
        r.row("Tokens out", session_mod.format_tokens(stats.output_tokens))
        r.row("Cache hit", session_mod.format_tokens(stats.cached_input_tokens))
        r.row("Cost", session_mod.format_cost(cost))
        r.divider("-")

        # What you actually did — tools used, files touched, lines changed.
        if stats.tools:
            r.row("Tools", str(sum(stats.tools.values())))
            for name, count in sorted(stats.tools.items(), key=lambda kv: -kv[1])[:TOP_TOOLS]:
                r.row(f"  {name}", str(count))
        r.row("Files", str(len(stats.files)))
        if lines_added or lines_removed:
            r.row("Lines added", f"+{lines_added:,}")
            r.row("Lines removed", f"-{lines_removed:,}")
        r.divider("-")

        # Narrative — written by the parent Claude Code agent and passed
        # in via --summary. Fallback if absent.
        if isinstance(summary, str) and summary.strip():
            r.text(summary.strip())
        else:
            r.text("(summary unavailable)")
        r.spacer()

    r.footer("thermal-print")
    r.serial()
    r.cut()
