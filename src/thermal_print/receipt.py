"""Receipt builder — bitmap renderer for the TSP143IIIU.

The printer accepts only Star Graphic raster (see [[notes/2026-05-27-tsp143iiiu-default-mode]]),
so every primitive draws onto a growing 576-pixel-wide monochrome PIL
image. :meth:`Receipt.send` crops to actual content, encodes the
bitmap via :mod:`star_raster`, and writes it to the USB device.

The 32-char design grid from ADR 0004 survives — it's just a layout
choice now (32 chars × ~18px = 576px), not a property of the printer.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

from . import state
from .star_raster import PRINTABLE_WIDTH_PX, encode_job

if TYPE_CHECKING:
    from .printer import StarUsbPrinter

ASSETS_DIR = Path(__file__).parent / "assets"

# 32-character design grid (ADR 0004 design choice).
GRID_WIDTH = 32

# 576 / 32 = 18 px/char target. Menlo at size 28 gives ~17 px monospace
# (32 chars = 540 px) — comfortable inside the 576 px printable area.
BODY_FONT_SIZE = 28
HEADER_FONT_SIZE = 56  # ~2× body for the "double-height" effect
FOOTER_FONT_SIZE = 18  # small, centered (ADR 0004 footer)

_BODY_FONT_PATH = "/System/Library/Fonts/Menlo.ttc"

# Vertical padding between lines so type isn't crushed against itself.
_LINE_PADDING = 4

# Initial canvas height; the image is cropped to the actual content at
# send time. 4096 px ≈ 51 cm of paper — way past any plausible receipt.
_INITIAL_CANVAS_H = 4096

# Left/right margins inside the printable area.
_MARGIN_PX = 8


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(_BODY_FONT_PATH, size)
    except OSError:
        # On a non-macOS dev box (CI) PIL's default font keeps tests passing.
        return ImageFont.load_default()


class Receipt:
    """Accumulate a receipt image, then flush it as Star Graphic raster.

    Auxiliary state (``_cuts``, ``_lines``) lets structural tests assert
    "exactly one cut" and "no row exceeds 32 chars" without inspecting
    raw bitmap pixels.
    """

    GRID_WIDTH = GRID_WIDTH
    WIDTH_PX = PRINTABLE_WIDTH_PX

    def __init__(self) -> None:
        self._img: Image.Image = Image.new("1", (self.WIDTH_PX, _INITIAL_CANVAS_H), 1)
        self._draw: ImageDraw.ImageDraw = ImageDraw.Draw(self._img)
        self._y: int = 0
        self._cuts: int = 0
        self._lines: list[str] = []

        self._font_body = _load_font(BODY_FONT_SIZE)
        self._font_header = _load_font(HEADER_FONT_SIZE)
        self._font_footer = _load_font(FOOTER_FONT_SIZE)

        self._lh_body = self._font_body.size + _LINE_PADDING
        self._lh_header = self._font_header.size + _LINE_PADDING * 2
        self._lh_footer = self._font_footer.size + _LINE_PADDING

        # Pre-measure monospace body-font character width once. Menlo is
        # truly monospaced, so any non-space character works.
        bbox = self._font_body.getbbox("M")
        self._body_char_w = bbox[2] - bbox[0]

    # ── primitives ──────────────────────────────────────────────────────

    def _track_line(self, text: str) -> None:
        """Record the logical text content for structural assertions."""
        self._lines.append(text)

    def _draw_centered(self, text: str, font: ImageFont.FreeTypeFont) -> int:
        bbox = font.getbbox(text)
        text_w = bbox[2] - bbox[0]
        x = max(_MARGIN_PX, (self.WIDTH_PX - text_w) // 2)
        self._draw.text((x, self._y), text, font=font, fill=0)
        return text_w

    def _draw_left(self, text: str, font: ImageFont.FreeTypeFont, x: int = _MARGIN_PX) -> None:
        self._draw.text((x, self._y), text, font=font, fill=0)

    def _draw_right(self, text: str, font: ImageFont.FreeTypeFont) -> None:
        bbox = font.getbbox(text)
        text_w = bbox[2] - bbox[0]
        x = self.WIDTH_PX - text_w - _MARGIN_PX
        self._draw.text((x, self._y), text, font=font, fill=0)

    # ── images ──────────────────────────────────────────────────────────

    def _paste_image(self, bitmap: Image.Image) -> None:
        """Centered paste with auto-downscale to the printable width."""
        if bitmap.mode != "1":
            bitmap = bitmap.convert("1")
        if bitmap.width > self.WIDTH_PX:
            new_w = (self.WIDTH_PX // 8) * 8
            new_h = int(bitmap.height * new_w / bitmap.width)
            bitmap = bitmap.resize((new_w, new_h), Image.NEAREST)
        x = (self.WIDTH_PX - bitmap.width) // 2
        self._img.paste(bitmap, (x, self._y))
        self._y += bitmap.height + _LINE_PADDING

    def logo(self, name: str) -> "Receipt":
        """Paste a 1-bit PNG from ``assets/<name>.png``, centered."""
        asset = ASSETS_DIR / f"{name}.png"
        if not asset.exists():
            raise FileNotFoundError(f"logo asset not found: {asset}")
        self._paste_image(Image.open(asset))
        return self

    def paste(self, img: Image.Image) -> "Receipt":
        """Paste an arbitrary PIL ``Image`` onto the canvas, centered.

        The image is converted to 1-bit and auto-downscaled if wider
        than the printable area. Distinct from :meth:`logo` (which
        loads from ``assets/``) and from the :attr:`image` property
        (which returns the rendered receipt).
        """
        self._paste_image(img)
        return self

    # ── serial ──────────────────────────────────────────────────────────

    def serial(self) -> "Receipt":
        """Emit ``REC-#NNNN`` right-aligned. Bumps the persisted counter."""
        n = state.bump_serial()
        text = f"REC-#{n:04d}"
        self._draw_right(text, self._font_body)
        self._track_line(text)
        self._y += self._lh_body
        return self

    # ── headings ────────────────────────────────────────────────────────

    def header(self, text: str) -> "Receipt":
        """Double-height (≈2×) centered header."""
        self._draw_centered(text, self._font_header)
        self._track_line(text)
        self._y += self._lh_header
        return self

    def subheader(self, text: str) -> "Receipt":
        """Single-height centered subheader (uses body font)."""
        self._draw_centered(text, self._font_body)
        self._track_line(text)
        self._y += self._lh_body
        return self

    # ── separators ──────────────────────────────────────────────────────

    def divider(self, char: str = "-") -> "Receipt":
        """Full-width divider line. Standard chars (ADR 0004): ``-`` light,
        ``=`` heavy, ``·`` dotted."""
        if len(char) != 1:
            raise ValueError(f"divider char must be a single character, got {char!r}")
        line = char * self.GRID_WIDTH
        self._draw_left(line, self._font_body)
        self._track_line(line)
        self._y += self._lh_body
        return self

    def spacer(self) -> "Receipt":
        """One blank line."""
        self._track_line("")
        self._y += self._lh_body
        return self

    # ── content ─────────────────────────────────────────────────────────

    def row(self, label: str, value: str) -> "Receipt":
        """Label-on-left / value-on-right row, both sharing the 32-char grid.

        Overflow policy (ADR 0004): the value is reserved space-first;
        if value alone fills the grid it gets hard-truncated and the
        label is dropped. Otherwise the label is truncated from the
        right with ``…`` to leave at least one separating space.
        """
        label = str(label)
        value = str(value)

        if len(value) >= self.GRID_WIDTH:
            line = value[: self.GRID_WIDTH]
            self._draw_left(line, self._font_body)
        else:
            max_label_len = self.GRID_WIDTH - len(value) - 1
            if len(label) > max_label_len:
                label = label[: max_label_len - 1] + "…" if max_label_len >= 1 else ""
            pad = self.GRID_WIDTH - len(label) - len(value)
            line = label + " " * pad + value
            # Draw label at the left, value right-aligned.
            if label:
                self._draw_left(label, self._font_body)
            self._draw_right(value, self._font_body)

        self._track_line(line)
        self._y += self._lh_body
        return self

    def text(self, txt: str) -> "Receipt":
        """Plain text. Word-wrapped at 32 chars; tokens longer than 32 hard-break."""
        for line in _wrap(txt, self.GRID_WIDTH):
            self._draw_left(line, self._font_body)
            self._track_line(line)
            self._y += self._lh_body
        return self

    # ── footer ──────────────────────────────────────────────────────────

    def footer(self, text: str) -> "Receipt":
        """Small (footer font) centered single line."""
        self._draw_centered(text, self._font_footer)
        self._track_line(text)
        self._y += self._lh_footer
        return self

    # ── cut + flush ─────────────────────────────────────────────────────

    def cut(self) -> "Receipt":
        """Mark the receipt for partial cut. Tracked so tests can assert
        exactly one cut per receipt; the actual cut byte is emitted by
        :func:`star_raster.encode_job` from a flag at send time."""
        self._cuts += 1
        return self

    def send(self, printer: "StarUsbPrinter") -> None:
        """Crop the image to actual content, encode as Star Graphic raster,
        and write to the printer in one USB transaction."""
        try:
            payload = self.bytes
            printer.write(payload)
        finally:
            printer.close()

    # ── introspection ───────────────────────────────────────────────────

    @property
    def image(self) -> Image.Image:
        """The rendered receipt as a PIL Image, cropped to actual content."""
        # Add a small bottom margin so the last line isn't flush against the cut.
        end_y = min(self._y + _LINE_PADDING * 2, _INITIAL_CANVAS_H)
        return self._img.crop((0, 0, self.WIDTH_PX, end_y))

    @property
    def bytes(self) -> bytes:
        """The full Star Graphic raster job as a byte string."""
        return encode_job(self.image, cut=self._cuts > 0)


# ── helpers ────────────────────────────────────────────────────────────


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


__all__ = ["Receipt", "ASSETS_DIR", "GRID_WIDTH"]
