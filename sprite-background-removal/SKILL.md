---
name: "sprite-background-removal"
description: "Cut flat-colour backgrounds out of character sprite sets and deliver them named 'FullName, Expression' in emotion order; also makes ID card export corners transparent."
---

# Sprite background removal

Use this whenever Kom sends a batch of character sprite renders (Civitai / Illustrious, flat green or other single-colour background) and asks for the background removed, or sends an exported ID card PNG whose rounded corners came out white.

The script below is tested: it handles vivid AND pale backgrounds, clean anti-aliased line-art edges, thin hair strands, gaps between hair and neck, the pale rim generators leave along the image border (e.g. where a blazer touches the right edge), and soft effects like sigh puffs. Do not rewrite it from scratch; write it out and run it.

## Workflow (sprites)

1. **Match images to expressions** by looking at them (they often arrive out of order). The standard order is: Neutral, Happy, Playful, Tired, Sad, Wary, Angry, Shocked, Embarrassed, Strained.
2. **Copy** each image into a fresh folder as `in/<Expression>.png` (e.g. `in/Neutral.png`). Work on copies, never the uploads.
3. **Write `cutout.py`** (below) into the scratch/working folder and run (needs numpy, Pillow and scipy; `pip install scipy` if the import fails):
   ```
   python3 cutout.py "Full Name" in out --despill-all --sheet sheet.png
   ```
   Use `--despill-all` unless the character has clothing/eyes/hair in the background's hue (the background is normally chosen to contrast, so this is usually safe). It removes any background-colour tint left on the character. Bg-hued parts also go see-through without the flag (see **Background choice**).
4. **One check, not a rebuild:** open `sheet.png` (alternating dark/light backdrops). If something looks off, zoom only that spot (crop + NEAREST upscale over a dark backdrop). Common places: outer hair edge, the image border where clothes touch the frame, effect elements.
5. **Do not post-fix the art** (pupils, pendants, small drawing details). Kom has asked for background removal and naming only.
6. **Send** the files in the standard order with SendUserFile (display: attach), named exactly `Full Name, Expression.png`. Give a one or two line summary; mention any problem in the source image only if it affects the cutout.

If a background came out pale instead of vivid, it still works, but suggest `(vivid green background:1.5)` for the next character.

**Background choice.** Anything on the character close to the background's hue (green eyes or a green ribbon on green; a navy blazer on blue) comes out see-through and greyed, with or without `--despill-all`. For such a character, suggest a contrasting key instead, e.g. `(vivid magenta background:1.5)` for green eyes (not for pink or purple hair). Avoid white or grey backgrounds: white clothes and white effects vanish into them.

## cutout.py

