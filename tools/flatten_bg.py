"""Flatten a same-hue patterned bg (burst streaks) to its main colour."""
import sys, numpy as np
from PIL import Image
from scipy import ndimage as ndi
src, dst = sys.argv[1:3]
C = np.asarray(Image.open(src).convert("RGB")).astype(np.float32)
H, W, _ = C.shape
top = C[:200].reshape(-1, 3)
Y = top @ [0.299, 0.587, 0.114]
B = np.median(top[Y > np.median(Y)], axis=0)            # the brighter, main bg tone
lo, mid, hi = np.argsort(B)
t = lambda X: np.minimum(X[..., mid], X[..., hi]) - X[..., lo]
m = t(C) > 0.6 * t(B[None])[0]
lab, _ = ndi.label(m)
edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
bg = np.isin(lab, edge[edge > 0])
C[bg] = B
Image.fromarray(C.round().astype(np.uint8)).save(dst)
print(src.split('/')[-1], "bg", B.round().astype(int).tolist(), "flattened", int(bg.sum()))
