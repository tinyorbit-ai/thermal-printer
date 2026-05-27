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
    lines_added: int = 0
    lines_removed: int = 0


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

            # Edit/Write tool results land on `user`-type lines as
            # `toolUseResult` with a `structuredPatch` field. Each hunk's
            # `lines` array has `+`/`-`/` `-prefixed entries — the same
            # convention as unified diff. Skip everything else.
            if d.get("type") == "user":
                _tally_patch_lines(d, stats)
                continue

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


def _tally_patch_lines(d: dict, stats: SessionStats) -> None:
    """Count ``+``/``-`` lines from a tool-result structuredPatch.

    Edit/Write tool results land on ``user``-type lines as
    ``toolUseResult`` with a ``structuredPatch`` (a list of hunks). Each
    hunk's ``lines`` array uses unified-diff prefixes: ``+`` added,
    ``-`` removed, `` `` context.
    """
    tur = d.get("toolUseResult")
    if not isinstance(tur, dict):
        return
    patch = tur.get("structuredPatch")
    if not isinstance(patch, list):
        return
    for hunk in patch:
        if not isinstance(hunk, dict):
            continue
        lines = hunk.get("lines")
        if not isinstance(lines, list):
            continue
        for line in lines:
            if not isinstance(line, str) or not line:
                continue
            if line[0] == "+":
                stats.lines_added += 1
            elif line[0] == "-":
                stats.lines_removed += 1


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
    """Compact token count: ``4221`` → ``4,221``; ``15977610`` → ``15.9M``.

    Big numbers don't fit a 32-char grid in expanded form, so anything
    over 1M collapses to ``N.NM``; anything over 10K collapses to ``NN.NK``.
    """
    n = int(n)
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 10_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:,}"


# Approximate pricing in USD per million tokens. The receipt is a
# celebration, not an invoice — for the *exact* number, the slash
# command can pass ``--cost-override`` from Claude Code's runtime. These
# rates were calibrated against a real Opus 4.7 session whose
# Claude-Code-reported cost was $49.25 and our pricing reproduces
# within ~5% of that. If Anthropic re-tiers, update this table.
PRICING_USD_PER_MILLION: dict[str, dict[str, float]] = {
    "opus":   {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_creation": 3.75},
    "sonnet": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_creation": 3.75},
    "haiku":  {"input": 1.00, "output":  5.00, "cache_read": 0.10, "cache_creation": 1.25},
}


def model_family(model: str | None) -> str:
    """Map a full model id to its pricing family. Falls back to ``opus``
    (the most expensive — better to over-quote than mislead)."""
    if not model:
        return "opus"
    m = model.lower()
    if "haiku" in m:
        return "haiku"
    if "sonnet" in m:
        return "sonnet"
    return "opus"


def compute_cost_usd(stats: "SessionStats") -> float:
    """Approximate session cost in USD from the model + token totals."""
    family = model_family(stats.model)
    p = PRICING_USD_PER_MILLION[family]
    return (
        stats.input_tokens          * p["input"]          / 1_000_000
        + stats.output_tokens         * p["output"]         / 1_000_000
        + stats.cached_input_tokens   * p["cache_read"]     / 1_000_000
        + stats.cached_creation_tokens * p["cache_creation"] / 1_000_000
    )


def format_cost(usd: float) -> str:
    """Currency-formatted dollars: ``2.34`` → ``$2.34``; ``24.2`` → ``$24.20``."""
    if usd < 0.01:
        return "<$0.01"
    return f"${usd:,.2f}"


def short_model_name(model: str | None) -> str:
    """Strip the ``claude-`` prefix and trailing date for receipt brevity."""
    if not model:
        return "—"
    name = model.removeprefix("claude-")
    # Drop trailing date stamps like "-20251001".
    parts = name.rsplit("-", 1)
    if len(parts) == 2 and parts[1].isdigit() and len(parts[1]) >= 6:
        name = parts[0]
    return name


__all__ = [
    "PRICING_USD_PER_MILLION",
    "SessionStats",
    "compute_cost_usd",
    "encode_cwd",
    "find_project_dir",
    "find_session_file",
    "format_cost",
    "format_duration",
    "format_tokens",
    "model_family",
    "parse",
    "short_model_name",
]
