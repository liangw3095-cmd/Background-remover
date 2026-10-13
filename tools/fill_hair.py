#!/usr/bin/env python3
"""Recolour hair the generator drew in the background colour (inner and back hair).

Fills every bg-tinted area inside the hair in the top 35% of the image that is
not open to the outer background, with the hair's own shading (pure bg colour
becomes the hair's shadow tone, fading to white). Only for a mint (cyan-ish)
background, where red is the suppressed channel. Run it on a cutout.py output.

Usage: python3 fill_hair.py SRC_IMAGE CUTOUT_PNG OUT_PNG [--gap-seeds "x,y;x,y"]
  --gap-seeds  keep the enclosed areas containing these points clear (real
               background seen through a gap), walled off by the hair outlines.
"""
import sys
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

src, cut, dst = sys.argv[1:4]
C = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)
O = np.asarray(Image.open(cut)).astype(np.float32).copy()
H, W, _ = C.shape
B = np.median(np.concatenate([C[:200, :120].reshape(-1, 3), C[:200, -120:].reshape(-1, 3)]), axis=0)
lum = np.array([0.299, 0.587, 0.114], np.float32)
Y, YB = C @ lum, float(B @ lum)
dist = np.linalg.norm(C - B, axis=-1)
tint = np.minimum(C[..., 1], C[..., 2]) - C[..., 0]          # mint key: red is the suppressed channel
ratio = tint / (min(B[1], B[2]) - B[0])

lab, _ = ndi.label(dist < 12)                                 # the real background, flooded from the edges
outside = np.isin(lab, np.unique(np.concatenate([lab[0], lab[:, 0], lab[:, -1]]))) & (lab > 0)
near_out = ndi.binary_dilation(outside, iterations=5)
head = np.zeros((H, W), bool)
head[: int(0.35 * H)] = True

# Tinted hair, not plain bg: enclosed gaps of pure bg (behind the neck) stay clear.
cand = head & (ratio > 0.12) & ~near_out
keep_clear = np.zeros((H, W), bool)
lab, n = ndi.label(cand)
sizes = ndi.sum(cand, lab, range(1, n + 1)) if n else np.array([])
core = np.isin(lab, np.where(sizes >= 150)[0] + 1)
holes = ndi.binary_fill_holes(core) & ~core                    # small bg specks inside the hair
lab, n = ndi.label(holes)
if n:
    hs = ndi.sum(holes, lab, range(1, n + 1))
    core |= np.isin(lab, np.where(hs < 300)[0] + 1)
if "--gap-seeds" in sys.argv:
    # Bg gaps enclosed by hair tips and clothes: remove the areas, walled off by
    # the hair's teal and dark outlines, that contain the given points.
    seeds = [tuple(int(v) for v in p.split(",")) for p in sys.argv[sys.argv.index("--gap-seeds") + 1].split(";")]
    teal = (C[..., 1] - C[..., 0] > 40) & (Y < 170) & (dist > 40)
    walls = ndi.binary_dilation(teal | (Y < 110), iterations=1)
    lab, n = ndi.label(core & ~walls)
    ids = {int(lab[y, x]) for x, y in seeds if lab[y, x] > 0}
    gap = np.isin(lab, list(ids))
    print("gap areas", {i: int((lab == i).sum()) for i in ids}, "of core", int(core.sum()))
    keep_clear = ndi.binary_dilation(gap, iterations=3)   # leave the gap's own edges to the cutout
    core &= ~keep_clear
region = ndi.binary_dilation(core, iterations=2) & head & ~near_out

# The hair's own shading: untinted, light-to-mid pixels of the hair near the patches.
near = ndi.binary_dilation(core, iterations=25) & ~near_out & ~core
shade = near & (np.abs(ratio) < 0.05) & (Y > 170) & (Y < 245)
hue = np.median(C[shade] / Y[shade][:, None], axis=0)
shadeY = float(np.median(Y[shade]))

# Map brightness: pure bg tint -> hair shade, white -> white, darker lines scale down.
Yn = np.where(Y >= YB, shadeY + (Y - YB) / max(255 - YB, 1) * (255 - shadeY), shadeY * Y / max(YB, 1))
mapped = np.clip(Yn[..., None] * hue, 0, 255)
s = np.clip((ratio - 0.08) / 0.15, 0, 1)[..., None]
colour = s * mapped + (1 - s) * C

# Where the inner hair just fades into the bg there is no outline: smooth the
# fill's shape and feather its edge by ~1-2 px instead of a pixel staircase.
smooth = ndi.gaussian_filter(region.astype(np.float32), 2.0) > 0.5
smooth &= head & ~outside & ~keep_clear
a_fill = ndi.gaussian_filter(smooth.astype(np.float32), 1.0) * head
inside = smooth & (a_fill > 0.98)
O[inside, :3] = colour[inside]
O[inside, 3] = 255
rim = (a_fill > 0.02) & ~inside & ~keep_clear
raise_ = rim & (O[..., 3] < a_fill * 255)
O[raise_, :3] = mapped[raise_]
O[raise_, 3] = a_fill[raise_] * 255
region = inside | raise_
Image.fromarray(O.round().astype(np.uint8), "RGBA").save(dst)
print(f"{dst.split('/')[-1]:32s} filled {int(region.sum()):5d} px  hair shade {np.round(shadeY * hue).astype(int).tolist()}")
