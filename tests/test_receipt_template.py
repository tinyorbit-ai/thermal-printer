"""receipt template — end-to-end render against a fixture JSONL.

The narrative summary is provided by the caller via ``ctx["summary"]``
(passed through the CLI's ``--summary`` flag). Absence collapses to
``(summary unavailable)``; see ADR 0006.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from thermal_print.receipt import Receipt
from thermal_print.templates import receipt as receipt_template


def _stage_fixture(tmp_path: Path, jsonl_src: Path) -> tuple[str, str]:
    """Stage a fixture JSONL under a fake ~/.claude/projects/ tree and
    return ``(cwd, session_id)`` that the receipt template will resolve."""
    projects = tmp_path / "projects"
    cwd = "/tmp/fake-project"
    project_dir = projects / "-tmp-fake-project"
    project_dir.mkdir(parents=True)
    session_id = "test-session"
    (project_dir / f"{session_id}.jsonl").write_bytes(jsonl_src.read_bytes())
    return cwd, session_id


@pytest.fixture(autouse=True)
def patch_projects_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Each test gets its own fake ~/.claude/projects/ root."""
    from thermal_print import session as session_mod

    monkeypatch.setattr(session_mod, "CLAUDE_PROJECTS_DIR", tmp_path / "projects")


def test_receipt_template_renders_with_summary_unavailable_when_no_arg(
    tmp_path: Path,
) -> None:
    """No --summary passed → `(summary unavailable)` in the receipt; stats unchanged."""
    fixture = Path(__file__).parent / "fixtures" / "session-sample.jsonl"
    cwd, sid = _stage_fixture(tmp_path, fixture)

    r = Receipt()
    receipt_template.render({"cwd": cwd, "session_id": sid}, r)

    joined = "\n".join(r._lines)
    assert "(summary unavailable)" in joined
    assert "350" in joined  # input tokens from fixture
    assert "150" in joined  # output tokens
    assert r._cuts == 1


def test_receipt_template_uses_empty_state_for_brand_new_session(
    tmp_path: Path,
) -> None:
    fixture = Path(__file__).parent / "fixtures" / "session-empty.jsonl"
    cwd, sid = _stage_fixture(tmp_path, fixture)

    r = Receipt()
    receipt_template.render({"cwd": cwd, "session_id": sid}, r)

    joined = "\n".join(r._lines)
    assert "(session just started)" in joined
    # Empty state preempts the summary block.
    assert "(summary unavailable)" not in joined
    assert r._cuts == 1


def test_receipt_template_prints_provided_summary(tmp_path: Path) -> None:
    """A --summary arg lands in the receipt verbatim (subject to text wrapping)."""
    fixture = Path(__file__).parent / "fixtures" / "session-sample.jsonl"
    cwd, sid = _stage_fixture(tmp_path, fixture)

    summary = "wrestled the printer.\nshipped the rewrite.\nphase 5 sings."
    r = Receipt()
    receipt_template.render(
        {"cwd": cwd, "session_id": sid, "summary": summary}, r
    )

    joined = "\n".join(r._lines)
    # Each newline-separated summary line should appear on its own row.
    assert "wrestled the printer." in joined
    assert "shipped the rewrite." in joined
    assert "phase 5 sings." in joined
    # The fallback should not be used when a real summary is given.
    assert "(summary unavailable)" not in joined
    assert r._cuts == 1


def test_receipt_template_treats_empty_summary_as_missing(tmp_path: Path) -> None:
    """An empty / whitespace-only --summary degrades to the fallback."""
    fixture = Path(__file__).parent / "fixtures" / "session-sample.jsonl"
    cwd, sid = _stage_fixture(tmp_path, fixture)

    r = Receipt()
    receipt_template.render(
        {"cwd": cwd, "session_id": sid, "summary": "   \n  "}, r
    )

    joined = "\n".join(r._lines)
    assert "(summary unavailable)" in joined


def test_receipt_template_requires_cwd() -> None:
    r = Receipt()
    with pytest.raises(ValueError, match="cwd"):
        receipt_template.render({}, r)
