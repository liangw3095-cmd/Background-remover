#!/usr/bin/env python3
"""Make the rounded corners of an exported ID card PNG transparent.

Usage: python3 card_corners.py IN.png OUT.png [--radius-css 44] [--card-width-css 2000]
"""
import sys
import numpy as np
from PIL import Image

args = [a for a in sys.argv[1:] if not a.startswith("--")]
src, dst = args[0], args[1]
r_css = float(sys.argv[sys.argv.index("--radius-css") + 1]) if "--radius-css" in sys.argv else 44.0
w_css = float(sys.argv[sys.argv.index("--card-width-css") + 1]) if "--card-width-css" in sys.argv else 2000.0

im = np.array(Image.open(src).convert("RGBA"))
src_px = im.copy()
H, W = im.shape[:2]
R = r_css * W / w_css
SS = 8
B = int(np.ceil(R)) + 2
for x0, y0, cx, cy in [(0, 0, R, R), (W - B, 0, W - R, R),
                       (0, H - B, R, H - R), (W - B, H - B, W - R, H - R)]:
    ys = (np.arange(B * SS) + 0.5) / SS + y0
    xs = (np.arange(B * SS) + 0.5) / SS + x0
    X, Y = np.meshgrid(xs, ys)
    dx = np.where(((X < cx) & (cx < W / 2)) | ((X > cx) & (cx > W / 2)), X - cx, 0)
    dy = np.where(((Y < cy) & (cy < H / 2)) | ((Y > cy) & (cy > H / 2)), Y - cy, 0)
    cov = ((dx ** 2 + dy ** 2) <= R * R).reshape(B, SS, B, SS).mean((1, 3))
    reg = im[y0:y0 + B, x0:x0 + B]
    # Edge pixels were blended with white: give each the colour 2 px further in
    # along the radius, so a border stroke keeps its own colour round the curve.
    part = (cov > 0) & (cov < 1)
    py, px = np.nonzero(part)
    gx, gy = x0 + px + 0.5, y0 + py + 0.5
    n = np.maximum(np.hypot(cx - gx, cy - gy), 1e-6)
    sx = np.clip(gx + 2 * (cx - gx) / n, 0, W - 1).astype(int)
    sy = np.clip(gy + 2 * (cy - gy) / n, 0, H - 1).astype(int)
    reg[py, px, :3] = src_px[sy, sx, :3]
    reg[..., 3] = np.minimum(reg[..., 3], np.round(cov * 255)).astype(np.uint8)
    im[y0:y0 + B, x0:x0 + B] = reg
Image.fromarray(im, "RGBA").save(dst)
print(f"radius {R:.1f}px, saved {dst}")
