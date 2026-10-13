#!/usr/bin/env python3
"""Sprite background remover for flat, single-colour backgrounds (vivid or pale).

Usage:
  python3 cutout.py "Full Name" OUT_DIR IMAGE[=Expression] ... [--keep-tint] [--sheet SHEET.png]

Each IMAGE is read (never changed) and written as OUT_DIR/"Full Name, Expression.png"
(transparent RGBA). Expression defaults to the file name (Neutral.png -> Neutral); a
folder stands for all the images in it. Output and check sheet follow ORDER, then any
other expressions alphabetically. Prints one line per image with warnings.

--keep-tint  only clean bg-coloured tint off the edges, not the whole character
             (use when the character has eyes/clothes/hair in the background's hue).
--sheet      where to write the check sheet (default sheet.png).
"""
import os
import sys
from concurrent.futures import ProcessPoolExecutor
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

EXTS = (".png", ".jpg", ".jpeg", ".webp")

ORDER = ["Neutral", "Happy", "Playful", "Tired", "Sad", "Wary",
         "Angry", "Shocked", "Embarrassed", "Strained"]


def cut(path, despill_all=True, bg_thr=10.0):
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
    lo, mid, hi = np.argsort(B)           # low, mid, high
    keys = [(True, hi, [lo, mid], B[hi] - B[mid]), (False, lo, [mid, hi], B[mid] - B[lo])]
    keys.sort(key=lambda key: -key[3])    # the stronger signature first

    def make_tint(dominant, k, others, _=None):
        if dominant:
            return lambda X: X[..., k] - np.maximum(X[..., others[0]], X[..., others[1]])
        return lambda X: np.minimum(X[..., others[0]], X[..., others[1]]) - X[..., k]

    key = keys[0]
    two_way = keys[1][3] >= 0.4 * keys[0][3]
    if two_way:
        # In-between hues (mint, teal) read either way. Switch when only the
        # first reading sees bg hue in much of the character: light-blue jeans
        # or blue eyes are "low red" like mint, but not "green above all".
        # (Real bg mixes such as sigh puffs show under both readings.)
        inner = C[ndi.binary_erosion(dist > 60, iterations=6)]
        if len(inner):
            t0, t1 = [make_tint(*kk)(inner) > 0.3 * kk[3] for kk in keys]
            if np.mean(t0 & ~t1) > 0.002 and np.mean(t1 & ~t0) < 0.5 * np.mean(t0 & ~t1):
                key = keys[1]
    dominant, k, others, _ = key
    other = keys[1] if key is keys[0] else keys[0]
    tint_of = make_tint(*key)
    tB = float(tint_of(B[None, :])[0])

    lum = np.array([0.299, 0.587, 0.114], np.float32)
    # Generators leave a pale rim on the outer few px. Where it lies over the
    # bg (5 px in is bg, or the rim pixel is more bg-tinted than 5 px in) it
    # is background. Cool-white clothes running off the frame continue inward,
    # so they are not rim.
    band = np.zeros((H, W), bool)
    band[:, :4] = band[:, -4:] = True
    band[:4, :] = band[-4:, :] = True
    ry, rx = np.nonzero(band)
    Cr, In = C[ry, rx], C[np.clip(ry, 5, H - 6), np.clip(rx, 5, W - 6)]
    pale = ((Cr.min(-1) > 170) & (tint_of(Cr) > 3)
            & ((np.linalg.norm(In - B, axis=-1) < 60) | (tint_of(Cr) > tint_of(In) + 3)))
    rim = np.zeros((H, W), bool)
    rim[ry[pale], rx[pale]] = True

    # Clothes cut off by the frame: where the pixel 3 px in is clearly
    # character and the outer 1-2 px are lighter, give them that inner colour.
    frame = np.zeros((H, W), bool)
    frame[:, :2] = frame[:, -2:] = True
    frame[:2, :] = frame[-2:, :] = True
    fy, fx = np.nonzero(frame & ~rim)
    Cf, Fi = C[fy, fx], C[np.clip(fy, 2, H - 3), np.clip(fx, 2, W - 3)]
    fix = (np.linalg.norm(Fi - B, axis=-1) > 60) & (Cf @ lum > Fi @ lum + 8)
    C[fy[fix], fx[fix]] = Fi[fix]
    dist = np.linalg.norm(C - B, axis=-1)
    tint = tint_of(C)
    if two_way:
        # Where both readings see bg hue (smoke, glows, spill), use their mean:
        # either one alone under- or over-counts the bg in a bluish mix.
        own, alt = tint / tB, make_tint(*other)(C) / other[3]
        both = (own > 0.1) & (alt > 0.1)
        tint = np.where(both, tB * (own + alt) / 2, tint)

    Y = C @ lum
    YB = float(B @ lum)
    dY = Y - YB

    nonbg = (dist > bg_thr) & ~rim
    lab, n = ndi.label(nonbg)                      # drop tiny foreground specks
    if n:
        sizes = ndi.sum(np.ones_like(dist), lab, range(1, n + 1))
        nonbg &= ~np.isin(lab, np.where(sizes < 40)[0] + 1)
    lab, n = ndi.label(~nonbg)                     # fill tiny background pinholes
    if n:
        sizes = ndi.sum(np.ones_like(dist), lab, range(1, n + 1))
        nonbg |= np.isin(lab, np.where(sizes < 15)[0] + 1)

    # Compressed images ring: faint near-bg pixels just outside the line art.
    # Their alpha would be cut to 0 anyway; peel them off first so the edge
    # band starts at the line instead of 1-2 px outside it.
    localmax = ndi.maximum_filter(np.where(nonbg, dist, 0.0), size=7)
    faint = nonbg & (dist < 0.15 * np.maximum(localmax, 20.0))
    for _ in range(3):
        peel = faint & ndi.binary_dilation(~nonbg)
        nonbg &= ~peel

    # Only the outer ~2 px are anti-aliased (the image border is not an edge).
    edt_in = ndi.distance_transform_edt(np.pad(nonbg, 1, constant_values=True))[1:-1, 1:-1]
    solid = nonbg & (edt_in > 2.0)
    edge = nonbg & ~solid

    _, (iy, ix) = ndi.distance_transform_edt(~solid, return_indices=True)

    # Alpha relative to the strongest nearby stroke (the line art).
    A = np.zeros((H, W), np.float32)
    A[solid] = 1.0
    A[edge] = np.clip(dist / np.maximum(localmax, 20.0), 0.0, 1.0)[edge]
    # Lossy files (WebP, JPEG) keep brightness sharp but blur colour, so where
    # the nearby stroke differs from the bg in brightness, measure alpha in
    # brightness: against the darkest pixel nearby if this one is darker than
    # the bg, the lightest if lighter.
    Ymask = np.where(nonbg, dY, 0.0)
    ext = np.where(dY < 0, ndi.minimum_filter(Ymask, size=5), ndi.maximum_filter(Ymask, size=5))
    useY = edge & (np.abs(ext) > 40)
    A[useY] = np.clip(dY / np.where(np.abs(ext) > 1e-3, ext, 1e-3), 0.0, 1.0)[useY]

    # Pixels tinted toward the bg hue are mostly background: cap their alpha.
    if tB > 8:
        raw = np.clip(1.0 - tint / tB, 0.0, 1.0)
        a_t = ndi.median_filter(raw, size=5)
        # The median misses bg slivers 1-2 px wide (between hair strands):
        # strongly tinted pixels also use their own value.
        a_t = np.where(tint > 0.5 * tB, np.minimum(a_t, raw), a_t)
        # Floor: a pixel can't be mostly bg if it is far from the bg in
        # brightness (even black or white would need this much coverage).
        # Keeps thin dark lines solid when compression blurs bg hue into them.
        a_min = np.where(dY < 0, -dY / max(YB, 1.0), dY / max(255.0 - YB, 1.0))
        a_t = np.maximum(a_t, np.clip(a_min, 0.0, 1.0))
        t = tint > 0.15 * tB
        A[t] = np.minimum(A[t], a_t[t])
    A[rim] = 0.0

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

    return np.dstack([out, A * 255]).round().astype(np.uint8), B, tB



