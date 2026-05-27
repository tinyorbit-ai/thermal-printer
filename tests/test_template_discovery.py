"""Template auto-discovery — registry, syntax errors, duplicate NAMEs."""

from __future__ import annotations

from pathlib import Path

import pytest

from thermal_print.cli import _discover_in_path, discover_templates


# ── shipped templates ──────────────────────────────────────────────────


def test_shipped_registry_has_all_templates() -> None:
    registry = discover_templates()
    for name in ("hello", "demo", "session", "receipt", "playground", "mandala"):
        assert name in registry, f"shipped template missing: {name}"
        assert callable(registry[name])


# ── _smoke as a valid template (gate item 4a) ──────────────────────────


def test_dropping_smoke_template_makes_it_dispatch(tmp_path: Path) -> None:
    (tmp_path / "_smoke.py").write_text(
        "NAME = '_smoke'\n"
        "def render(ctx, r):\n"
        "    r.text('smoke').cut()\n"
    )
    registry = _discover_in_path(tmp_path, None)
    assert "_smoke" in registry


# ── syntax error path (gate item 4b) ───────────────────────────────────


def test_syntax_error_template_exits_non_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "broken.py").write_text("def render(ctx, r:\n    pass\n")
    with pytest.raises(SystemExit) as exc:
        _discover_in_path(tmp_path, None)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "broken.py" in err
    assert "syntax error" in err.lower()


# ── duplicate NAME path (gate item 4c) ─────────────────────────────────


def test_duplicate_name_exits_non_zero_naming_both_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "first.py").write_text(
        "NAME = 'dup'\n"
        "def render(ctx, r):\n"
        "    r.text('first')\n"
    )
    (tmp_path / "second.py").write_text(
        "NAME = 'dup'\n"
        "def render(ctx, r):\n"
        "    r.text('second')\n"
    )
    with pytest.raises(SystemExit) as exc:
        _discover_in_path(tmp_path, None)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "first.py" in err and "second.py" in err
    assert "dup" in err


# ── missing-attribute path ─────────────────────────────────────────────


def test_template_missing_attributes_exits_non_zero(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "headless.py").write_text("X = 1\n")
    with pytest.raises(SystemExit) as exc:
        _discover_in_path(tmp_path, None)
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "headless.py" in err
    assert "NAME" in err and "render" in err


# ── __init__.py is skipped ─────────────────────────────────────────────


def test_init_py_is_not_treated_as_template(tmp_path: Path) -> None:
    (tmp_path / "__init__.py").write_text("# package marker\n")
    (tmp_path / "real.py").write_text(
        "NAME = 'real'\n"
        "def render(ctx, r):\n"
        "    r.text('hi')\n"
    )
    registry = _discover_in_path(tmp_path, None)
    assert list(registry) == ["real"]
