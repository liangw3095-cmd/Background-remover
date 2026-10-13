#!/usr/bin/env python3
"""Regression check for the sprite-background-removal skill.

Pulls cutout.py and card_corners.py out of SKILL.md (so the code tested is the
code the skill writes out), runs them on synthetic sprites and ID cards with a
known right answer, and fails if a cutout drifts. Some sprites go through lossy
WebP first, like images pasted into a chat.

Usage: python3 tests/check_skill.py [--keep DIR]
"""
import io
import os
import re
import subprocess
import sys
import tempfile
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL = os.path.join(ROOT, "sprite-background-removal", "SKILL.md")

W, H, SS = 832, 1216, 4
LINE = (40, 30, 35)
SKIN = (250, 222, 205)
EYES = (slice(385, 426), slice(352, 389)), (slice(385, 426), slice(462, 499))
PUFF = (slice(540, 580), slice(160, 200))
DROP = (slice(328, 343), slice(583, 595))


def sprite(eye):
    """Hard-edged RGBA sprite at SS x scale: line art, thin hair strands with a
    gap to the neck, a blazer cut off by the right and bottom frame (with a
    dark fold running off the bottom), a tiny sweat drop and a 55% white sigh
    puff."""
    im = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    s = lambda *v: [x * SS for x in v]
    lw = 3 * SS
    hair = (70, 45, 40, 255)
    d.ellipse(s(250, 140, 600, 560), fill=hair, outline=LINE, width=lw)
    for x0, w in [(300, 1.0), (310, 0.5), (318, 2.0), (530, 1.0), (540, 0.5), (548, 2.0)]:
        d.line(s(x0, 480, x0 + 12, 760), fill=hair, width=max(1, int(w * SS)))
    d.rectangle(s(385, 520, 465, 800), fill=SKIN + (255,), outline=LINE, width=lw)
    d.ellipse(s(300, 230, 550, 600), fill=SKIN + (255,), outline=LINE, width=lw)
    for cx in (370, 480):
        d.ellipse(s(cx - 22, 380, cx + 22, 430), fill=eye + (255,), outline=LINE, width=2 * SS)
        d.ellipse(s(cx - 6, 395, cx + 6, 410), fill=(15, 15, 25, 255))
    d.polygon(s(290, 300, 425, 200, 560, 300, 520, 270, 425, 250, 330, 270), fill=hair, outline=LINE)
    d.polygon(s(180, 1216, 260, 830, 425, 790, 600, 830, 832, 900, 832, 1216), fill=(35, 40, 70, 255),
              outline=LINE, width=lw)
    d.line(s(500, 1060, 515, 1216), fill=LINE, width=2 * SS)
    d.polygon(s(385, 795, 425, 900, 465, 795), fill=(245, 245, 245, 255), outline=LINE, width=2 * SS)
    d.ellipse(s(585, 330, 592, 340), fill=(170, 210, 255, 255), outline=LINE, width=SS)
    puff = Image.new("RGBA", im.size, (0, 0, 0, 0))
    pd = ImageDraw.Draw(puff)
    for cx, cy, r in [(180, 560, 40), (140, 520, 30), (215, 520, 28)]:
        pd.ellipse(s(cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, 140))
    return Image.alpha_composite(puff, im)


def downsample(rgba):
    a = np.asarray(rgba).astype(np.float64)
    al = a[..., 3:] / 255.0
    pre = np.concatenate([a[..., :3] * al, al], -1).reshape(H, SS, W, SS, 4).mean((1, 3))
    return pre[..., :3] / np.maximum(pre[..., 3:], 1e-6), pre[..., 3]


# name: (bg colour, darkening toward the bottom, pale rim on the right border,
#        WebP quality or None, max % of edge pixels visibly off)
SPRITES = {
    "vivid_green": ((30, 230, 50), 0, True, None, 3),
    "pale_green": ((190, 235, 195), 0, True, None, 2),
    "magenta": ((230, 40, 220), 0, False, None, 5.5),
    "pale_green_gradient": ((190, 235, 195), 18, False, None, 3.5),
    "white": ((252, 250, 249), 0, False, None, None),
    "vivid_green_webp": ((30, 230, 50), 0, True, 80, 9),
    "pale_green_webp": ((226, 255, 218), 0, True, 80, 3.5),
}


