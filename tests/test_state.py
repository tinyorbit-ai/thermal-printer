"""Persistent state — env override, increment, atomic write, lazy mkdir."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from thermal_print import state


# ── hermetic guard ─────────────────────────────────────────────────────


def test_hermetic_env_var_is_set() -> None:
    """If this fails, the autouse hermetic_state fixture is not active and
    other tests could write to ~/.thermal-printer/."""
    assert os.environ.get("THERMAL_PRINT_STATE"), (
        "THERMAL_PRINT_STATE must be set during test runs — see tests/conftest.py"
    )


def test_state_path_honors_env_override(hermetic_state: Path) -> None:
    assert state.state_path() == hermetic_state


def test_state_path_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("THERMAL_PRINT_STATE", raising=False)
    assert state.state_path() == state.DEFAULT_PATH


# ── bump_serial ────────────────────────────────────────────────────────


def test_bump_starts_at_one_on_fresh_file() -> None:
    assert state.bump_serial() == 1


def test_bump_increments_monotonically() -> None:
    assert state.bump_serial() == 1
    assert state.bump_serial() == 2
    assert state.bump_serial() == 3


def test_bump_persists_across_processes(hermetic_state: Path) -> None:
    state.bump_serial()
    state.bump_serial()
    on_disk = json.loads(hermetic_state.read_text())
    assert on_disk["serial"] == 2


# ── atomic write ───────────────────────────────────────────────────────


def test_write_uses_atomic_rename(
    hermetic_state: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Failing mid-write must not leave a half-written state.json."""
    calls: list[tuple[str, str]] = []

    real_replace = os.replace

    def spy_replace(src: str | os.PathLike, dst: str | os.PathLike) -> None:
        calls.append((str(src), str(dst)))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy_replace)
    state.bump_serial()

    assert len(calls) == 1
    src, dst = calls[0]
    assert src.endswith(".tmp")
    assert dst == str(hermetic_state)


# ── lazy directory creation ────────────────────────────────────────────


def test_lazy_parent_directory_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    nested = tmp_path / "deep" / "deeper" / "state.json"
    monkeypatch.setenv("THERMAL_PRINT_STATE", str(nested))
    state.bump_serial()
    assert nested.parent.is_dir()
    assert nested.exists()


# ── tolerant read ──────────────────────────────────────────────────────


def test_read_returns_empty_dict_when_file_missing() -> None:
    assert state.read() == {}


def test_read_returns_empty_dict_on_corrupt_json(hermetic_state: Path) -> None:
    hermetic_state.parent.mkdir(parents=True, exist_ok=True)
    hermetic_state.write_text("not json at all")
    assert state.read() == {}


def test_bump_recovers_from_corrupt_file(hermetic_state: Path) -> None:
    hermetic_state.parent.mkdir(parents=True, exist_ok=True)
    hermetic_state.write_text("garbage")
    assert state.bump_serial() == 1
