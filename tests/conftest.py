"""Test fixtures shared across the suite.

The autouse ``hermetic_state`` fixture redirects ``state.json`` to a
per-test temp path. No test should ever touch the real
``~/.thermal-printer/`` — the guard test in ``test_state.py`` asserts the
env var is present, which catches a misconfigured suite before it can
silently mutate the real state file.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def hermetic_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    state_file = tmp_path / "state.json"
    monkeypatch.setenv("THERMAL_PRINT_STATE", str(state_file))
    return state_file