def make_sprites(root):
    rng = np.random.default_rng(0)
    col, alpha = downsample(sprite((60, 110, 200)))
    for name, (bg, grad, rim, webp, _) in SPRITES.items():
        bgimg = np.broadcast_to(np.array(bg, float), (H, W, 3)).copy()
        bgimg -= np.linspace(0, grad, H)[:, None, None]
        img = col * alpha[..., None] + bgimg * (1 - alpha[..., None])
        if rim:
            pale = np.array(bg, float) * 0.3 + 255 * 0.7
            for k, f in [(1, 0.6), (2, 0.35)]:
                img[:, -k] = img[:, -k] * (1 - f) + pale * f
        img += rng.normal(0, 1.5, img.shape)
        im = Image.fromarray(np.clip(img, 0, 255).round().astype(np.uint8))
        if webp:
            buf = io.BytesIO()
            im.save(buf, "WEBP", quality=webp)
            im = Image.open(io.BytesIO(buf.getvalue())).convert("RGB")
        os.makedirs(os.path.join(root, name, "in"), exist_ok=True)
        im.save(os.path.join(root, name, "in", "Neutral.png"))
    return col, alpha


def make_card(path, border):
    """4000 px export of a 2000 CSS px card (radius 88 px), white outside the corners."""
    CW, CH, R, cs, ss = 4000, 2520, 88, 98, 8
    face, stroke = (240, 228, 200), (30, 40, 90)
    im = Image.new("RGB", (CW, CH), "white")
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([0, 0, CW - 1, CH - 1], radius=R, fill=face)
    if border:
        d.rectangle([0, 0, CW - 1, CH - 1], outline=stroke, width=border)
    for x0, y0 in [(0, 0), (CW - cs, 0), (0, CH - cs), (CW - cs, CH - cs)]:
        c = Image.new("RGB", (cs * ss, cs * ss), "white")
        cd = ImageDraw.Draw(c)
        o = (-x0 * ss, -y0 * ss)
        box = [o[0], o[1], o[0] + CW * ss - 1, o[1] + CH * ss - 1]
        cd.rounded_rectangle(box, radius=R * ss, fill=stroke if border else face)
        if border:
            b = border * ss
            cd.rounded_rectangle([box[0] + b, box[1] + b, box[2] - b, box[3] - b],
                                 radius=(R - border) * ss, fill=face)
        im.paste(c.resize((cs, cs), Image.BOX), (x0, y0))
    im.save(path)
    return np.array(stroke if border else face, float)


