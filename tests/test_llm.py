"""LLM summary — graceful-degrade paths via THERMAL_PRINT_LLM_FAULT."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from thermal_print import llm
from thermal_print.session import SessionStats


@pytest.fixture
def stats() -> SessionStats:
    return SessionStats(
        input_tokens=1000,
        output_tokens=500,
        cached_input_tokens=2000,
        cached_creation_tokens=100,
        duration_s=300.0,
        files=["a.py", "b.py"],
        tools={"Read": 3, "Bash": 2},
        started_at="2026-05-26T10:00:00.000Z",
        model="claude-opus-4-7",
        assistant_turns=5,
    )


# ── graceful-degrade matrix (gate 3) ───────────────────────────────────


def test_summarize_returns_none_when_api_key_unset(
    monkeypatch: pytest.MonkeyPatch, stats: SessionStats
) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert llm.summarize(stats, "excerpt") is None


def test_summarize_returns_none_on_simulated_no_api_key(
    monkeypatch: pytest.MonkeyPatch, stats: SessionStats
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    monkeypatch.setenv(llm._FAULT_ENV, "no-api-key")
    assert llm.summarize(stats, "excerpt") is None


@pytest.mark.parametrize("fault", ["timeout", "401", "429", "500", "malformed"])
def test_summarize_returns_none_on_failure(
    monkeypatch: pytest.MonkeyPatch, stats: SessionStats, fault: str
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    monkeypatch.setenv(llm._FAULT_ENV, fault)
    assert llm.summarize(stats, "excerpt") is None


def test_summarize_never_raises(
    monkeypatch: pytest.MonkeyPatch, stats: SessionStats
) -> None:
    """Belt-and-braces: any unexpected exception must be caught."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")

    def boom(*args, **kwargs):
        raise RuntimeError("totally unexpected")

    monkeypatch.setattr("anthropic.Anthropic", boom)
    assert llm.summarize(stats, "excerpt") is None


# ── transcript excerpt slicing (ADR 0006) ──────────────────────────────


def _write_jsonl(path: Path, records: list[dict]) -> Path:
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    return path


def test_slice_transcript_takes_last_n_user_turns_and_last_assistant(
    tmp_path: Path,
) -> None:
    f = _write_jsonl(
        tmp_path / "s.jsonl",
        [
            {"type": "user", "message": {"role": "user", "content": "u1"}},
            {"type": "user", "message": {"role": "user", "content": "u2"}},
            {"type": "user", "message": {"role": "user", "content": "u3"}},
            {"type": "user", "message": {"role": "user", "content": "u4"}},
            {
                "type": "assistant",
                "message": {
                    "model": "claude-opus-4-7",
                    "usage": {},
                    "content": [{"type": "text", "text": "older assistant"}],
                },
            },
            {
                "type": "assistant",
                "message": {
                    "model": "claude-opus-4-7",
                    "usage": {},
                    "content": [{"type": "text", "text": "latest assistant"}],
                },
            },
        ],
    )
    out = llm.slice_transcript(f, n_user_turns=3)
    # The four user turns → last 3 only.
    assert "u1" not in out
    assert "u2" in out and "u3" in out and "u4" in out
    # Only the latest assistant text survives.
    assert "latest assistant" in out
    assert "older assistant" not in out


def test_slice_transcript_caps_at_max_chars(tmp_path: Path) -> None:
    big = "x" * 50_000
    f = _write_jsonl(
        tmp_path / "s.jsonl",
        [
            {"type": "user", "message": {"role": "user", "content": big}},
            {
                "type": "assistant",
                "message": {
                    "model": "claude-opus-4-7",
                    "content": [{"type": "text", "text": "ok"}],
                },
            },
        ],
    )
    out = llm.slice_transcript(f, max_chars=2000)
    assert len(out) <= 2000


def test_slice_transcript_handles_list_form_user_content(tmp_path: Path) -> None:
    """Real Claude Code JSONL sometimes ships user content as
    [{"type": "text", "text": ...}, ...]."""
    f = _write_jsonl(
        tmp_path / "s.jsonl",
        [
            {
                "type": "user",
                "message": {
                    "role": "user",
                    "content": [{"type": "text", "text": "hello block"}],
                },
            },
        ],
    )
    assert "hello block" in llm.slice_transcript(f)


def test_slice_transcript_tolerates_missing_file(tmp_path: Path) -> None:
    assert llm.slice_transcript(tmp_path / "nope.jsonl") == ""


def test_slice_transcript_skips_malformed_lines(tmp_path: Path) -> None:
    f = tmp_path / "s.jsonl"
    f.write_text(
        '{"type":"user","message":{"role":"user","content":"good"}}\n'
        "{bad json here\n"
        '{"type":"assistant","message":{"content":[{"type":"text","text":"ok"}]}}\n'
    )
    out = llm.slice_transcript(f)
    assert "good" in out and "ok" in out
