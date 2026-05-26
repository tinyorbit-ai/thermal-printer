"""demo — exercises every primitive in the Receipt grammar.

The visual showcase for phase 2. Phase 3 will add ``.logo()`` and ``.serial()``
to the demo to prove the full visual identity.
"""

from __future__ import annotations

from typing import Any

from ..receipt import Receipt

NAME = "demo"


def render(ctx: dict[str, Any], r: Receipt) -> None:
    r.header("CLAUDE CODE")
    r.divider("=")
    r.row("Tokens", "4,221")
    r.row("Time", "47m")
    r.divider("-")
    r.text("a sweet little summary line.")
    r.footer("thermal-print")
    r.cut()