def main():
    keep = sys.argv[sys.argv.index("--keep") + 1] if "--keep" in sys.argv else None
    work = keep or tempfile.mkdtemp()
    os.makedirs(work, exist_ok=True)
    blocks = re.findall(r"```python\n(.*?)```", open(SKILL).read(), re.S)
    assert len(blocks) == 2, "SKILL.md should hold cutout.py and card_corners.py"
    for name, code in zip(["cutout.py", "card_corners.py"], blocks):
        open(os.path.join(work, name), "w").write(code)

    failures = []

    def check(label, ok, detail):
        print(f"  {'ok  ' if ok else 'FAIL'} {label:28s} {detail}")
        if not ok:
            failures.append(label)

    col, alpha = make_sprites(work)
    gt = np.dstack([col, alpha])
    deep = ndi.binary_erosion(alpha > 0.999, iterations=3)
    deep[:, -3:] = deep[-3:, :] = False
    clear = alpha < 0.001
    clear[:, -3:] = clear[-3:, :] = False
    edge = (alpha > 0.001) & (alpha < 0.999)
    edge[:, -3:] = edge[-3:, :] = False
    near = ndi.binary_dilation(edge, iterations=2)
    near[:, -3:] = near[-3:, :] = False

    def over(rgb, a, bgc):
        return rgb * a[..., None] + np.array(bgc, float) * (1 - a[..., None])

    for name, (bg, _, _, webp, max_off) in SPRITES.items():
        d = os.path.join(work, name)
        subprocess.run([sys.executable, os.path.join(work, "cutout.py"), "Test Girl",
                        os.path.join(d, "in"), os.path.join(d, "out"), "--despill-all"],
                       check=True, stdout=subprocess.DEVNULL)
        out = np.asarray(Image.open(os.path.join(d, "out", "Test Girl, Neutral.png"))).astype(float)
        oa = out[..., 3] / 255
        cerr = np.abs(out[..., :3] - gt[..., :3]).max(-1)
        print(name)
        if name == "white":
            # White on white can't be cut perfectly; the skin must keep its colour.
            skin = np.abs(out[500, 425, :3] - np.array(SKIN)).max()
            check("skin colour kept", skin <= 6, f"{out[500, 425, :3].astype(int).tolist()}")
            continue
        check("no holes in body", np.mean(oa[deep] < 0.95) < 0.001, f"{np.mean(oa[deep] < 0.95):.4f}")
        # Lossy input blurs lines by ~1 px, so for WebP look from 2 px out.
        cl = ndi.binary_erosion(clear, iterations=2) if webp else clear
        check("no background left", np.mean(oa[cl] > 0.05) < 0.001, f"{np.mean(oa[cl] > 0.05):.4f}")
        check("edge alpha", np.mean(np.abs(oa - alpha)[edge]) < 0.08, f"MAE {np.mean(np.abs(oa - alpha)[edge]):.3f}")
        check("body colour", cerr[deep].mean() < (6 if webp else 4), f"mean err {cerr[deep].mean():.1f}")
        # Edges as seen over a dark and a light scene: % of pixels off by > 40.
        off = np.maximum(*[np.abs(over(out[..., :3], oa, b) - over(col, alpha, b)).max(-1)
                           for b in [(30, 30, 38), (250, 250, 250)]])
        pct = np.mean(off[near] > 40) * 100
        check("edges over a scene", pct < max_off, f"{pct:.1f}% of edge px off (max {max_off}%)")
        # Clothes cut off by the frame stay solid (bottom rows, right columns).
        fa = min(oa[-2:, 300:800].min(), oa[930:1200, -2:].min())
        check("clothes at frame solid", fa > 0.99, f"min alpha {fa:.2f}")
        eyes = np.concatenate([oa[e] for e in EYES])
        check("eyes opaque", eyes.min() > 0.99, f"min alpha {eyes.min():.2f}")
        check("sweat drop kept", oa[DROP].max() == 1.0, f"max alpha {oa[DROP].max():.2f}")
        pa, pc = oa[PUFF].mean(), out[PUFF][..., :3].reshape(-1, 3).mean(0)
        check("sigh puff 55% white", 0.5 < pa < 0.6 and pc.min() > 230,
              f"alpha {pa:.2f} colour {pc.round().astype(int).tolist()}")

    print("ID card corners")
    for label, border in [("plain card", 0), ("bordered card", 16)]:
        src, dst = os.path.join(work, f"{label}.png"), os.path.join(work, f"{label} out.png")
        rim = make_card(src, border)
        subprocess.run([sys.executable, os.path.join(work, "card_corners.py"), src, dst],
                       check=True, stdout=subprocess.DEVNULL)
        out = np.asarray(Image.open(dst)).astype(float)
        a = out[..., 3] / 255
        part = (a > 0) & (a < 1)
        corners = [a[0, 0], a[0, -1], a[-1, 0], a[-1, -1]]
        check(f"{label}: corners clear", max(corners) == 0 and a[0, 2000] == 1 and a[1260, 0] == 1,
              f"corner alpha {max(corners):.0f}")
        err = np.abs(out[part][:, :3] - rim).max(-1).mean()
        check(f"{label}: no fringe", err < 3, f"edge colour err {err:.1f}")

    print(f"\n{'all checks passed' if not failures else f'{len(failures)} failed: ' + ', '.join(failures)}"
          + (f"\noutputs in {work}" if keep else ""))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
