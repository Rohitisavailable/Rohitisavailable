#!/usr/bin/env python3
"""ascii-garden — an animated ASCII art GIF that grows with your commits.

The plant's growth stage is derived from the commit count. The stem grows
with the first commits, the main flower opens, and every few commits after
that an extra flower opens on an upper branch. The GIF animates the whole
growth from seed to the current stage, then holds and twinkles.

Usage:
    python grow.py --commits 42 --output garden.gif
    python grow.py --commits 42 --output garden.gif --png-dir frames
"""

from __future__ import annotations

import argparse
import os

from PIL import Image, ImageDraw, ImageFont

# --- palette (GitHub-dark friendly) ---------------------------------------
BG      = "#0d1117"
GREEN   = "#3fb950"
GREEN_D = "#2ea043"
PINK    = "#f778ba"
YELLOW  = "#ffd33d"
GREY    = "#8b949e"
GROUND  = "#30363d"
SOIL    = "#21262d"

# --- scene geometry ---------------------------------------------------------
COLS     = 100
ROWS     = 30
GROUND_Y = 27          # row of the ground surface
CENTER_X = 50          # plant column

MAX_H   = 20           # max stem height (rows)
BUD_H   = 8            # stem height where a bud appears
BLOOM_H = 12           # stem height where the main flower opens

# commit counts at which an extra flower opens on an upper leaf pair
SIDE_FLOWER_STAGES = [20, 24, 28, 32, 36]

# commit counts at which a sparkle appears around the mature plant
SPARKLE_STAGES = [38, 40, 42, 44, 46, 48]
SPARKLE_OFFSETS = [(-2, -5), (-3, 5), (-5, -6), (-6, 4), (-4, 7), (-7, -5)]


def font_path() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(here, "assets", "CascadiaMono.ttf"),
        r"C:\Windows\Fonts\CascadiaMono.ttf",
        r"C:\Windows\Fonts\consola.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    raise SystemExit(
        "No monospace font found. On Linux run: sudo apt-get install fonts-dejavu-core"
    )


def put(cells: dict, r: int, c: int, ch: str, color: str) -> None:
    if 0 <= r < ROWS and 0 <= c < COLS:
        cells[(r, c)] = (ch, color)


def draw_ground(cells: dict) -> None:
    for c in range(COLS):
        put(cells, GROUND_Y, c, "_" if c % 2 == 0 else "/", GROUND)
    for r in (GROUND_Y + 1, GROUND_Y + 2):
        for c in range(COLS):
            if (c * 7 + r * 13) % 11 == 0:
                put(cells, r, c, ".", SOIL)


def draw_sun(cells: dict) -> None:
    r0, c0 = 2, 92
    put(cells, r0,     c0 - 1, "\\", YELLOW)
    put(cells, r0,     c0,     "|", YELLOW)
    put(cells, r0,     c0 + 1, "/", YELLOW)
    put(cells, r0 + 1, c0 - 2, "-", YELLOW)
    put(cells, r0 + 1, c0 - 1, "-", YELLOW)
    put(cells, r0 + 1, c0,     "O", YELLOW)
    put(cells, r0 + 1, c0 + 1, "-", YELLOW)
    put(cells, r0 + 1, c0 + 2, "-", YELLOW)
    put(cells, r0 + 2, c0 - 1, "/", YELLOW)
    put(cells, r0 + 2, c0,     "|", YELLOW)
    put(cells, r0 + 2, c0 + 1, "\\", YELLOW)


def draw_grass(cells: dict) -> None:
    x = 12345
    for c in range(COLS):
        x = (x * 1103515245 + 12345) & 0x7FFFFFFF
        if x % 100 < 11:
            ch = ["'", '"', ',', '.'][x % 4]
            put(cells, GROUND_Y - 1, c, ch, GREEN_D)


def draw_cloud(cells: dict, r0: int, c0: int) -> None:
    for i, line in enumerate([".--.", ".-(    ).", "(__.__.__)"]):
        for j, ch in enumerate(line):
            if ch != " ":
                put(cells, r0 + i, c0 + j, ch, GREY)


def draw_stem(cells: dict, h: int) -> int:
    """Draw the stem and leaf pairs. Returns the row of the stem top."""
    top = GROUND_Y - h
    for r in range(GROUND_Y - 1, top - 1, -1):
        put(cells, r, CENTER_X, "|", GREEN)
    if h < 3:
        # young sprout: two tiny leaves at the very top
        if h >= 1:
            put(cells, top - 1, CENTER_X - 1, "\\", GREEN_D)
            put(cells, top - 1, CENTER_X + 1, "/", GREEN_D)
        return top
    # leaf pairs every 3 rows, 2-cell diagonals
    for L in range(3, max(4, h - 2), 3):
        base_r = GROUND_Y - L
        put(cells, base_r,     CENTER_X - 2, "\\", GREEN_D)
        put(cells, base_r + 1, CENTER_X - 1, "\\", GREEN_D)
        put(cells, base_r,     CENTER_X + 2, "/", GREEN_D)
        put(cells, base_r + 1, CENTER_X + 1, "/", GREEN_D)
    return top


def draw_side_flowers(cells: dict, h: int, stage: int) -> None:
    """Small flowers on the upper leaf pairs, unlocked as commits accumulate."""
    n = sum(1 for t in SIDE_FLOWER_STAGES if stage >= t)
    if n == 0:
        return
    levels = list(range(3, max(4, h - 2), 3))
    for L in levels[-n:]:
        base_r = GROUND_Y - L
        put(cells, base_r - 1, CENTER_X - 2, "o", PINK)
        put(cells, base_r - 1, CENTER_X + 2, "o", PINK)


