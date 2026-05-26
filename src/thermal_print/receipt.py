"""Receipt builder — the 32-char layout grammar.

The only module that knows about font-A width, alignment, dividers, and the
cut command. Templates compose receipts by calling these methods; the CLI
flushes the accumulated bytes via :py:meth:`Receipt.send`.

Cut ownership lives here (per [[architecture]]); :mod:`printer` only opens,
writes, and closes the USB device.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from escpos.printer import Dummy
from PIL import Image

from . import state

if TYPE_CHECKING:
    from escpos.escpos import Escpos


ASSETS_DIR = Path(__file__).parent / "assets"


__all__ = ["Receipt", "GRID_WIDTH"]


GRID_WIDTH = 32
"""Design grid width at font A. Per ADR 0004 this is the *design* choice; the
TSP 100III's hardware printable width at font A is wider, but legibility
beats density."""


class Receipt:
    """Accumulate escpos bytes for one receipt, then flush to a printer.

    Internal byte buffer is a python-escpos :class:`Dummy` printer — it has
    the same API as the real printer (``text``, ``set``, ``cut``, …) but
    captures bytes to ``.output`` instead of writing to USB. This keeps
    layout testable in isolation: render to bytes, compare to a fixture.

    Auxiliary state (``_cuts``, ``_lines``) lets structural tests assert
    "exactly one cut" and "no row exceeds 32 chars" without parsing the raw
    byte stream.
    """

    GRID_WIDTH = GRID_WIDTH

    def __init__(self) -> None:
        self._buf: Dummy = Dummy()
        self._cuts: int = 0
        self._lines: list[str] = []

    # ── primitive: track + write ────────────────────────────────────────

    def _writeln(self, line: str) -> None:
        """Track the line for structural assertions and emit it."""
        self._lines.append(line)
        self._buf.textln(line)

    # ── logo ────────────────────────────────────────────────────────────

    def logo(self, name: str) -> Receipt:
        """Raster a 1-bit PNG from :data:`ASSETS_DIR`, centered.

        ``name`` is the bare filename without extension (e.g. ``"crab"``
        loads ``assets/crab.png``). python-escpos handles the raster
        encoding via the GS v 0 command path.
        """
        asset = ASSETS_DIR / f"{name}.png"
        if not asset.exists():
            raise FileNotFoundError(f"logo asset not found: {asset}")
        img = Image.open(asset)
        img.load()
        self._buf.set(align="center")
        self._buf.image(img)
        self._buf.set()
        return self

    # ── serial ──────────────────────────────────────────────────────────

    def serial(self) -> Receipt:
        """Emit ``REC-#NNNN``, right-aligned. Bumps the persisted counter."""
        n = state.bump_serial()
        line = f"REC-#{n:04d}"
        self._buf.set(align="right")
        self._writeln(line)
        self._buf.set()
        return self

    # ── headings ────────────────────────────────────────────────────────

    def header(self, text: str) -> Receipt:
        """Double-height, double-width, centered, bold. Receipt title."""
        self._buf.set(double_height=True, double_width=True, align="center", bold=True)
        self._writeln(text)
        self._buf.set()  # reset to defaults
        return self

    def subheader(self, text: str) -> Receipt:
        """Single-height, centered, bold. Receipt sub-title."""
        self._buf.set(align="center", bold=True)
        self._writeln(text)
        self._buf.set()
        return self

    # ── separators ──────────────────────────────────────────────────────

    def divider(self, char: str = "-") -> Receipt:
        """Full-width divider line. Standard chars per ADR 0004: ``-`` light,
        ``=`` heavy, ``·`` dotted."""
        if len(char) != 1:
            raise ValueError(f"divider char must be a single character, got {char!r}")
        self._writeln(char * self.GRID_WIDTH)
        return self

    def spacer(self) -> Receipt:
        """One blank line."""
        self._writeln("")
        return self

    # ── content ─────────────────────────────────────────────────────────

    def row(self, label: str, value: str) -> Receipt:
        """A label/value row, padded to fill the 32-char grid.

        Overflow policy: the **value** is the contract — it is reserved
        space-first and never truncated when it fits the grid. The
        **label** is truncated from the right with ``…`` if it doesn't
        fit alongside the value with at least one separating space. If
        the value alone fills/exceeds the grid, the label is dropped and
        the value is hard-truncated.
        """
        label = str(label)
        value = str(value)

        if len(value) >= self.GRID_WIDTH:
            line = value[: self.GRID_WIDTH]
        else:
            max_label_len = self.GRID_WIDTH - len(value) - 1  # 1+ separating space
            if len(label) > max_label_len:
                label = label[: max_label_len - 1] + "…" if max_label_len >= 1 else ""
            pad = self.GRID_WIDTH - len(label) - len(value)
            line = label + " " * pad + value

        self._writeln(line)
        return self

    def text(self, txt: str) -> Receipt:
        """Plain text. Word-wrapped at 32 chars; tokens longer than 32 hard-break."""
        for line in _wrap(txt, self.GRID_WIDTH):
            self._writeln(line)
        return self

    # ── footer ──────────────────────────────────────────────────────────

    def footer(self, text: str) -> Receipt:
        """Single-line footer, small (font B) and centered."""
        self._buf.set(align="center", font="b")
        self._writeln(text)
        self._buf.set()
        return self

    # ── cut + flush ─────────────────────────────────────────────────────

    def cut(self) -> Receipt:
        """Emit a partial cut. Tracked so tests can assert exactly one per receipt."""
        self._buf.cut()
        self._cuts += 1
        return self

    def send(self, printer: Escpos) -> None:
        """Flush the accumulated byte stream to the printer in one write, then close.

        Single USB write per print where the OS allows — keeps the device
        and the layout grammar decoupled.
        """
        try:
            printer._raw(self._buf.output)
        finally:
            printer.close()

    # ── introspection (for tests + debugging) ───────────────────────────

    @property
    def bytes(self) -> bytes:
        """Raw escpos byte stream accumulated so far."""
        return self._buf.output


def _wrap(text: str, width: int) -> list[str]:
    """Word-wrap ``text`` to ``width`` characters.

    Preserves explicit newlines (they start a new wrapped block). Tokens
    longer than ``width`` are hard-broken across lines.
    """
    if not text:
        return [""]

    lines: list[str] = []
    for paragraph in text.split("\n"):
        if paragraph == "":
            lines.append("")
            continue
        current = ""
        for word in paragraph.split(" "):
            # Hard-break tokens longer than the grid width.
            while len(word) > width:
                if current:
                    lines.append(current)
                    current = ""
                lines.append(word[:width])
                word = word[width:]

            if not current:
                current = word
            elif len(current) + 1 + len(word) <= width:
                current = f"{current} {word}"
            else:
                lines.append(current)
                current = word
        lines.append(current)
    return lines
