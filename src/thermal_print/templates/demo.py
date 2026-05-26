"""demo — exercises every primitive in the Receipt grammar.

The visual showcase for the project: a centered crab logo, a double-height
header, dividers, two rows, a body line, a small centered footer, the
persistent serial, and one cut.
"""

from __future__ import annotations

from typing import Any

from ..receipt import Receipt

NAME = "demo"


def render(ctx: dict[str, Any], r: Receipt) -> None:
    r.logo("crab")
    r.header("CLAUDE CODE")
    r.divider("=")
    r.row("Tokens", "4,221")
    r.row("Time", "47m")
    r.divider("-")
    r.text("a sweet little summary line.")
    r.spacer()
    r.footer("thermal-print")
    r.serial()
    r.cut()
