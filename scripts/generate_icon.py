"""Generates the app's original app icon (assets/icon.ico).

Fully procedural - drawn from scratch with Pillow (gradients, bezier-
sampled curved strokes, blurred glow layers), not traced or copied from
any existing artwork, logo, or Blizzard/Diablo asset. The design is an
abstract "infernal sigil" (a central blade flanked by two curved horn
strokes) rendered in a black/red/orange glow palette - evocative of the
game's dark-fantasy tone without reproducing its actual ram-skull logo
or any other copyrighted mark.

Run from repo root:

    .venv/bin/python3 scripts/generate_icon.py

Writes assets/icon.ico (multi-resolution: 16/24/32/48/64/128/256).
"""

import math
import os

from PIL import Image, ImageDraw, ImageFilter

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(REPO_ROOT, "assets", "icon.ico")

SIZE = 512
CENTER = (SIZE // 2, SIZE // 2)

BG_TOP = (8, 4, 4)
BG_BOTTOM = (0, 0, 0)
GLOW_COLOR = (255, 70, 20)
GLYPH_TOP = (255, 176, 40)
GLYPH_BOTTOM = (150, 18, 12)
RIM_COLOR = (255, 214, 140)


def quadratic_bezier(p0, p1, p2, n=40):
    points = []
    for i in range(n + 1):
        t = i / n
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * p1[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * p1[1] + t ** 2 * p2[1]
        points.append((x, y))
    return points


def tapered_stroke(centerline, width_start, width_end):
    """Builds a closed polygon that follows ``centerline`` as a stroke
    whose width linearly tapers from ``width_start`` to ``width_end`` -
    used to turn a bare curve into a solid horn-shaped silhouette."""

    n = len(centerline)
    left_edge = []
    right_edge = []

    for i, (x, y) in enumerate(centerline):
        if i == 0:
            dx, dy = centerline[i + 1][0] - x, centerline[i + 1][1] - y
        elif i == n - 1:
            dx, dy = x - centerline[i - 1][0], y - centerline[i - 1][1]
        else:
            dx = centerline[i + 1][0] - centerline[i - 1][0]
            dy = centerline[i + 1][1] - centerline[i - 1][1]

        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length

        t = i / (n - 1)
        half_width = (width_start + (width_end - width_start) * t) / 2.0

        left_edge.append((x + nx * half_width, y + ny * half_width))
        right_edge.append((x - nx * half_width, y - ny * half_width))

    return left_edge + list(reversed(right_edge))


def vertical_gradient_fill(draw_target_size, top_color, bottom_color):
    grad = Image.new("RGBA", draw_target_size)
    grad_draw = ImageDraw.Draw(grad)
    height = draw_target_size[1]
    for y in range(height):
        t = y / max(height - 1, 1)
        color = tuple(int(top_color[i] + (bottom_color[i] - top_color[i]) * t) for i in range(3))
        grad_draw.line([(0, y), (draw_target_size[0], y)], fill=color + (255,))
    return grad


def build_background():
    bg = vertical_gradient_fill((SIZE, SIZE), BG_TOP, BG_BOTTOM).convert("RGB")
    return bg.convert("RGBA")


def build_glyph_mask():
    """Central blade + two curved flanking horns, as a single white
    silhouette mask on a transparent canvas."""

    mask = Image.new("L", (SIZE, SIZE), 0)
    draw = ImageDraw.Draw(mask)

    cx, cy = CENTER

    # Central blade: a tall kite/flame-like polygon pointing up.
    blade = [
        (cx, cy - 150),
        (cx + 34, cy - 20),
        (cx + 16, cy + 130),
        (cx, cy + 165),
        (cx - 16, cy + 130),
        (cx - 34, cy - 20),
    ]
    draw.polygon(blade, fill=255)

    # Left horn: curves up and out from near the blade's base, tapering
    # to a point.
    left_curve = quadratic_bezier(
        (cx - 26, cy + 30), (cx - 150, cy - 40), (cx - 118, cy - 170)
    )
    left_horn = tapered_stroke(left_curve, width_start=46, width_end=8)
    draw.polygon(left_horn, fill=255)

    # Right horn: mirror of the left.
    right_curve = quadratic_bezier(
        (cx + 26, cy + 30), (cx + 150, cy - 40), (cx + 118, cy - 170)
    )
    right_horn = tapered_stroke(right_curve, width_start=46, width_end=8)
    draw.polygon(right_horn, fill=255)

    # Small crossbar grounding the sigil, evoking a hilt/rune-line.
    draw.polygon(
        [
            (cx - 70, cy + 60), (cx + 70, cy + 60),
            (cx + 58, cy + 82), (cx - 58, cy + 82),
        ],
        fill=255,
    )

    return mask


def compose():
    background = build_background()
    glyph_mask = build_glyph_mask()

    # Soft outer glow: blur a copy of the glyph mask, tint it orange-red,
    # and composite it behind the sharp glyph.
    glow_mask = glyph_mask.filter(ImageFilter.GaussianBlur(22))
    glow_layer = Image.new("RGBA", (SIZE, SIZE), GLOW_COLOR + (0,))
    glow_layer.putalpha(glow_mask.point(lambda v: int(v * 0.85)))

    # A second, wider/fainter halo for extra depth.
    halo_mask = glyph_mask.filter(ImageFilter.GaussianBlur(46))
    halo_layer = Image.new("RGBA", (SIZE, SIZE), GLOW_COLOR + (0,))
    halo_layer.putalpha(halo_mask.point(lambda v: int(v * 0.35)))

    # Sharp glyph fill: vertical orange-to-red gradient, masked to the
    # glyph silhouette, plus a thin brighter rim for readability at
    # small sizes.
    glyph_fill = vertical_gradient_fill((SIZE, SIZE), GLYPH_TOP, GLYPH_BOTTOM)
    glyph_fill.putalpha(glyph_mask)

    rim_mask = glyph_mask.filter(ImageFilter.MaxFilter(5))
    rim_only = Image.eval(rim_mask, lambda v: v)
    rim_layer = Image.new("RGBA", (SIZE, SIZE), RIM_COLOR + (255,))
    # Rim = dilated mask minus original mask (just the outline band).
    import PIL.ImageChops as ImageChops
    rim_band = ImageChops.subtract(rim_mask, glyph_mask)
    rim_layer.putalpha(rim_band.point(lambda v: int(v * 0.9)))

    composed = background
    composed = Image.alpha_composite(composed, halo_layer)
    composed = Image.alpha_composite(composed, glow_layer)
    composed = Image.alpha_composite(composed, rim_layer)
    composed = Image.alpha_composite(composed, glyph_fill)

    return composed


def main():
    image = compose()
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    image.save(OUTPUT_PATH, format="ICO", sizes=sizes)
    print(f"OK: wrote {OUTPUT_PATH} ({', '.join(f'{w}x{h}' for w, h in sizes)})")


if __name__ == "__main__":
    main()
