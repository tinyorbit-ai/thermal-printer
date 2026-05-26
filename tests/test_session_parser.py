"""Session parser — totals, line-type tolerance, partial trailing line."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from thermal_print import session as session_mod
from thermal_print.session import (
    SessionStats,
    encode_cwd,
    find_project_dir,
    find_session_file,
    parse,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures"
SAMPLE = FIXTURE_DIR / "session-sample.jsonl"
PARTIAL = FIXTURE_DIR / "session-partial-trailing.jsonl"
EMPTY = FIXTURE_DIR / "session-empty.jsonl"


# ── totals ─────────────────────────────────────────────────────────────


def test_parse_sums_tokens_across_assistant_turns() -> None:
    stats = parse(SAMPLE)
    # 100 + 200 + 50 across 3 assistant turns
    assert stats.input_tokens == 350
    # 50 + 75 + 25
    assert stats.output_tokens == 150
    # 1000 + 1500 + 500
    assert stats.cached_input_tokens == 3000
    # 200 + 0 + 50
    assert stats.cached_creation_tokens == 250
    assert stats.assistant_turns == 3
    assert stats.model == "claude-opus-4-7"


def test_parse_matches_jq_extraction() -> None:
    """The parser totals must match what a pure-jq pipeline would produce
    on the same file. This is the gate-2 invariant from the plan."""

    def jq_sum(key: str) -> int:
        out = subprocess.run(
            [
                "jq",
                "-s",
                f"[.[] | select(.type==\"assistant\") | .message.usage.{key} // 0] | add",
                str(SAMPLE),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return int(out.stdout.strip())

    stats = parse(SAMPLE)
    assert stats.input_tokens == jq_sum("input_tokens")
    assert stats.output_tokens == jq_sum("output_tokens")
    assert stats.cached_input_tokens == jq_sum("cache_read_input_tokens")
    assert stats.cached_creation_tokens == jq_sum("cache_creation_input_tokens")


# ── line types ─────────────────────────────────────────────────────────


def test_parse_skips_non_assistant_line_types() -> None:
    """Real JSONL contains system / user / file-history-snapshot /
    attachment / last-prompt / ai-title lines — they must not affect
    totals or tool counts."""
    stats = parse(SAMPLE)
    # Fixture has 2 Reads + 1 Bash across assistant turns.
    assert stats.tools == {"Read": 2, "Bash": 1}
    assert sorted(stats.files) == [
        "/Users/USER/code/project/README.md",
        "/Users/USER/code/project/src/main.py",
    ]


def test_parse_handles_empty_session_without_crashing() -> None:
    """A brand-new session has no assistant turns — must return zeros."""
    stats = parse(EMPTY)
    assert stats == SessionStats(
        input_tokens=0,
        output_tokens=0,
        cached_input_tokens=0,
        cached_creation_tokens=0,
        duration_s=5.0,  # timestamps still bound the session
        files=[],
        tools={},
        started_at="2026-05-26T10:00:00.000Z",
        model=None,
        assistant_turns=0,
    )


# ── partial trailing line robustness ───────────────────────────────────


def test_parse_skips_partial_trailing_line() -> None:
    """Claude Code is mid-write; the last line may be truncated JSON."""
    stats = parse(PARTIAL)
    # First (complete) assistant line contributes; the second (truncated) is skipped.
    assert stats.input_tokens == 42
    assert stats.output_tokens == 7
    assert stats.assistant_turns == 1


def test_parse_skips_blank_lines(tmp_path: Path) -> None:
    f = tmp_path / "blanks.jsonl"
    f.write_text(
        "\n"
        + json.dumps(
            {
                "type": "assistant",
                "timestamp": "2026-05-26T10:00:00.000Z",
                "message": {
                    "model": "claude-opus-4-7",
                    "usage": {"input_tokens": 1, "output_tokens": 1},
                },
            }
        )
        + "\n\n"
    )
    stats = parse(f)
    assert stats.input_tokens == 1


# ── duration ───────────────────────────────────────────────────────────


def test_duration_is_last_minus_first_timestamp() -> None:
    stats = parse(SAMPLE)
    # First ts 10:00:00, last 10:00:30 → 30 seconds (last is ai-title at
    # offset, but the last with a timestamp wins).
    assert stats.duration_s >= 30.0


# ── encoded cwd ────────────────────────────────────────────────────────


def test_encode_cwd_basic_path() -> None:
    assert encode_cwd("/Users/USER/code/thermal-printer") == (
        "-Users-USER-code-thermal-printer"
    )


def test_encode_cwd_collapses_dots_to_dashes() -> None:
    """Confirmed from real ~/.claude/projects/ entries: `.dotconfig` → `-dotconfig`
    (the dot and the preceding slash both map to `-`)."""
    assert encode_cwd("/Users/USER/.dotconfig/instances/default") == (
        "-Users-USER--dotconfig-instances-default"
    )


def test_encode_cwd_preserves_uuids() -> None:
    p = "/path/with/4dbf8d1b-37d0-4c08-813d-192990b4ec5a"
    assert encode_cwd(p) == "-path-with-4dbf8d1b-37d0-4c08-813d-192990b4ec5a"


def test_find_project_dir_resolves_real_cwd(tmp_path: Path) -> None:
    fake_base = tmp_path / "projects"
    target = fake_base / "-Users-USER-code-thermal-printer"
    target.mkdir(parents=True)
    found = find_project_dir("/Users/USER/code/thermal-printer", base=fake_base)
    assert found == target


def test_find_project_dir_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        find_project_dir("/nonexistent/path", base=tmp_path)


# ── session file selection ────────────────────────────────────────────


def test_find_session_file_requires_session_id(tmp_path: Path) -> None:
    fake_base = tmp_path / "projects"
    (fake_base / "-cwd").mkdir(parents=True)
    with pytest.raises(ValueError, match="session_id"):
        find_session_file("/cwd", base=fake_base)


def test_find_session_file_by_id(tmp_path: Path) -> None:
    fake_base = tmp_path / "projects"
    project_dir = fake_base / "-cwd"
    project_dir.mkdir(parents=True)
    sid_path = project_dir / "abc-123.jsonl"
    sid_path.write_text("{}\n")
    found = find_session_file("/cwd", session_id="abc-123", base=fake_base)
    assert found == sid_path


def test_find_session_file_latest(tmp_path: Path) -> None:
    fake_base = tmp_path / "projects"
    project_dir = fake_base / "-cwd"
    project_dir.mkdir(parents=True)
    older = project_dir / "older.jsonl"
    newer = project_dir / "newer.jsonl"
    older.write_text("{}\n")
    newer.write_text("{}\n")
    # Make `newer` actually newer.
    import os
    import time

    os.utime(older, (time.time() - 60, time.time() - 60))
    found = find_session_file("/cwd", latest=True, base=fake_base)
    assert found == newer


# ── integration: against the live project's session JSONL ──────────────


def test_can_resolve_this_project_if_present() -> None:
    """If a session JSONL for this repo exists, resolve it and parse without
    crashing. Skipped if the user has no live Claude Code session here."""
    try:
        project_dir = find_project_dir("/Users/USER/code/thermal-printer")
    except FileNotFoundError:
        pytest.skip("no live Claude Code session for this repo")
    jsonl_files = list(project_dir.glob("*.jsonl"))
    if not jsonl_files:
        pytest.skip("project dir has no JSONL files")
    stats = parse(jsonl_files[0])
    assert isinstance(stats, SessionStats)