def draw_sparkles(cells: dict, top: int, stage: int) -> None:
    """Sparkles around the mature plant, unlocked as commits accumulate."""
    n = sum(1 for t in SPARKLE_STAGES if stage >= t)
    for dr, dc in SPARKLE_OFFSETS[:n]:
        put(cells, top + dr, CENTER_X + dc, "*", YELLOW)


def draw_flower(cells: dict, top: int, progress: int, sparkle: bool = False) -> None:
    """progress 0 = bud, 1..3 = opening, 3 + sparkle = full twinkle."""
    if progress <= 0:
        put(cells, top - 1, CENTER_X, "o", PINK)
        return
    put(cells, top - 1, CENTER_X, "O", YELLOW)
    put(cells, top - 2, CENTER_X - 1, "\\", PINK)
    put(cells, top - 2, CENTER_X,     "|", PINK)
    put(cells, top - 2, CENTER_X + 1, "/", PINK)
    put(cells, top,     CENTER_X - 1, "/", PINK)
    put(cells, top,     CENTER_X + 1, "\\", PINK)
    if progress >= 2:
        put(cells, top - 1, CENTER_X - 2, "-", PINK)
        put(cells, top - 1, CENTER_X - 1, "-", PINK)
        put(cells, top - 1, CENTER_X + 1, "-", PINK)
        put(cells, top - 1, CENTER_X + 2, "-", PINK)
    if progress >= 3 and sparkle:
        put(cells, top - 2, CENTER_X - 2, "*", YELLOW)
        put(cells, top - 2, CENTER_X + 2, "*", YELLOW)


def render(stage: int, flower=None, sparkle: bool = False) -> dict:
    cells: dict = {}
    draw_ground(cells)
    draw_grass(cells)
    draw_sun(cells)
    draw_cloud(cells, 3, 10)
    draw_cloud(cells, 6, 68)

    h = min(stage, MAX_H)
    if h == 0:
        put(cells, GROUND_Y - 1, CENTER_X, "o", GREY)
        return cells

    top = draw_stem(cells, h)
    draw_side_flowers(cells, h, stage)
    draw_sparkles(cells, top, stage)

    if flower is None:
        if stage >= BLOOM_H:
            flower = 3
        elif stage >= BUD_H:
            flower = "bud"

    if flower == "bud":
        put(cells, top - 1, CENTER_X, "o", PINK)
    elif flower is not None:
        draw_flower(cells, top, flower, sparkle=sparkle)
    return cells


def to_image(cells: dict, font, cw: float, lh: int) -> Image.Image:
    w = int(round(COLS * cw))
    hgt = int(round(ROWS * lh))
    img = Image.new("RGB", (w, hgt), BG)
    draw = ImageDraw.Draw(img)
    for (r, c), (ch, color) in cells.items():
        draw.text((c * cw, r * lh), ch, font=font, fill=color)
    return img


def build_frames(stage: int, font, cw: float, lh: int) -> list:
    frames = []
    # growth time-lapse: seed -> current stage (capped at full height)
    growth = list(range(0, min(stage, MAX_H) + 1))
    # milestone frames beyond full height so extra details appear gradually
    for t in SIDE_FLOWER_STAGES + SPARKLE_STAGES:
        if stage >= t and t > MAX_H:
            growth.append(t)
    if stage > MAX_H and stage not in growth:
        growth.append(stage)

    for s in growth:
        if s == BLOOM_H:
            # the main flower opens
            for p in (1, 2, 3):
                frames.append(to_image(render(s, flower=p), font, cw, lh))
        else:
            frames.append(to_image(render(s), font, cw, lh))

    # hold with a gentle twinkle
    for i in range(4):
        frames.append(to_image(render(stage, sparkle=(i % 2 == 1)),
                               font, cw, lh))
    return frames


def main() -> None:
    ap = argparse.ArgumentParser(description="Grow an animated ASCII garden GIF.")
    ap.add_argument("--commits", type=int, default=0,
                    help="commit count that drives the growth stage")
    ap.add_argument("--output", default="garden.gif")
    ap.add_argument("--font-size", type=int, default=16)
    ap.add_argument("--fps", type=float, default=12.0)
    ap.add_argument("--png-dir", default=None,
                    help="also dump every frame as PNG into this directory")
    args = ap.parse_args()

    stage = max(0, args.commits)
    font = ImageFont.truetype(font_path(), args.font_size)
    cw = font.getlength("M")
    lh = int(round(args.font_size * 1.2))

    frames = build_frames(stage, font, cw, lh)
    duration = int(round(1000 / args.fps))

    if args.png_dir:
        os.makedirs(args.png_dir, exist_ok=True)
        for i, f in enumerate(frames):
            f.save(os.path.join(args.png_dir, f"frame-{i:03d}.png"))

    frames[0].save(
        args.output,
        save_all=True,
        append_images=frames[1:],
        duration=duration,
        loop=0,
        optimize=True,
    )
    print(f"wrote {args.output}: {len(frames)} frames, "
          f"{frames[0].size[0]}x{frames[0].size[1]} px, {duration} ms/frame")


if __name__ == "__main__":
    main()
