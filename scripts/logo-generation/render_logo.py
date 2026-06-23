#!/usr/bin/env python3
"""Render the Stemchotic ASCII logo to a square PNG app icon.

Stacks the banner as STEM / CHO / TIC (ANSI Shadow font, matching src/banner.py),
wraps it in a star-ringed circle, and paints it with the app's sunset gradient.
The star ring is generated programmatically so it fits the word widths.

Usage: render_logo.py [out.png] [size]
"""

from PIL import Image, ImageDraw, ImageFont
import os
import sys
import math
import random

# Kanagawa gradient, matching the app's theme (stemchotic.py: set_theme("kanagawa")).
GRADIENT_COLORS = [
    (101, 133, 148),  # Dragon blue
    (126, 156, 216),  # Crystal blue
    (127, 180, 202),  # Spring blue
    (122, 168, 159),  # Wave aqua
    (152, 187, 108),  # Spring green
    (200, 192, 147),  # Old white
    (230, 195, 132),  # Carp yellow
    (255, 160, 102),  # Surimi orange
    (210, 126, 153),  # Sakura pink
    (185, 115, 150),  # Plum
    (149, 127, 184),  # Oni violet
    (165, 150, 200),  # Light violet
]

BG_CENTER = (60, 62, 84)         # brighter kanagawa slate at the center
BG_EDGE = (30, 31, 42)           # darker toward the edges
VIGNETTE = True                  # radial brighten toward the center
RING_BAND = 0.16                 # ring thickness as a fraction of radius
TEXTURE_DENSITY = 0.55           # chance of a texture particle in an interior cell
TEXTURE_OPACITY = (120, 190)

STEM = r"""
███████╗████████╗███████╗███╗   ███╗
██╔════╝╚══██╔══╝██╔════╝████╗ ████║
███████╗   ██║   █████╗  ██╔████╔██║
╚════██║   ██║   ██╔══╝  ██║╚██╔╝██║
███████║   ██║   ███████╗██║ ╚═╝ ██║
╚══════╝   ╚═╝   ╚══════╝╚═╝     ╚═╝
"""
CHO = r"""
 ██████╗██╗  ██╗ ██████╗
██╔════╝██║  ██║██╔═══██╗
██║     ███████║██║   ██║
██║     ██╔══██║██║   ██║
╚██████╗██║  ██║╚██████╔╝
 ╚═════╝╚═╝  ╚═╝ ╚═════╝
"""
TIC = r"""
████████╗██╗ ██████╗
╚══██╔══╝██║██╔════╝
   ██║   ██║██║
   ██║   ██║██║
   ██║   ██║╚██████╗
   ╚═╝   ╚═╝ ╚═════╝
"""

WORDS = [STEM, CHO, TIC]
GAP_ROWS = 1          # blank rows between words
MARGIN_CELLS = 5      # blank cells around the text block, inside the ring
LETTER_Y_NUDGE = 1.3  # push the letters down by this fraction of a cell height
EDGE_CELLS = 0        # outer cells reserved for the ASCII frame (0 = no frame)


