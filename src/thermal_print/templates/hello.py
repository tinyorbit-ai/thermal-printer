"""hello — phase 1's smoke test, now a template."""

from __future__ import annotations

from typing import Any

from ..receipt import Receipt

NAME = "hello"


def render(ctx: dict[str, Any], r: Receipt) -> None:
    r.text("hello, matt")
    r.cut()