```python
#!/usr/bin/env python3
"""Sprite background remover for flat, single-colour backgrounds (vivid or pale).

Usage:
  python3 cutout.py "Full Name" IN_DIR OUT_DIR [--despill-all] [--sheet SHEET.png]

IN_DIR holds one image per expression, named <Expression>.png (Neutral.png, Happy.png, ...);
.jpg/.jpeg/.webp are accepted too.
Writes OUT_DIR/"Full Name, Expression.png" (transparent RGBA) for each, in ORDER,
then any extra PNGs in IN_DIR alphabetically. --sheet also writes a check sheet.
"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

ORDER = ["Neutral", "Happy", "Playful", "Tired", "Sad", "Wary",
         "Angry", "Shocked", "Embarrassed", "Strained"]


def cut(path, despill_all=False, bg_thr=10.0):
    C = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    H, W, _ = C.shape
    # Background colour from the top corners (sprites never reach them).
    B = np.median(np.concatenate([C[:200, :120].reshape(-1, 3),
                                  C[:200, -120:].reshape(-1, 3)]), axis=0)
    dist = np.linalg.norm(C - B, axis=-1)

    # Background hue signature. One dominant channel (green/blue/red key):
    #   tint = that channel minus the larger other one.
    # One suppressed channel (magenta/yellow/cyan key):
    #   tint = the smaller other channel minus that channel.
    order = np.argsort(B)                 # low, mid, high
    lo, mid, hi = order
    dominant = (B[hi] - B[mid]) >= (B[mid] - B[lo])
    if dominant:
        k, others = hi, [lo, mid]
        tint_of = lambda X: X[..., k] - np.maximum(X[..., others[0]], X[..., others[1]])
    else:
        k, others = lo, [mid, hi]
        tint_of = lambda X: np.minimum(X[..., others[0]], X[..., others[1]]) - X[..., k]
    tB = float(tint_of(B[None, :])[0])
    tint = tint_of(C)

    nonbg = dist > bg_thr
    lab, n = ndi.label(nonbg)                      # drop tiny foreground specks
    if n:
        sizes = ndi.sum(np.ones_like(dist), lab, range(1, n + 1))
        nonbg &= ~np.isin(lab, np.where(sizes < 40)[0] + 1)
    lab, n = ndi.label(~nonbg)                     # fill tiny background pinholes
    if n:
        sizes = ndi.sum(np.ones_like(dist), lab, range(1, n + 1))
        nonbg |= np.isin(lab, np.where(sizes < 15)[0] + 1)

    # Only the outer ~2 px are anti-aliased; the image border counts as an edge.
    edt_in = ndi.distance_transform_edt(np.pad(nonbg, 1, constant_values=False))[1:-1, 1:-1]
    solid = nonbg & (edt_in > 2.0)
    edge = nonbg & ~solid

    _, (iy, ix) = ndi.distance_transform_edt(~solid, return_indices=True)

    # Alpha relative to the strongest nearby stroke (the line art).
    localmax = ndi.maximum_filter(np.where(nonbg, dist, 0.0), size=7)
    A = np.zeros((H, W), np.float32)
    A[solid] = 1.0
    A[edge] = np.clip(dist / np.maximum(localmax, 20.0), 0.0, 1.0)[edge]

    # Pixels tinted toward the bg hue are mostly background: cap their alpha.
    if tB > 8:
        raw = np.clip(1.0 - tint / tB, 0.0, 1.0)
        a_t = ndi.median_filter(raw, size=5)
        # The median misses bg slivers 1-2 px wide (between hair strands):
        # strongly tinted pixels also use their own value.
        a_t = np.where(tint > 0.5 * tB, np.minimum(a_t, raw), a_t)
        t = tint > 0.15 * tB
        A[t] = np.minimum(A[t], a_t[t])
    # Generators leave a pale rim along the image border: clear it.
    rim = np.zeros((H, W), bool)
    rim[:, :4] = rim[:, -4:] = True
    rim[:4, :] = rim[-4:, :] = True
    A[rim & (C.min(-1) > 170) & (tint > 3)] = 0.0

    A[A < 0.15] = 0.0
    A[A > 0.97] = 1.0

    unmix = lambda X, a: np.clip((X - (1 - a) * B) / np.maximum(a, 1e-3), 0, 255)
    fade = lambda a: np.clip((a - 0.15) / 0.35, 0, 1)

    # Solid pixels the tint cap made see-through (sigh puffs, soft effects):
    # unmix them too, so a white puff stays white instead of going grey.
    out = C.copy()
    s = solid & (A > 0) & (A < 1)
    a_s = A[s][:, None]
    out[s] = unmix(C[s], a_s) * fade(a_s) + C[s] * (1 - fade(a_s))
    F = out[iy, ix]                                # nearest solid colour

    # Edge colour: unmix from B, fall back to F when faint, never lighter than F.
    e = edge & (A > 0) & (A < 1)
    ae = A[e][:, None]
    out[e] = np.minimum(unmix(C[e], ae) * fade(ae) + F[e] * (1 - fade(ae)), F[e])

    # Despill: remove any lean toward the bg hue (edge band, or everywhere).
    # Skipped for a white/grey background: it has no hue, so k would be an
    # arbitrary channel (red would turn skin grey).
    band = edge | (ndi.binary_dilation(~nonbg, iterations=4) & nonbg)
    where = np.ones_like(band) if despill_all else band
    if tB > 8 and dominant:
        cap = np.maximum(out[..., others[0]], out[..., others[1]])
        out[..., k] = np.where(where, np.minimum(out[..., k], cap), out[..., k])
    elif tB > 8:
        floor = np.minimum(out[..., others[0]], out[..., others[1]])
        out[..., k] = np.where(where, np.maximum(out[..., k], floor), out[..., k])
    out = np.clip(out, 0, 255)

    return np.dstack([out, A * 255]).round().astype(np.uint8), B


def sheet(paths, dest):
    tiles = []
    for i, p in enumerate(paths):
        im = Image.open(p)
        bg = (30, 30, 38) if i % 2 == 0 else (250, 250, 250)
        b = Image.new("RGBA", im.size, bg + (255,))
        b.alpha_composite(im)
        t = b.convert("RGB")
        t.thumbnail((230, 420))
        d = ImageDraw.Draw(t)
        label = os.path.splitext(os.path.basename(p))[0].split(", ")[-1]
        d.rectangle([0, 0, 110, 14], fill="black")
        d.text((3, 1), label, fill="white")
        tiles.append(t)
    cols = 5
    tw = max(t.width for t in tiles)
    th = max(t.height for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    s = Image.new("RGB", (tw * cols, th * rows), "white")
    for i, t in enumerate(tiles):
        s.paste(t, ((i % cols) * tw, (i // cols) * th))
    s.save(dest)


if __name__ == "__main__":
    argv = sys.argv[1:]
    sheet_path = None
    if "--sheet" in argv:
        i = argv.index("--sheet")
        sheet_path = argv[i + 1]
        del argv[i:i + 2]
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 3:
        sys.exit(__doc__)
    name, in_dir, out_dir = args
    despill_all = "--despill-all" in argv
    os.makedirs(out_dir, exist_ok=True)
    files = {os.path.splitext(f)[0]: f for f in os.listdir(in_dir)
             if f.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))}
    exprs = [e for e in ORDER if e in files] + sorted(set(files) - set(ORDER))
    outs = []
    for e in exprs:
        rgba, B = cut(os.path.join(in_dir, files[e]), despill_all)
        dest = os.path.join(out_dir, f"{name}, {e}.png")
        Image.fromarray(rgba, "RGBA").save(dest)
        outs.append(dest)
        a = rgba[..., 3]
        print(f"{e:12s} bg {B.round().astype(int).tolist()} edge {np.mean((a > 0) & (a < 255)):.4f} clear {np.mean(a == 0):.3f}")
    if sheet_path:
        sheet(outs, sheet_path)
        print("sheet:", sheet_path)
```

## ID card exports: transparent corners

The Rebis Academy ID card (Design canvas, 2000 CSS px wide, 44 px corner radius) exports as a rectangle, so the area outside the rounded corners is white. When Kom sends an export, write `card_corners.py` and run:

```
python3 card_corners.py "export.png" "Full Name, ID Card.png"
```

It detects the export scale from the width (a 4000 px export means radius 88 px). Check one corner over a coloured backdrop, then send the file named `Full Name, ID Card.png`.

```python
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
```