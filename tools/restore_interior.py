#!/usr/bin/env python3
"""Undo the key's damage inside a character: restore source pixels the cutout changed
that sit well away from any real background (pink/red key: skin under lace, open mouths,
lavender shading on white cloth).

Usage: python3 restore_interior.py SRC_IMAGE CUTOUT_PNG OUT_PNG ["x0,y0,x1,y1;..."]
Background = every flat bg-coloured area of 300+ px (enclosed pockets included); only
pixels more than 6 px from it, and 5+ px from any bg-hue pixel, are restored. The optional
boxes are left alone: glowing effects that show the bg through (Mele Kealoha's water orb)
and hair strands over bg beside the neck (they come back as red streaks).
"""
import sys, numpy as np
from PIL import Image
from scipy import ndimage as ndi
src, cut, dst = sys.argv[1:4]
C = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)
O = np.asarray(Image.open(cut)).astype(np.float32).copy()
B = np.median(np.concatenate([C[:200, :120].reshape(-1, 3), C[:200, -120:].reshape(-1, 3)]), axis=0)
dist = np.linalg.norm(C - B, axis=-1)
lab, n = ndi.label(dist < 45)
sz = ndi.sum(np.ones_like(dist), lab, range(1, n + 1))
bg = np.isin(lab, np.where(sz >= 300)[0] + 1)
far = ndi.distance_transform_edt(~bg) > 6
changed = (O[..., 3] < 250) | (np.abs(O[..., :3] - C).max(-1) > 30)
R, G, Bc = C[..., 0], C[..., 1], C[..., 2]
bglike = (G < 0.15 * R) & (Bc > 0.3 * R) & (R > 50)
m = far & changed & ~ndi.binary_dilation(bglike, iterations=5) & ndi.binary_dilation(O[..., 3] > 0, iterations=2)
lab, n = ndi.label(ndi.binary_closing(m, iterations=2))
for i in range(1, n + 1):
    ys, xs = np.where(lab == i)
    if len(ys) > 80: print(f"  {len(ys):6d}px x{xs.min()}-{xs.max()} y{ys.min()}-{ys.max()}")
if len(sys.argv) > 4:
    for b in sys.argv[4].split(";"):
        x0, y0, x1, y1 = map(int, b.split(",")); m[y0:y1, x0:x1] = False
O[m, :3] = C[m]; O[m, 3] = 255
Image.fromarray(O.round().astype(np.uint8), "RGBA").save(dst)
