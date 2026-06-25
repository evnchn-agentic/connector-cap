"""Extract cap (trapezoid) geometry from the scale drawing (image 1).

Blue ink on white paper:
  - outer rounded rectangle = traced credit card  -> known ISO ID-1 = 85.60 x 53.98 mm
  - inner rounded trapezoid  = the cap top outline -> what we want, in mm

Method: threshold blue, label white regions. Outermost-but-enclosing -> card,
innermost enclosed hole -> trapezoid interior. Use the card's pixel size as scale
(separately in x and y to expose perspective), then report trapezoid metrics.
"""
import numpy as np
from PIL import Image
from scipy import ndimage

CARD_W_MM = 85.60   # ISO/IEC 7810 ID-1
CARD_H_MM = 53.98

img = Image.open("refs/20260612_161205.jpg")
a = np.asarray(img).astype(np.int16)
R, G, B = a[..., 0], a[..., 1], a[..., 2]

# blue ink: B clearly above R and G
blue = (B - R > 22) & (B - G > 12) & (B > 70)
# clean specks
blue = ndimage.binary_closing(blue, iterations=2)
blue = ndimage.binary_opening(blue, iterations=1)
print("blue px:", int(blue.sum()))

# --- label WHITE (non-blue) regions ---
white = ~blue
lab, n = ndimage.label(white)
print("white regions:", n)
H, W = blue.shape
border_ids = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]])))
sizes = ndimage.sum(np.ones_like(lab), lab, index=np.arange(1, n + 1))

# enclosed (not touching border) white regions, by size desc
enclosed = [(i + 1, sizes[i]) for i in range(n) if (i + 1) not in border_ids]
enclosed.sort(key=lambda t: -t[1])
print("enclosed white regions (id,size) top5:", [(int(i), int(s)) for i, s in enclosed[:5]])

# innermost = enclosed white region with the SMALLEST bbox (annulus has card-sized bbox)
def bbox_area(i):
    ys, xs = np.where(lab == i)
    return (ys.max() - ys.min()) * (xs.max() - xs.min())
trap_id = min((i for i, _ in enclosed), key=bbox_area)
print("chosen trapezoid region id:", trap_id)
trap = lab == trap_id

# card = blue bbox (outer loop). use full blue extent.
ys, xs = np.where(blue)
card_x0, card_x1 = xs.min(), xs.max()
card_y0, card_y1 = ys.min(), ys.max()
card_px_w = card_x1 - card_x0
card_px_h = card_y1 - card_y0
print(f"\ncard bbox px: x {card_x0}..{card_x1} (w {card_px_w}), y {card_y0}..{card_y1} (h {card_px_h})")
sx = CARD_W_MM / card_px_w   # mm per px, horizontal
sy = CARD_H_MM / card_px_h   # mm per px, vertical
print(f"scale: sx={sx:.5f} mm/px  sy={sy:.5f} mm/px  (aniso {sx/sy:.3f})")

# --- trapezoid metrics ---
tys, txs = np.where(trap)
ty0, ty1 = tys.min(), tys.max()
tx0, tx1 = txs.min(), txs.max()
print(f"\ntrapezoid interior bbox px: x {tx0}..{tx1}, y {ty0}..{ty1}")

# width profile: for each row, span of interior
rows = np.arange(ty0, ty1 + 1)
left = np.full(rows.shape, np.nan)
right = np.full(rows.shape, np.nan)
for k, y in enumerate(rows):
    cols = np.where(trap[y])[0]
    if cols.size:
        left[k] = cols.min(); right[k] = cols.max()
widths = (right - left)

# height profile: for each col, span
cols_all = np.arange(tx0, tx1 + 1)
top = np.full(cols_all.shape, np.nan)
bot = np.full(cols_all.shape, np.nan)
for k, x in enumerate(cols_all):
    r = np.where(trap[:, x])[0]
    if r.size:
        top[k] = r.min(); bot[k] = r.max()

interior_h_px = ty1 - ty0
# sample widths away from rounded corners: 15%,50%,85% of height
def width_at(frac):
    y = int(ty0 + frac * interior_h_px)
    cols = np.where(trap[y])[0]
    return (cols.max() - cols.min()) if cols.size else np.nan

print("\n--- trapezoid (INTERIOR / inner edge of ink) in mm ---")
print(f"  overall  W(px {tx1-tx0}) = {(tx1-tx0)*sx:.1f} mm   H(px {interior_h_px}) = {interior_h_px*sy:.1f} mm")
for f in (0.10, 0.15, 0.30, 0.50, 0.70, 0.85, 0.90):
    print(f"  width @ {int(f*100):>2}% height: {width_at(f)*sx:6.1f} mm")

# top edge width (near top, below corner radius) and bottom edge width
print(f"\n  approx TOP edge width   ~{width_at(0.18)*sx:.1f} mm")
print(f"  approx BOTTOM edge width ~{width_at(0.82)*sx:.1f} mm")

# position of trapezoid centre relative to card
cap_cx = (tx0 + tx1) / 2; cap_cy = (ty0 + ty1) / 2
card_cx = (card_x0 + card_x1) / 2; card_cy = (card_y0 + card_y1) / 2
print(f"\n  cap centre offset from card centre: dx={ (cap_cx-card_cx)*sx:.1f} mm  dy={ (cap_cy-card_cy)*sy:.1f} mm")

# save a debug overlay
from PIL import Image as I2
ov = np.asarray(img).copy()
ov[blue] = [255, 0, 0]
ov[trap] = [0, 255, 0]
I2.fromarray(ov).save("refs/_dbg_drawing.png")
print("\nsaved refs/_dbg_drawing.png")
