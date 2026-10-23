"""Turn owner-supplied player cards into site portraits (same look as the Falcons set).

    python scripts/make_portraits.py SRC_DIR --map name=steamid [name=steamid ...] [--out web/public/players]

SRC_DIR holds one image per player named <name>.png|jpg (e.g. HLTV-style player cards).
Each card is cleaned (left badge column and light tooltip boxes removed), upscaled 2x,
cut out with rembg (isnet-general-use), then placed on a 1000x666 transparent canvas:
head ~215 px wide, hair top at y=100, centred, with a soft fade at the bottom.
Requires: pip install "rembg[cpu]" opencv-python pillow numpy.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

W, H = 1000, 666
HAIR_TOP = 100
HEAD_W = 215            # head width in px, matched to the Falcons set
FADE_FROM = 560          # alpha fades from here to the bottom edge
LEFT_BADGES = 0.22       # share of the card width taken by the flag / role / logo column


def clean_card(img: Image.Image) -> Image.Image:
    rgb = np.array(img.convert("RGB"))
    h, w = rgb.shape[:2]
    rgb = rgb[:, int(w * LEFT_BADGES):]
    # light-grey tooltip boxes (e.g. "Winner of …"): inpaint the whole box rectangle
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    box = ((hsv[..., 2] > 190) & (hsv[..., 1] < 30)).astype(np.uint8)
    box = cv2.morphologyEx(box, cv2.MORPH_CLOSE, np.ones((7, 25), np.uint8))
    n, _, stats, _ = cv2.connectedComponentsWithStats(box)
    mask = np.zeros(box.shape, np.uint8)
    for x, y, bw, bh, area in stats[1:]:
        if bw > 0.25 * rgb.shape[1] and 12 < bh < 0.12 * h and area > 0.5 * bw * bh:
            mask[max(0, y - 4):y + bh + 4, max(0, x - 4):x + bw + 6] = 255
    if mask.any():
        rgb = cv2.inpaint(rgb, mask, 9, cv2.INPAINT_TELEA)
    out = Image.fromarray(rgb)
    out = out.resize((out.width * 2, out.height * 2), Image.LANCZOS)
    return out.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))


def cutout(img: Image.Image, session) -> Image.Image:
    from rembg import remove
    return remove(img, session=session, post_process_mask=True)


def head_width(a: np.ndarray) -> tuple[int, float, float]:
    """(hair-top row, head width, head centre x) from a cut-out alpha mask."""
    rows = np.where(a.any(1))[0]
    top = rows[0]
    widths, centres = [], []
    for y in range(top, rows[-1] + 1):
        xs = np.where(a[y])[0]
        widths.append(xs[-1] - xs[0] + 1 if len(xs) else 0)
        centres.append((xs[0] + xs[-1]) / 2 if len(xs) else 0)
    widths = np.array(widths, float)
    # head = widest row above the neck; the body below the neck reaches ~2x the head width
    body = int(np.argmax(widths > 0.8 * widths.max()))
    start = max(1, body // 5)                      # skip the narrow crown of the hair
    neck_i = start + int(np.argmin(widths[start:body]))
    head_i = int(np.argmax(widths[:neck_i]))
    best = float(widths[head_i])
    cx = centres[head_i]
    return int(top), best, float(cx)


def place(cut: Image.Image) -> Image.Image:
    a = np.array(cut.split()[-1]) > 128
    top, hw, cx = head_width(a)
    s = HEAD_W / hw
    cut = cut.resize((round(cut.width * s), round(cut.height * s)), Image.LANCZOS)
    canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(cut, (round(W / 2 - cx * s), round(HAIR_TOP - top * s)))
    alpha = np.array(canvas.split()[-1]).astype(np.float32)
    ramp = np.clip((H - np.arange(H)) / (H - FADE_FROM), 0, 1)[:, None]
    alpha *= ramp
    canvas.putalpha(Image.fromarray(alpha.astype(np.uint8)))
    return canvas


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("src", type=Path)
    ap.add_argument("--map", nargs="+", required=True, help="name=steamid")
    ap.add_argument("--out", type=Path, default=Path("web/public/players"))
    args = ap.parse_args()
    from rembg import new_session
    session = new_session("isnet-general-use")
    args.out.mkdir(parents=True, exist_ok=True)
    for pair in args.map:
        name, sid = pair.split("=")
        src = next((p for p in args.src.iterdir() if p.stem.lower() == name.lower()), None)
        if src is None:
            print(f"missing card for {name}")
            continue
        out = place(cutout(clean_card(Image.open(src)), session))
        out.save(args.out / f"{sid}.png", optimize=True)
        print(f"{name} → {args.out / f'{sid}.png'}")


if __name__ == "__main__":
    main()
