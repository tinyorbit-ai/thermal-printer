"""mandala — procedural radial bitmap, unique each print.

Generates a 480×480 1-bit mandala from concentric rings, radial spokes,
and an outer petal crown. The geometry is randomized via a seed (pass
``ctx["seed"]`` for reproducibility; otherwise time-based) so every
print is its own thing — pushing the bitmap path the way ``hello`` or
the row-grid templates can't.

Pure Pillow drawing primitives; no external assets. Receipt-tall by
design: the image alone takes ~80mm of paper, plus header + footer.
"""

from __future__ import annotations

import math
import random
import time
from typing import Any

from PIL import Image, ImageDraw

from ..receipt import Receipt

NAME = "mandala"

# The image is square and fills the printable width minus a small
# border. 480 / 8 = 60 bytes-per-line wire format, well inside the
# printer's 576px capacity with room for visual breathing.
SIZE = 480


def render(ctx: dict[str, Any], r: Receipt) -> None:
    seed_arg = ctx.get("seed")
    seed = int(seed_arg) if seed_arg is not None else int(time.time())
    rng = random.Random(seed)

    img = _draw_mandala(rng)

    r.logo("claude")
    r.header("MANDALA")
    r.subheader(f"#{seed % 10000:04d}")
    r.divider("=")
    r.paste(img)
    r.divider("-")
    r.text("a moment of quiet")
    r.text("from your terminal")
    r.spacer()
    r.footer("thermal-print")
    r.serial()
    r.cut()


def _draw_mandala(rng: random.Random) -> Image.Image:
    """Compose the radial pattern: outer ring + concentric rings +
    radial spokes + petal crown + center dot."""
    img = Image.new("1", (SIZE, SIZE), 1)
    d = ImageDraw.Draw(img)
    cx = cy = SIZE // 2

    # Outer frame.
    d.ellipse([4, 4, SIZE - 4, SIZE - 4], outline=0, width=4)

    # Concentric rings, irregularly spaced.
    radius = 30
    while radius < SIZE // 2 - 12:
        d.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            outline=0,
            width=2,
        )
        radius += rng.randint(22, 44)

    # Radial spokes from a small inner radius outward.
    n_spokes = rng.choice([8, 12, 16, 24])
    inner_r, outer_r = 30, SIZE // 2 - 12
    for i in range(n_spokes):
        angle = 2 * math.pi * i / n_spokes
        x1 = cx + inner_r * math.cos(angle)
        y1 = cy + inner_r * math.sin(angle)
        x2 = cx + outer_r * math.cos(angle)
        y2 = cy + outer_r * math.sin(angle)
        d.line([(x1, y1), (x2, y2)], fill=0, width=2)

    # Petal crown — circles offset around a mid-ring radius.
    petal_ring = rng.randint(115, 175)
    petal_size = rng.randint(18, 32)
    n_petals = rng.choice([8, 12, 16])
    for i in range(n_petals):
        angle = 2 * math.pi * i / n_petals + math.pi / n_petals
        px = cx + petal_ring * math.cos(angle)
        py = cy + petal_ring * math.sin(angle)
        d.ellipse(
            [px - petal_size, py - petal_size, px + petal_size, py + petal_size],
            outline=0,
            width=2,
        )

    # Center dot, solid.
    d.ellipse([cx - 10, cy - 10, cx + 10, cy + 10], fill=0)

    return img
