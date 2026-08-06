#!/usr/bin/env python3
"""Prepare a photo for ASCII conversion.

A flatly-lit photo converts to a dark, unreadable blob, so this script does
three things before make_ascii_svg.py ever sees it:

  1. isolate the subject (rembg if installed, luminance keying otherwise)
  2. boost local contrast with CLAHE so a flat face gets real highs and lows
  3. composite onto pure white, so the background maps to the blank end of
     the ASCII ramp and prints as nothing

Run it once per photo:

    python scripts/prep_photo.py source-photo.jpg

Output: source-prepped.png (grayscale, ready for make_ascii_svg.py)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "source-prepped.png"

# Work at a generous resolution; the ASCII grid downsamples hard anyway, and
# extra pixels per character cell mean a better-averaged glyph choice.
WORK_SIZE = 1000


# --------------------------------------------------------------------------
# contrast
# --------------------------------------------------------------------------
def clahe_numpy(gray: np.ndarray, tiles: tuple[int, int] = (8, 8),
                clip_limit: float = 3.0) -> np.ndarray:
    """Contrast-limited adaptive histogram equalization, NumPy only.

    Mirrors cv2.createCLAHE: per-tile clipped-histogram equalization with
    bilinear interpolation between tile centres so no tile seams show.
    """
    h, w = gray.shape
    ty, tx = tiles
    th, tw = h / ty, w / tx

    luts = np.zeros((ty, tx, 256), dtype=np.uint8)
    for i in range(ty):
        y0, y1 = int(round(i * th)), int(round((i + 1) * th))
        for j in range(tx):
            x0, x1 = int(round(j * tw)), int(round((j + 1) * tw))
            tile = gray[y0:y1, x0:x1]
            if tile.size == 0:
                luts[i, j] = np.arange(256, dtype=np.uint8)
                continue
            hist = np.bincount(tile.ravel(), minlength=256).astype(np.float64)
            # Clip the peaks and redistribute the clipped mass uniformly.
            limit = max(1.0, clip_limit * tile.size / 256.0)
            excess = np.maximum(hist - limit, 0.0).sum()
            hist = np.minimum(hist, limit) + excess / 256.0
            cdf = np.cumsum(hist)
            span = max(cdf[-1] - cdf[0], 1e-9)
            luts[i, j] = np.clip((cdf - cdf[0]) / span * 255.0, 0, 255).astype(np.uint8)

    # Bilinear blend of the four nearest tile LUTs for every pixel.
    fy = (np.arange(h) + 0.5) / th - 0.5
    fx = (np.arange(w) + 0.5) / tw - 0.5
    i0 = np.clip(np.floor(fy).astype(int), 0, ty - 1)
    j0 = np.clip(np.floor(fx).astype(int), 0, tx - 1)
    i1 = np.clip(i0 + 1, 0, ty - 1)
    j1 = np.clip(j0 + 1, 0, tx - 1)
    wy = np.clip(fy - np.floor(fy), 0, 1).astype(np.float32)[:, None]
    wx = np.clip(fx - np.floor(fx), 0, 1).astype(np.float32)[None, :]

    def lut_at(ii, jj):
        return luts[ii[:, None], jj[None, :], gray].astype(np.float32)

    top = lut_at(i0, j0) * (1 - wx) + lut_at(i0, j1) * wx
    bot = lut_at(i1, j0) * (1 - wx) + lut_at(i1, j1) * wx
    return np.clip(top * (1 - wy) + bot * wy, 0, 255).astype(np.uint8)


def apply_clahe(gray: np.ndarray, clip_limit: float) -> np.ndarray:
    """Use OpenCV's CLAHE when available, otherwise the NumPy one above."""
    try:
        import cv2  # noqa: PLC0415
    except ImportError:
        return clahe_numpy(gray, clip_limit=clip_limit)
    op = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=(8, 8))
    return op.apply(gray)


# --------------------------------------------------------------------------
# subject isolation
# --------------------------------------------------------------------------
def cutout_rembg(img: Image.Image) -> Image.Image | None:
    """Background removal via rembg. Returns None when rembg isn't installed."""
    try:
        from rembg import remove  # noqa: PLC0415
    except ImportError:
        return None
    print("  subject     : rembg cutout")
    return remove(img.convert("RGBA"))


