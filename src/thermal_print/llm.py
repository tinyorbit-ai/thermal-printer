"""Anthropic Haiku summary for ``/receipt``.

The summary is a **bonus** — the stats are the receipt's contract. Any
failure (no API key, request timeout, 4xx/5xx, malformed response)
returns ``None``; the receipt template falls back to
``(summary unavailable)``.

Test instrument: set ``THERMAL_PRINT_LLM_FAULT`` to one of
``no-api-key``, ``timeout``, ``401``, ``429``, ``500``, ``malformed``
to exercise each graceful-degrade path without an actual network call.
See ADR 0006 for the model pin, deadline, slicing rule, and trust-line
note.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# Pinned model id per ADR 0006 — *not* the marketing label "Haiku 4.5".
MODEL = "claude-haiku-4-5-20251001"

# Hard request deadline; passed to the SDK and also used as a wall-clock
# cap. Keeps `/receipt` from blocking paper-out indefinitely.
REQUEST_DEADLINE_S = 10.0

# Transcript-excerpt slicing rule per ADR 0006:
# "last N user turns + last assistant turn, capped at K chars."
N_LAST_USER_TURNS = 3
MAX_EXCERPT_CHARS = 8000

MAX_OUTPUT_TOKENS = 300

_FAULT_ENV = "THERMAL_PRINT_LLM_FAULT"


_PROMPT_TEMPLATE = """You are writing a 3-5 line summary for a thermal-printed receipt of a coding session.

Session stats:
- input tokens: {input_tokens}
- output tokens: {output_tokens}
- cached tokens: {cached_input_tokens}
- duration: {duration}
- files touched: {n_files}
- tool calls: {n_tools}
- top tools: {top_tools}

Last messages of the session:
{transcript_excerpt}

Write 3 to 5 short lines (each at most 32 characters) summarizing what the developer accomplished in this session. Tone: warm, observational, concrete. No buzzwords. No "session completed successfully" boilerplate. Output ONLY the lines, one per line, no leading dashes or numbering."""


def summarize(stats, transcript_excerpt: str) -> str | None:
    """Return a 3-5 line summary or ``None``. Never raises.

    ``stats`` is a :class:`~thermal_print.session.SessionStats`.
    """
    fault = os.environ.get(_FAULT_ENV)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if fault == "no-api-key":
        api_key = None

    try:
        if not api_key:
            return None

        if fault == "timeout":
            raise TimeoutError("simulated timeout")
        if fault == "401":
            raise PermissionError("simulated 401")
        if fault == "429":
            raise RuntimeError("simulated 429")
        if fault == "500":
            raise ConnectionError("simulated 500")
        if fault == "malformed":
            # Empty / non-text response — treated identically to a real
            # malformed body.
            return None

        from anthropic import Anthropic

        from .session import format_duration, format_tokens

        client = Anthropic(api_key=api_key, timeout=REQUEST_DEADLINE_S)
        top_tools = ", ".join(
            f"{name}:{count}"
            for name, count in sorted(stats.tools.items(), key=lambda kv: -kv[1])[:5]
        ) or "(none)"

        prompt = _PROMPT_TEMPLATE.format(
            input_tokens=format_tokens(stats.input_tokens),
            output_tokens=format_tokens(stats.output_tokens),
            cached_input_tokens=format_tokens(stats.cached_input_tokens),
            duration=format_duration(stats.duration_s),
            n_files=len(stats.files),
            n_tools=sum(stats.tools.values()),
            top_tools=top_tools,
            transcript_excerpt=transcript_excerpt or "(no transcript)",
        )

        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_OUTPUT_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )

        # Defensive against schema drift / malformed response bodies.
        content = getattr(response, "content", None)
        if not content or not isinstance(content, list):
            return None
        first = content[0]
        text = getattr(first, "text", None)
        if not isinstance(text, str) or not text.strip():
            return None
        return text.strip()
    except Exception:
        # Stats are sacred; summary is a bonus. Never raise.
        return None


def slice_transcript(
    jsonl_path: Path,
    *,
    n_user_turns: int = N_LAST_USER_TURNS,
    max_chars: int = MAX_EXCERPT_CHARS,
) -> str:
    """Build the LLM excerpt: last N user turns + last assistant turn.

    Tail-bias the cap — keep the most recent characters when the
    accumulated text exceeds ``max_chars``.
    """
    user_turns: list[str] = []
    last_assistant: str | None = None

    try:
        with jsonl_path.open(encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                except json.JSONDecodeError:
                    continue

                t = d.get("type")
                if t == "user":
                    text = _extract_text(d.get("message", {}))
                    if text:
                        user_turns.append(text)
                elif t == "assistant":
                    text = _extract_text(d.get("message", {}))
                    if text:
                        last_assistant = text
    except OSError:
        return ""

    parts: list[str] = []
    for u in user_turns[-n_user_turns:]:
        parts.append(f"USER: {u}")
    if last_assistant:
        parts.append(f"ASSISTANT: {last_assistant}")

    text = "\n\n".join(parts)
    if len(text) > max_chars:
        text = text[-max_chars:]
    return text


def _extract_text(message: dict) -> str:
    """Pull the text content out of either ``content: str`` or
    ``content: [{type: text, text: ...}, ...]``."""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return " ".join(parts).strip()
    return ""