def lerp(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def gradient_color(pos):
    pos = max(0.0, min(1.0, pos))
    scaled = pos * (len(GRADIENT_COLORS) - 1)
    idx = int(scaled)
    if idx >= len(GRADIENT_COLORS) - 1:
        return GRADIENT_COLORS[-1]
    return lerp(GRADIENT_COLORS[idx], GRADIENT_COLORS[idx + 1], scaled - idx)


def add_frame(grid, gw, gh):
    """Draw a rounded-corner ASCII box on the outermost ring of cells, so the
    frame follows the macOS squircle mask."""
    cells = set()

    def put(r, c, ch):
        grid[r][c] = ch
        cells.add((r, c))

    put(0, 0, "╭"); put(0, gw - 1, "╮")
    put(gh - 1, 0, "╰"); put(gh - 1, gw - 1, "╯")
    for c in range(1, gw - 1):
        put(0, c, "─"); put(gh - 1, c, "─")
    for r in range(1, gh - 1):
        put(r, 0, "│"); put(r, gw - 1, "│")
    return cells


def build_grid():
    """Compose the character grid: words centered, a star ring, an ASCII frame.

    Returns the grid plus the cell counts and the core (text+margin) cell box
    the star circle is sized to, and the text/frame cell sets so the renderer
    can treat them differently (letters nudge down; frame stays put).
    """
    blocks = []
    for w in WORDS:
        lines = w.strip("\n").split("\n")
        width = max(len(ln) for ln in lines)
        blocks.append([ln.ljust(width) for ln in lines])

    inner_w = max(len(b[0]) for b in blocks)
    text_rows = []
    for i, b in enumerate(blocks):
        if i:
            text_rows += [" " * inner_w] * GAP_ROWS
        for ln in b:
            text_rows.append(ln.center(inner_w))

    text_h = len(text_rows)
    core_w = inner_w + MARGIN_CELLS * 2      # the box the star circle fills
    core_h = text_h + MARGIN_CELLS * 2
    grid_w = core_w + EDGE_CELLS * 2
    grid_h = core_h + EDGE_CELLS * 2
    grid = [[" "] * grid_w for _ in range(grid_h)]

    y0 = (grid_h - text_h) // 2
    x0 = (grid_w - inner_w) // 2
    text_cells = set()
    for r, ln in enumerate(text_rows):
        for c, ch in enumerate(ln):
            if ch != " ":
                grid[y0 + r][x0 + c] = ch
                text_cells.add((y0 + r, x0 + c))

    frame_cells = add_frame(grid, grid_w, grid_h) if EDGE_CELLS else set()
    return grid, grid_w, grid_h, core_w, core_h, text_cells, frame_cells


def render(out_path="stemchotic_logo.png", size=1024):
    font_candidates = [
        ("/System/Library/Fonts/Menlo.ttc", 0),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", 0),
        ("/usr/share/fonts/TTF/DejaVuSansMono.ttf", 0),
    ]

    grid, gw, gh, core_w, core_h, text_cells, frame_cells = build_grid()

    # Cell pixel size: pick a font size so the grid fits `size` with a margin.
    # Char cells are taller than wide; measure with the chosen font.
    # Start from a guess, then scale to fit.
    canvas = Image.new("RGBA", (size, size), BG_EDGE + (255,))
    draw = ImageDraw.Draw(canvas)

    if VIGNETTE:
        # Concentric circles from edge color (large) to center color (small).
        cx0, cy0 = size // 2, size // 2
        steps = 120
        for i in range(steps, 0, -1):
            t = i / steps
            col = lerp(BG_CENTER, BG_EDGE, t)
            rad = int(size / 2 * t * 1.25)
            draw.ellipse((cx0 - rad, cy0 - rad, cx0 + rad, cy0 + rad), fill=col + (255,))

    # Find a font size where the grid fits within ~92% of the canvas.
    target = size * 0.99
    fs = 8
    font = None
    char_w = char_h = 1
    fpath, fidx = next(((p, i) for p, i in font_candidates if os.path.exists(p)), (None, 0))
    while True:
        f = (ImageFont.truetype(fpath, fs, index=fidx) if fpath
             else ImageFont.load_default())
        bbox = f.getbbox("█")
        cw = bbox[2] - bbox[0]
        ch = int((bbox[3] - bbox[1]) * 1.05)
        if cw * gw > target or ch * gh > target or fpath is None:
            break
        font, char_w, char_h = f, cw, ch
        fs += 2
    if font is None:
        font = (ImageFont.truetype(fpath, 8, index=fidx) if fpath
                else ImageFont.load_default())
        bbox = font.getbbox("█")
        char_w = bbox[2] - bbox[0]
        char_h = int((bbox[3] - bbox[1]) * 1.05)

    block_w = char_w * gw
    block_h = char_h * gh
    ox = (size - block_w) // 2
    oy = (size - block_h) // 2

    # Circle geometry: sized to the core (text+margin) box, inside the frame.
    cx = ox + block_w / 2
    cy = oy + block_h / 2
    radius = min(core_w * char_w, core_h * char_h) / 2 * 0.98
    inner_ring = radius * (1 - RING_BAND)

    occupied = text_cells | frame_cells

    random.seed(1305)  # fixed seed -> reproducible

    for r in range(gh):
        for c in range(gw):
            px = ox + c * char_w
            py = oy + r * char_h
            # cell center distance from circle center
            dx = (px + char_w / 2) - cx
            dy = (py + char_h / 2) - cy
            dist = math.hypot(dx, dy)
            pos = (r / gh) * 0.35 + (c / gw) * 0.65
            color = gradient_color(pos)

            ch = grid[r][c]
            if (r, c) in text_cells:
                draw.text((px, py + LETTER_Y_NUDGE * char_h), ch, fill=color + (255,), font=font)
            elif (r, c) in frame_cells:
                draw.text((px, py), ch, fill=color + (255,), font=font)
            elif inner_ring <= dist <= radius:
                draw.text((px, py), "*", fill=color + (255,), font=font)
            elif dist < inner_ring and (r, c) not in occupied and random.random() < TEXTURE_DENSITY:
                tc = random.choice([".", "·", ":", ",", "'"])
                a = random.randint(*TEXTURE_OPACITY)
                draw.text((px, py), tc, fill=color + (a,), font=font)

    canvas.save(out_path)
    print(f"Saved {out_path} ({size}x{size}, grid {gw}x{gh})")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "stemchotic_logo.png"
    sz = int(sys.argv[2]) if len(sys.argv) > 2 else 1024
    render(out, sz)
