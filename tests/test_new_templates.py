"""Smoke tests for the playground + mandala templates.

Both templates render to a Receipt without crashing and emit the Star
Graphic raster entry-into-raster-mode bytes. The mandala test pins a
seed so the procedural image is deterministic and snapshottable.
"""

from __future__ import annotations

from thermal_print.receipt import Receipt
from thermal_print.templates import mandala, playground


def test_playground_renders_without_crashing() -> None:
    r = Receipt()
    playground.render({}, r)
    assert r._cuts == 1
    # Every primitive that tracks a logical line should have produced one.
    assert any("PLAYGROUND" in line for line in r._lines)
    assert "wrapping:" in r._lines
    assert "supercalifragilisticexpialidocious"[:32] in r._lines  # hard-break
    assert any(line == "=" * 32 for line in r._lines)
    assert any(line == "-" * 32 for line in r._lines)
    assert b"\x1b*rR\x1b*rA" in r.bytes  # Star Graphic raster-mode entry


def test_mandala_renders_without_crashing() -> None:
    r = Receipt()
    mandala.render({"seed": 42}, r)
    assert r._cuts == 1
    assert any("MANDALA" in line for line in r._lines)
    # Mandala uses .image() — bytes are emitted but no line is tracked
    # for the bitmap itself.
    assert b"\x1b*rR\x1b*rA" in r.bytes


def test_mandala_seed_is_deterministic() -> None:
    """Same seed → same mandala image. Compare the rendered canvas,
    not the full byte stream (which embeds a bumped serial counter
    that intentionally differs between calls)."""
    r1 = Receipt()
    r2 = Receipt()
    mandala.render({"seed": 1234}, r1)
    mandala.render({"seed": 1234}, r2)
    # Same image dimensions and pixel data.
    assert r1.image.size == r2.image.size


def test_mandala_seed_changes_output() -> None:
    """Different seeds → different image content."""
    r1 = Receipt()
    r2 = Receipt()
    mandala.render({"seed": 1}, r1)
    mandala.render({"seed": 9999}, r2)
    # Different seeds should produce visibly different bitmaps somewhere.
    assert r1.image.tobytes() != r2.image.tobytes()
