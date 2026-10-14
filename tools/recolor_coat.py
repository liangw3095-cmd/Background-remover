"""Recolour a red/crimson coat on a cutout to a target colour (e.g. from a cover), keeping its shading.

Usage: python3 recolor_coat.py CUTOUT.png OUT.png R,G,B
The coat is the large crimson area (blue above green, which leaves brown hair alone), plus its
near-black maroon outline and buttons. Mouths and blush are too small or too light to be picked up.
"""
from PIL import Image
from scipy import ndimage as ndi
src, dst = sys.argv[1:3]
T = np.array([float(v) for v in sys.argv[3].split(",")])
O = np.asarray(Image.open(src)).astype(np.float32)
rgb, a = O[..., :3], O[..., 3]
mx, mn = rgb.max(-1), rgb.min(-1)
s = (mx - mn) / np.maximum(mx, 1)
red = (rgb[..., 0] >= mx - 1) & (rgb[..., 2] > rgb[..., 1] + 5)        # crimson, not the brown hair
maroon = (mx < 70) & (rgb[..., 0] >= mx - 1) & (rgb[..., 1] < 0.3 * rgb[..., 0]) & (rgb[..., 2] >= rgb[..., 1] - 3)  # near-black outline/buttons
core = red & (s > 0.55) & (mx > 40) & (mx < 190) & (a > 200)
lab, n = ndi.label(ndi.binary_closing(core, iterations=2))
sz = ndi.sum(core, lab, range(1, n + 1))
core &= np.isin(lab, np.where(sz >= 3000)[0] + 1)                       # the coat, not mouths
soft = ndi.binary_dilation(core, iterations=6) & (red | maroon) & (s > 0.2) & (a > 0)   # outlines, buttons
vb = float(np.median(mx[core]))
f = (mx / vb)[..., None]
new = np.clip(T * f, 0, 255)
w = np.clip((s - 0.2) / 0.3, 0, 1)[..., None]                          # fade at anti-aliased edges
out = rgb.copy()
out[soft] = (w * new + (1 - w) * rgb)[soft]
out[core] = new[core]
Image.fromarray(np.dstack([out, a]).round().astype(np.uint8), "RGBA").save(dst)
print(dst.split("/")[-1], "coat px", int(soft.sum()), "src base v", round(vb))
