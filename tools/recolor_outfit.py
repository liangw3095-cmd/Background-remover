#!/usr/bin/env python3
"""Recolour one colour of an outfit on a cutout (e.g. to match a cover), keeping its shading.

Usage: python3 recolor_outfit.py CUTOUT.png OUT.png --from R,G,B --to R,G,B
           [--tol 0.15] [--min 3000] [--not-skin]

--from  the garment's base colour on the sprite (sample its median); --to  the cover's.
Pixels whose chroma (rgb / max) is within --tol of --from's, in areas of at least --min px,
are mapped to --to scaled by their brightness, so folds, shadows and patterns (plaid) carry
over. Near-black outline pixels next to the garment follow. --not-skin drops areas that are
mostly surrounded by light skin (for a pink close to skin shadow, e.g. rolled-up cuffs).
"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


src, dst = sys.argv[1:3]
F = np.array([float(v) for v in arg("--from").split(",")])
T = np.array([float(v) for v in arg("--to").split(",")])
tol, min_px = float(arg("--tol", 0.15)), int(arg("--min", 3000))

O = np.asarray(Image.open(src)).astype(np.float32)
rgb, a = O[..., :3], O[..., 3]
mx = rgb.max(-1)
chroma = rgb / np.maximum(mx, 1)[..., None]
d = np.linalg.norm(chroma - F / F.max(), axis=-1)
vb = F.max()

core = (d < tol) & (mx > 0.35 * vb) & (a > 200)
lab, n = ndi.label(ndi.binary_closing(core, iterations=2))
keep = np.zeros(n + 1, bool)
if n:
    keep[1:] = ndi.sum(core, lab, range(1, n + 1)) >= min_px
if n and "--not-skin" in sys.argv:
    s = (mx - rgb.min(-1)) / np.maximum(mx, 1)
    light = (mx > 200) & (s < 0.2) & (a > 200)
    for i in np.where(keep)[0]:
        m = lab == i
        ring = ndi.binary_dilation(m, iterations=4) & ~m & (a > 200)
        if ring.any() and light[ring].mean() > 0.6:
            keep[i] = False
core &= keep[lab]

# Anti-aliased edges and the garment's own dark outline/stitching nearby.
near = ndi.binary_dilation(core, iterations=5)
dark = (mx < 0.45 * vb) & (d < 2.5 * tol)
soft = near & ((d < 2 * tol) | dark) & (a > 0) & ~core

new = np.clip(T * (mx / vb)[..., None], 0, 255)
w = np.clip(1 - (d - tol) / tol, 0, 1)[..., None]
w = np.where(dark[..., None], 1.0, w)
out = rgb.copy()
out[soft] = (w * new + (1 - w) * rgb)[soft]
out[core] = new[core]
Image.fromarray(np.dstack([out, a]).round().astype(np.uint8), "RGBA").save(dst)
print(f"{dst.split('/')[-1]:34s} recoloured {int(core.sum() + soft.sum()):7d} px")
