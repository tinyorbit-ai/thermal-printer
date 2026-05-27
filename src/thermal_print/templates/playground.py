"""playground — exercises every Receipt primitive.

A controlled layout test. Run this after touching anything in
``src/thermal_print/receipt.py`` to verify the bitmap renderer's output
still looks right on real paper.

Touches every public method on :class:`Receipt`: ``logo``, ``header``,
``subheader``, ``divider`` (every standard char + a custom one),
``row`` (short label, long label that truncates with ``…``, value that
spills the grid), ``text`` (single line, wrapping, multi-line via
``\\n``, hard-break of a single oversized token), ``spacer``,
``footer``, ``serial``, ``cut``.
"""

from __future__ import annotations

from typing import Any

from ..receipt import Receipt

NAME = "playground"


def render(ctx: dict[str, Any], r: Receipt) -> None:
    r.logo("claude")
    r.header("PLAYGROUND")
    r.subheader("layout test")
    r.divider("=")

    # — rows ————————————————————————————————————
    r.text("rows:")
    r.row("Short", "42")
    r.row("Medium label", "1,234")
    r.row("A label that's much too long", "1")
    r.row("ignored", "v" * 36)  # value exceeds grid → label dropped
    r.divider("-")

    # — text wrapping ————————————————————————————
    r.text("wrapping:")
    r.text(
        "this is a paragraph that runs past the 32-character grid "
        "and should wrap onto multiple lines without dropping any words."
    )
    r.spacer()

    # — hard break of an oversized token —————————
    r.text("hard-break:")
    r.text("supercalifragilisticexpialidocious")
    r.spacer()

    # — multi-line via \n ————————————————————————
    r.text("multi-line:")
    r.text("line one.\nline two.\nline three.")
    r.spacer()

    # — every divider char ——————————————————————
    r.text("dividers:")
    r.divider("=")
    r.divider("-")
    r.divider("·")
    r.divider("*")
    r.divider("~")
    r.spacer()

    r.footer("playground")
    r.serial()
    r.cut()
