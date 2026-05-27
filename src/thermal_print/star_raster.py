"""Star Graphic raster encoder for the TSP143IIIU.

The TSP143IIIU only accepts bitmap data via Star's proprietary command
set. The byte sequence below was reverse-engineered from Star's own
open-source CUPS filter (`rastertostar.c`, GPLv2) and verified on
hardware 2026-05-27 — see
[[notes/2026-05-27-tsp143iiiu-default-mode]] for the full incident.

The **load-bearing** sub-sequence is ``ESC * r R`` + ``ESC * r A`` —
without it the printer accepts every byte, reports no error, and
silently drops the entire job.
"""

from __future__ import annotations

from typing import Final

from PIL import Image

# TSP143IIIU at 72mm = 576 dots wide. Confirmed by self-test
# (Print Area 72mm) and Star CUPS filter (TSP100_MAX_WIDTH 72).
PRINTABLE_WIDTH_PX: Final[int] = 576


def encode_job(img: Image.Image, *, cut: bool = True) -> bytes:
    """Encode a PIL Image as a complete Star Graphic raster print job.

    The image is converted to 1-bit mode if not already. Width must be
    no greater than :data:`PRINTABLE_WIDTH_PX`; it is right-padded to a
    multiple of 8 (byte boundary) if necessary.

    Set ``cut=False`` to suppress the auto-cut at end-of-job (for
    receipts that *don't* want to be cut — none currently, but the
    plumbing is here).
    """
    if img.mode != "1":
        img = img.convert("1")

    if img.width > PRINTABLE_WIDTH_PX:
        raise ValueError(
            f"image width {img.width} exceeds printer width {PRINTABLE_WIDTH_PX}px"
        )
    if img.width % 8 != 0:
        padded = Image.new("1", ((img.width + 7) // 8 * 8, img.height), 1)
        padded.paste(img, (0, 0))
        img = padded

    w = img.width
    h = img.height
    bw = w // 8

    # Pack to monochrome: 1 = black dot, MSB first, top-to-bottom.
    rows: list[bytes] = []
    px = img.load()
    for y in range(h):
        row = bytearray(bw)
        for x in range(w):
            if px[x, y] == 0:  # PIL "1": 0=black, 255=white
                row[x // 8] |= 1 << (7 - (x % 8))
        rows.append(bytes(row))

    out = bytearray()
    # ── jobSetup ────────────────────────────────────────────────────
    out += b"\x1b\x40"                   # ESC @ — printer init
    out += b"\x1b\x1d\x03\x03\x00\x00"   # clear-data-start (TSP143 specific)
    out += b"\x1b*rR\x1b*rA"             # enter raster mode (LOAD-BEARING)
    out += b"\x1b*rP0\x00"               # page type = receipt
    if cut:
        out += b"\x1b*rE13\x00"          # doc cut type = partial cut
    else:
        out += b"\x1b*rE1\x00"           # doc cut type = no cut

    # ── pageSetup ───────────────────────────────────────────────────
    out += b"\x00"                       # start page

    # ── raster lines ────────────────────────────────────────────────
    blanks = 0
    for row in rows:
        # Trim trailing zero bytes to shorten the wire format.
        last = 0
        for i in range(len(row) - 1, -1, -1):
            if row[i] != 0:
                last = i + 1
                break
        if last == 0:
            blanks += 1
            continue
        if blanks > 0:
            out += b"\x1b*rY%d\x00" % blanks
            blanks = 0
        out += b"b" + bytes([last & 0xFF, (last >> 8) & 0xFF])
        out += bytes(row[:last])

    # ── endPage ─────────────────────────────────────────────────────
    out += b"\x1b*rY1\x00\x1b\x0c"       # feed 1 line + ESC FF (form feed)

    # ── endJob ──────────────────────────────────────────────────────
    out += b"\x1b\x1d\x03\x04\x00\x00"   # clear-data-finish (TSP143)
    out += b"\x04\x1b*rB"                # EOT + ESC * r B

    return bytes(out)


__all__ = ["PRINTABLE_WIDTH_PX", "encode_job"]
