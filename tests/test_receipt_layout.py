"""Receipt layout grammar — snapshot + structural assertions."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from thermal_print.receipt import ASSETS_DIR, Receipt
from thermal_print.templates import demo as demo_template

FIXTURE_DIR = Path(__file__).parent / "fixtures"
DEMO_SNAPSHOT = FIXTURE_DIR / "demo_receipt.bin"


def _build_demo_receipt(hermetic_state: Path) -> Receipt:
    """Render the real demo template against a Receipt with the serial
    counter seeded so the snapshot is deterministic."""
    hermetic_state.parent.mkdir(parents=True, exist_ok=True)
    hermetic_state.write_text('{"serial": 41}')  # next bump → 42
    r = Receipt()
    demo_template.render({}, r)
    return r


# ── snapshot ───────────────────────────────────────────────────────────


def test_demo_byte_stream_matches_snapshot(hermetic_state: Path) -> None:
    r = _build_demo_receipt(hermetic_state)
    actual = r.bytes
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    if not DEMO_SNAPSHOT.exists():
        DEMO_SNAPSHOT.write_bytes(actual)
    expected = DEMO_SNAPSHOT.read_bytes()
    assert actual == expected, (
        "demo byte stream changed. If intentional, delete "
        f"tests/fixtures/{DEMO_SNAPSHOT.name} and re-run."
    )


# ── structural (the snapshot's pair) ───────────────────────────────────


def test_demo_has_exactly_one_cut(hermetic_state: Path) -> None:
    r = _build_demo_receipt(hermetic_state)
    assert r._cuts == 1


def test_demo_no_line_exceeds_grid(hermetic_state: Path) -> None:
    r = _build_demo_receipt(hermetic_state)
    for line in r._lines:
        assert len(line) <= Receipt.GRID_WIDTH, (
            f"line exceeds 32 chars ({len(line)}): {line!r}"
        )


def test_demo_serial_present(hermetic_state: Path) -> None:
    r = _build_demo_receipt(hermetic_state)
    # Serial was seeded to 41, so the bump emits REC-#0042.
    assert any(re.fullmatch(r"REC-#0042", line) for line in r._lines)


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


# ── logo ───────────────────────────────────────────────────────────────


def test_logo_crab_loads() -> None:
    """The shipped crab logo asset is present and loadable."""
    asset = ASSETS_DIR / "crab.png"
    assert asset.exists(), f"missing logo asset: {asset}"
    r = Receipt()
    r.logo("crab")
    # logo emits raster bytes but no tracked _lines
    assert len(r._lines) == 0
    assert len(r.bytes) > 0


def test_logo_missing_raises() -> None:
    r = Receipt()
    with pytest.raises(FileNotFoundError):
        r.logo("does-not-exist")


# ── serial ─────────────────────────────────────────────────────────────


def test_serial_starts_at_one_on_fresh_state() -> None:
    r = Receipt()
    r.serial()
    assert r._lines == ["REC-#0001"]


def test_serial_increments_across_receipts(hermetic_state: Path) -> None:
    first = Receipt()
    first.serial()
    second = Receipt()
    second.serial()
    assert first._lines == ["REC-#0001"]
    assert second._lines == ["REC-#0002"]


def test_serial_format_is_zero_padded_to_four(hermetic_state: Path) -> None:
    hermetic_state.parent.mkdir(parents=True, exist_ok=True)
    hermetic_state.write_text('{"serial": 8}')  # → 9
    r = Receipt()
    r.serial()
    assert r._lines == ["REC-#0009"]


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
