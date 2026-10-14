#!/usr/bin/env python3
"""Recolour a two-tone (lit + shadow) garment part to a cover's lit and shadow colours.

Usage: python3 recolor_shaded.py CUTOUT.png OUT.png --light R,G,B --shadow R,G,B
           --to-light R,G,B --to-shadow R,G,B [--min 1500] [--touch R,G,B] [--skip "x,y;x,y"]

--light/--shadow are the part's lit and shadow tones on the sprite, --to-* the cover's.
Seeds are areas of the lit tone (at least --min px, not ringed by skin); the part is every
pixel of the same hue family connected to a seed, so its shadows and fold lines move with it.
Brightness picks the blend between the cover's shadow and lit tones. Written for Tamsin Lau's
pink cuffs (lit 210,141,145, shadow 144,79,88 -> cover tan 196,161,139 / 140,103,90, --touch 97,68,113).
"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default


def rgb_arg(name):
    return np.array([float(v) for v in arg(name).split(",")])


src, dst = sys.argv[1:3]
L, Sh = rgb_arg("--light"), rgb_arg("--shadow")
TL, TS = rgb_arg("--to-light"), rgb_arg("--to-shadow")
min_px = int(arg("--min", 1500))

O = np.asarray(Image.open(src)).astype(np.float32)
rgb, a = O[..., :3], O[..., 3]
mx = rgb.max(-1)
sat = (mx - rgb.min(-1)) / np.maximum(mx, 1)
chroma = rgb / np.maximum(mx, 1)[..., None]

# Seeds: the lit tone, in areas big enough and not surrounded by skin.
seed = (np.linalg.norm(chroma - L / L.max(), axis=-1) < 0.08) & (mx > 0.75 * L.max()) & (a > 200)
lab, n = ndi.label(ndi.binary_closing(seed, iterations=2))
skin = (mx > 200) & (sat < 0.2) & (a > 200)
# --touch R,G,B: the part must sit on a garment of this colour (cuffs on the sleeve), which
# keeps skin shadows of the same pink (neck, jaw) out.
touch = None
if "--touch" in sys.argv:
    K = rgb_arg("--touch")
    touch = np.linalg.norm(chroma - K / K.max(), axis=-1) < 0.25
keep = np.zeros(n + 1, bool)
for i in range(1, n + 1):
    m = lab == i
    if (seed & m).sum() < min_px:
        continue
    ring = ndi.binary_dilation(m, iterations=6) & ~m & (a > 200)
    keep[i] = ring.any() and skin[ring].mean() <= 0.6
seed &= keep[lab]

# The part: same hue family (red channel highest, blue not below green), connected to a seed.
family = (rgb[..., 0] >= mx - 1) & (rgb[..., 2] >= rgb[..., 1] - 8) & (sat > 0.2) & (a > 0)
lab, n = ndi.label(family)
ids = [i for i in np.unique(lab[seed]) if i > 0]
if touch is not None:
    def on_garment(i):
        m = lab == i
        ring = ndi.binary_dilation(m, iterations=6) & ~m & (a > 200)
        return ring.any() and touch[ring].mean() >= 0.08
    ids = [i for i in ids if on_garment(i)]
# --skip "x,y;x,y": leave the parts under these points alone (a skin shadow of the same
# pink that also touches the garment, e.g. the neck between the collar).
if "--skip" in sys.argv:
    pts = [tuple(int(v) for v in p.split(",")) for p in arg("--skip").split(";")]
    ids = [i for i in ids if i not in {int(lab[y, x]) for x, y in pts}]
part = np.isin(lab, ids) & (lab > 0)

vL, vS = L.max(), Sh.max()
t = np.clip((mx - vS) / (vL - vS), 0, 1)[..., None]
col = TS + t * (TL - TS)
col = np.where((mx < vS)[..., None], TS * (mx / vS)[..., None], col)          # fold lines
col = np.where((mx > vL)[..., None], TL + (mx - vL)[..., None] / max(255 - vL, 1) * (255 - TL), col)
out = rgb.copy()
out[part] = col[part]
Image.fromarray(np.dstack([np.clip(out, 0, 255), a]).round().astype(np.uint8), "RGBA").save(dst)
print(f"{dst.split('/')[-1]:34s} recoloured {int(part.sum()):6d} px")