def report(rgba, B, tB):
    """One-line verdict: background type and any see-through areas inside the character."""
    notes = []
    if tB <= 8:
        notes.append("white/grey bg: white parts may be lost")
    elif tB < 60:
        notes.append("dull bg")
    a = rgba[..., 3]
    part = ndi.binary_erosion(a > 0, iterations=4) & (a < 204)
    lab, n = ndi.label(part)
    if n:
        sizes = ndi.sum(part, lab, range(1, n + 1))
        areas = sorted(((int(s), b) for s, b in zip(sizes, ndi.find_objects(lab)) if s >= 150),
                       key=lambda t: -t[0])
        for s, (ys, xs) in areas[:3]:
            notes.append(f"see-through {s}px at x{xs.start}-{xs.stop} y{ys.start}-{ys.stop}")
    return "; ".join(notes) or "ok"


def work(job):
    expr, path, dest, despill_all = job
    rgba, B, tB = cut(path, despill_all)
    Image.fromarray(rgba, "RGBA").save(dest)
    return f"{expr:12s} bg {B.round().astype(int).tolist()}  {report(rgba, B, tB)}"


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
    sheet_path = "sheet.png"
    if "--sheet" in argv:
        i = argv.index("--sheet")
        sheet_path = argv[i + 1]
        del argv[i:i + 2]
    despill_all = "--keep-tint" not in argv
    args = [a for a in argv if not a.startswith("--")]
    if len(args) < 3:
        sys.exit(__doc__)
    name, out_dir = args[:2]
    images = {}
    for item in args[2:]:
        path, expr = item, ""
        if "=" in item and os.path.exists(item.rpartition("=")[0]):
            path, _, expr = item.rpartition("=")
        paths = ([os.path.join(path, f) for f in sorted(os.listdir(path)) if f.lower().endswith(EXTS)]
                 if os.path.isdir(path) else [path])
        for p in paths:
            e = expr or os.path.splitext(os.path.basename(p))[0]
            if e in images:
                sys.exit(f"two images for {e}: {images[e]} and {p}")
            images[e] = p
    exprs = [e for e in ORDER if e in images] + sorted(set(images) - set(ORDER))
    os.makedirs(out_dir, exist_ok=True)
    jobs = [(e, images[e], os.path.join(out_dir, f"{name}, {e}.png"), despill_all) for e in exprs]
    # ~0.45 GB per sprite at 1143x2000: two at a time keeps memory modest.
    with ProcessPoolExecutor(max_workers=max(1, min(2, os.cpu_count() or 1, len(jobs)))) as ex:
        for line in ex.map(work, jobs):
            print(line)
    sheet([j[2] for j in jobs], sheet_path)
    print("sheet:", sheet_path)
