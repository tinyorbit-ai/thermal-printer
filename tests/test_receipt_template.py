"""receipt template — end-to-end render against a fixture JSONL."""

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
    return cwd, session_id, projects


@pytest.fixture(autouse=True)
def patch_projects_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Each test gets its own fake ~/.claude/projects/ root."""
    from thermal_print import session as session_mod

    monkeypatch.setattr(session_mod, "CLAUDE_PROJECTS_DIR", tmp_path / "projects")


def test_receipt_template_renders_with_summary_unavailable_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no API key, the summary is None and the receipt prints
    `(summary unavailable)` — stats are unchanged."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    fixture = Path(__file__).parent / "fixtures" / "session-sample.jsonl"
    cwd, sid, _ = _stage_fixture(tmp_path, fixture)

    r = Receipt()
    receipt_template.render({"cwd": cwd, "session_id": sid}, r)

    joined = "\n".join(r._lines)
    assert "(summary unavailable)" in joined
    # Stats lines for the real session-sample fixture (3 assistant turns,
    # 100+200+50 input).
    assert "350" in joined  # input tokens
    assert "150" in joined  # output tokens
    assert r._cuts == 1


def test_receipt_template_uses_empty_state_for_brand_new_session(
    tmp_path: Path,
) -> None:
    fixture = Path(__file__).parent / "fixtures" / "session-empty.jsonl"
    cwd, sid, _ = _stage_fixture(tmp_path, fixture)

    r = Receipt()
    receipt_template.render({"cwd": cwd, "session_id": sid}, r)

    joined = "\n".join(r._lines)
    assert "(session just started)" in joined
    assert "(summary unavailable)" not in joined  # empty state preempts the LLM block
    assert r._cuts == 1


def test_receipt_template_falls_back_on_llm_fault(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each simulated LLM failure mode keeps the stats intact and prints
    `(summary unavailable)` — the gate-3 invariant."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-fake")
    fixture = Path(__file__).parent / "fixtures" / "session-sample.jsonl"
    cwd, sid, _ = _stage_fixture(tmp_path, fixture)

    from thermal_print import llm

    for fault in ["timeout", "401", "429", "500", "malformed"]:
        monkeypatch.setenv(llm._FAULT_ENV, fault)
        r = Receipt()
        receipt_template.render({"cwd": cwd, "session_id": sid}, r)
        joined = "\n".join(r._lines)
        assert "(summary unavailable)" in joined, f"fault {fault} did not degrade"
        assert "350" in joined, f"fault {fault} clobbered stats"
        assert r._cuts == 1


def test_receipt_template_requires_cwd() -> None:
    r = Receipt()
    with pytest.raises(ValueError, match="cwd"):
        receipt_template.render({}, r)
