"""Receipt layout grammar — snapshot + structural assertions."""

from __future__ import annotations

from pathlib import Path

import pytest

from thermal_print.receipt import Receipt

FIXTURE_DIR = Path(__file__).parent / "fixtures"
DEMO_SNAPSHOT = FIXTURE_DIR / "demo_receipt.bin"


def _build_demo_receipt() -> Receipt:
    """The exact sequence demo.py emits — kept in sync so the snapshot is a
    faithful record of the demo template's byte stream."""
    r = Receipt()
    r.header("CLAUDE CODE")
    r.divider("=")
    r.row("Tokens", "4,221")
    r.row("Time", "47m")
    r.divider("-")
    r.text("a sweet little summary line.")
    r.footer("thermal-print")
    r.cut()
    return r


# ── snapshot ───────────────────────────────────────────────────────────


def test_demo_byte_stream_matches_snapshot() -> None:
    r = _build_demo_receipt()
    actual = r.bytes
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    if not DEMO_SNAPSHOT.exists():
        DEMO_SNAPSHOT.write_bytes(actual)
    expected = DEMO_SNAPSHOT.read_bytes()
    assert actual == expected, (
        "demo byte stream changed. If intentional, delete "
        f"{DEMO_SNAPSHOT.relative_to(Path.cwd()) if DEMO_SNAPSHOT.is_absolute() else DEMO_SNAPSHOT} "
        "and re-run."
    )


# ── structural (the snapshot's pair) ───────────────────────────────────


def test_demo_has_exactly_one_cut() -> None:
    r = _build_demo_receipt()
    assert r._cuts == 1


def test_demo_no_line_exceeds_grid() -> None:
    r = _build_demo_receipt()
    for line in r._lines:
        assert len(line) <= Receipt.GRID_WIDTH, (
            f"line exceeds 32 chars ({len(line)}): {line!r}"
        )


# ── overflow policy: row ───────────────────────────────────────────────


def test_row_fits_short_label_and_value() -> None:
    r = Receipt()
    r.row("Tokens", "4,221")
    line = r._lines[0]
    assert len(line) == 32
    assert line.startswith("Tokens")
    assert line.endswith("4,221")


def test_row_truncates_long_label_with_ellipsis() -> None:
    r = Receipt()
    r.row("a very long label that doesn't fit alongside the value", "42")
    line = r._lines[0]
    assert len(line) == 32
    assert "…" in line
    assert line.endswith("42")


def test_row_value_alone_fills_grid_drops_label() -> None:
    r = Receipt()
    r.row("ignored", "x" * 40)
    line = r._lines[0]
    assert len(line) == 32
    assert line == "x" * 32


# ── overflow policy: text ──────────────────────────────────────────────


def test_text_wraps_at_grid_width() -> None:
    r = Receipt()
    r.text("this is a sentence that exceeds the thirty two character grid by enough.")
    assert len(r._lines) >= 2
    for line in r._lines:
        assert len(line) <= 32


def test_text_hard_breaks_oversized_token() -> None:
    r = Receipt()
    r.text("a" * 50)
    assert len(r._lines) == 2
    assert r._lines[0] == "a" * 32
    assert r._lines[1] == "a" * 18


def test_text_preserves_explicit_newlines() -> None:
    r = Receipt()
    r.text("one\ntwo")
    assert r._lines == ["one", "two"]


# ── dividers ───────────────────────────────────────────────────────────


def test_divider_is_full_width() -> None:
    r = Receipt()
    r.divider("=")
    r.divider("-")
    r.divider("·")
    assert r._lines == ["=" * 32, "-" * 32, "·" * 32]


def test_divider_rejects_multi_char() -> None:
    r = Receipt()
    with pytest.raises(ValueError):
        r.divider("==")


# ── cut + send ─────────────────────────────────────────────────────────


def test_multiple_cuts_count_correctly() -> None:
    r = Receipt()
    r.cut()
    r.cut()
    assert r._cuts == 2


def test_send_writes_bytes_and_closes_printer() -> None:
    class FakePrinter:
        def __init__(self) -> None:
            self.raw_called_with: bytes | None = None
            self.closed = False

        def _raw(self, payload: bytes) -> None:
            self.raw_called_with = payload

        def close(self) -> None:
            self.closed = True

    r = Receipt()
    r.text("ping").cut()
    fp = FakePrinter()
    r.send(fp)  # type: ignore[arg-type]
    assert fp.raw_called_with == r.bytes
    assert fp.closed is True