def looks_inverted(gray: np.ndarray) -> bool:
    """True when the subject is bright on a dark background.

    The ASCII ramp runs bright -> sparse, so a dark background would print as
    a solid slab of '@'. Sampling the border tells us which way round we are.
    """
    border = np.concatenate([
        gray[:6, :].ravel(), gray[-6:, :].ravel(),
        gray[:, :6].ravel(), gray[:, -6:].ravel(),
    ])
    return float(np.median(border)) < float(np.median(gray))


def key_out_background(gray: np.ndarray, strength: float) -> np.ndarray:
    """Push the brightest band all the way to white.

    Cheap stand-in for a real matte: everything above the knee ramps to 255,
    so a light background collapses to spaces instead of stippling the frame
    with faint punctuation.
    """
    if strength <= 0:
        return gray
    knee = np.percentile(gray, 100.0 - strength)
    if knee >= 254:
        return gray
    out = gray.astype(np.float32)
    ramp = np.clip((out - knee) / max(255.0 - knee, 1e-6), 0, 1)
    return np.clip(out + ramp * (255.0 - out), 0, 255).astype(np.uint8)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("photo", help="source image (jpg/png)")
    ap.add_argument("-o", "--out", default=str(DEFAULT_OUT),
                    help="output path (default: source-prepped.png)")
    ap.add_argument("--clip", type=float, default=3.0,
                    help="CLAHE clip limit; higher = punchier (default: 3.0)")
    ap.add_argument("--bg", type=float, default=18.0,
                    help="percent of brightest pixels driven to pure white "
                         "(default: 18, use 0 to disable)")
    ap.add_argument("--gamma", type=float, default=1.0,
                    help="<1 lightens midtones, >1 darkens them (default: 1.0)")
    ap.add_argument("--invert", choices=["auto", "yes", "no"], default="auto",
                    help="flip a bright-subject-on-dark-background image "
                         "(default: auto-detect from the border)")
    ap.add_argument("--no-rembg", action="store_true",
                    help="skip rembg even when it is installed")
    args = ap.parse_args()

    src = Path(args.photo)
    if not src.exists():
        print(f"error: no such file: {src}", file=sys.stderr)
        return 1

    print(f"prep_photo: {src.name}")
    img = Image.open(src)
    img = ImageOps.exif_transpose(img)

    # 1. isolate the subject and flatten onto white
    cut = None if args.no_rembg else cutout_rembg(img)
    if cut is not None:
        canvas = Image.new("RGBA", cut.size, (255, 255, 255, 255))
        canvas.alpha_composite(cut)
        img = canvas.convert("RGB")
    else:
        if not args.no_rembg:
            print("  subject     : rembg not installed, using luminance keying")
        img = img.convert("RGB")

    img.thumbnail((WORK_SIZE, WORK_SIZE), Image.LANCZOS)
    gray = np.asarray(ImageOps.grayscale(img), dtype=np.uint8)

    # 2. orient so the subject is the DARK end of the ramp
    invert = looks_inverted(gray) if args.invert == "auto" else args.invert == "yes"
    if invert:
        print("  polarity    : inverted (bright subject on dark background)")
        gray = 255 - gray

    # 3. local contrast, then flatten the background to white
    gray = apply_clahe(gray, args.clip)
    print(f"  contrast    : CLAHE clip={args.clip}")

    if args.gamma != 1.0:
        norm = (gray.astype(np.float32) / 255.0) ** args.gamma
        gray = np.clip(norm * 255.0, 0, 255).astype(np.uint8)

    if cut is None:
        gray = key_out_background(gray, args.bg)
        print(f"  background  : top {args.bg:g}% driven to white")

    out_img = Image.fromarray(gray, mode="L")
    # A touch of sharpening keeps edges from smearing across character cells.
    out_img = out_img.filter(ImageFilter.UnsharpMask(radius=2, percent=90, threshold=3))
    out_img = ImageOps.autocontrast(out_img, cutoff=1)

    dest = Path(args.out)
    dest.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(dest)
    print(f"  wrote       : {dest.name}  ({out_img.width}x{out_img.height})")
    print("  next        : python scripts/make_ascii_svg.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
