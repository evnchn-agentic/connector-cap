"""Connector-panel cap — thin-walled shell + XT60/ethernet windows + screw holes.

Design:
  - Golden trapezoid outline (66 wide / 59.3 narrow / 26.5 deep, R4).
  - Thin-walled CAP SHELL: PLATE_T top plate + WALL perimeter walls, hollow, NO lip.
  - Two windows (XT60 house-shaped, ethernet rounded-rect) + two screw holes.
  - All feature positions are given in the user's 0..66 width ruler, then a single
    MIRROR_X / MIRROR_Y stage flips them to the installed orientation. The golden
    outline is symmetric in X and fixed, so mirroring only moves the cuts.

Frame: cap z in [0, THICK]; cavity opens at z=0 (bottom). +Y = wide edge.
Run:  python build_cap.py   ->  cap.step/.stl, xt60.step/.stl, cap_*.png + report
"""
import math, types
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import trimesh
from build123d import (
    Polygon, RectangleRounded, Box, Cylinder, Pos, Plane, Kind,
    extrude, offset, fillet, mirror, export_step, export_stl,
)

# ===================== KNOBS (mm) =====================
# --- outline (GOLDEN) + shell ---
TOP_W, BOT_W, DEPTH, CORNER_R = 66.0, 59.3, 26.5, 4.0
THICK, PLATE_T, WALL = 7.0, 2.0, 1.5
BODY_CLR = 0.0                      # shrink whole cap for recess fit (try 0.3 if tight)

WIDTH_REF = 66.0                    # the 0..WIDTH_REF ruler the user measures on
def u2x(u):  return u - WIDTH_REF/2 # 0..66  ->  centred model X

# --- openings, given on the 0..66 ruler ---
XT_U0, XT_U1 = 50.0, 58.0           # XT60 width extent  -> centre 54
XT_W, XT_H, XT_CHAMF, XT_LEN = 8.3, 15.6, 2.6, 16.0   # XT60 outline (measured)
WIN_CLR = 0.75                      # window clearance around the XT60 outline

ETH_U0, ETH_U1 = 30.0, 41.0         # ethernet width extent -> centre 35.5
ETH_W, ETH_H, ETH_R = ETH_U1 - ETH_U0 + 1.0, 13.0, 1.2  # +1mm wider (user); ETH_H (Y) assumed
# operator nudge in FINAL frame (after mirror): 2mm left (toward XT60), 3mm lower (toward -Y short edge)
ETH_NUDGE_X, ETH_NUDGE_Y = -2.0, -3.0

# --- SLIM variant: flat ethernet cable (8 wide x 2 tall), disguised ---
# Instead of a fat RJ45 window, a 2mm-tall slot runs from the XT60 window across to
# the ethernet port so the flat cable slots in (RJ45 connector is too thick to seat).
SLIM_VERSION = True
CABLE_W, CABLE_T = 9.0, 2.5          # slot: 9mm wide (1mm wider), 2.5mm tall (was 8x2)
SLOT_SHORTER = 3.0                   # slot is 3mm LESS LONG (cut from XT60 rightwards, far
                                    # end retracted 3mm). Through-cut. UNVERIFIED geometry.
# NOTE: cutout HEIGHTS (Y) are NOT calibrated yet -> slot Y centred at 0 (see TODO.md)

# --- screw holes: anchored to the WIDE edge (flip-invariant), counterbored ---
SCREW_D = 2.8              # FREE clearance for the 2mm screw — passes straight through the
                          # cap (threads only into the device, never the cap). 2.8 designed
                          # ~ 2.5 printed after FDM shrink -> still free on a 2mm shank.
SCREW_FROM_TOP = 6.0       # from wide edge
SCREW_FROM_SIDE = 3.0      # in from the slanted side edge
BORE_D, BORE_DEPTH = 5.5, 3.0   # counterbore inset: 5.5mm wide (6mm breached the edge), 3mm deep
BOSS_D = 5.5               # boss = bore; at 5.5 leaves ~0.26mm wall to the slanted edge
MEMBRANE_T = 0.2          # V1.1: 0.2mm solid skin closing the hole at the counterbore
                          # floor (print-z 2.0-2.2) -> printer BRIDGES the Ø4 flat (no
                          # support); drill through the 0.2mm after printing.
# stackup: 7mm cap, head seats 2mm down (z=5) -> 6mm thread tip at z=-1 -> 1mm bite

# --- installed-orientation mirror: only X (windows to the left).
# MIRROR_Y must stay False: it only ever flipped the XT60 chamfer (180deg rotation)
# and shoved screws to the narrow edge -- both were de-cursing regressions.
MIRROR_X, MIRROR_Y = True, False

PREFIX = "cap"
# ======================================================

SX = -1 if MIRROR_X else 1
SY = -1 if MIRROR_Y else 1

# feature centres (natural frame, before mirror)
XT_X0,  XT_Y0  = (XT_U0 + XT_U1)/2 - WIDTH_REF/2, 0.0
ETH_X0, ETH_Y0 = (ETH_U0 + ETH_U1)/2 - WIDTH_REF/2, 0.0


def trap_pts(top_w, bot_w, depth):
    return [(-bot_w/2, -depth/2), (bot_w/2, -depth/2),
            (top_w/2,  depth/2), (-top_w/2,  depth/2)]


def trap_face(top_w, bot_w, depth, r):
    sk = Polygon(*trap_pts(top_w, bot_w, depth), align=None)
    return fillet(sk.vertices(), radius=r) if r > 0 else sk


def xt60_face(w, h, chamf):
    """House cross-section (CCW): rectangle with 45deg chamfers at the -Y end."""
    hw, hh = w/2, h/2
    pts = [(-hw, hh), (-hw, -hh + chamf), (-hw + chamf, -hh),
           (hw - chamf, -hh), (hw, -hh + chamf), (hw, hh)]
    return Polygon(*pts, align=None)


def screws_natural():
    """Both screws in the natural frame: 5mm below +Y edge, 4mm in from the side."""
    y = DEPTH/2 - SCREW_FROM_TOP
    frac = (DEPTH/2 - y) / DEPTH
    edge_x = -TOP_W/2 + (TOP_W/2 - BOT_W/2) * frac
    x = edge_x + SCREW_FROM_SIDE
    return [(x, y), (-x, y)]


def place(sketch, x0, y0, mirror_y=False):
    """Apply the global mirror to a sketch defined at origin, then move to (x0,y0)."""
    if mirror_y and MIRROR_Y:
        sketch = mirror(sketch, about=Plane.XZ)   # flip chamfer to +Y side
    return Pos(SX * x0, SY * y0) * sketch


# resolved feature centres, shared by build + plots.
# WINDOWS mirror with the install flip; SCREWS are edge-referenced to the wide edge
# (flip-invariant) so they must NOT be mirrored -- mirroring them was the regression.
XT_CX, XT_CY = SX * XT_X0, SY * XT_Y0                      # XT60 FROZEN
ETH_CX, ETH_CY = SX * ETH_X0 + ETH_NUDGE_X, SY * ETH_Y0 + ETH_NUDGE_Y   # PORT (DEV window): nudged
ETH_SLOT_CX, ETH_SLOT_CY = SX * ETH_X0, SY * ETH_Y0       # SLOT (SLEEK): BASE pos, nudges NOT applied
SCREWS = screws_natural()


# variants: (prefix, slim_ethernet, inset_screws).
#  DEV = full RJ45 window, SLEEK = slim cable slot.
#  *_long = NO counterbore + NO 0.2mm membrane (plain through-hole) for long screws.
VARIANTS = [
    ("cap_dev",       False, True),
    ("cap_sleek",      True,  True),
    ("cap_dev_long",  False, False),
    ("cap_sleek_long", True,  False),
]


def build_cap(slim, inset):
    outline = trap_face(TOP_W - 2*BODY_CLR, BOT_W - 2*BODY_CLR, DEPTH - 2*BODY_CLR, CORNER_R)
    outer = extrude(outline, THICK)
    # hollow shell: remove inner cavity from the bottom (no lip)
    cap = outer - extrude(offset(outline, amount=-WALL, kind=Kind.ARC), THICK - PLATE_T)

    # screw bosses: solid columns (clipped to the outline so they never poke out)
    for (sx, sy) in SCREWS:
        cap = cap + ((Pos(sx, sy, THICK/2) * Cylinder(BOSS_D/2, THICK)) & outer)

    # cuts, all through the full height
    cut = place(offset(xt60_face(XT_W, XT_H, XT_CHAMF), WIN_CLR, kind=Kind.ARC),
                XT_X0, XT_Y0, mirror_y=True)
    cut = Pos(0, 0, -1) * extrude(cut, THICK + 2)
    if slim:
        # SLEEK: through-slot from the XT60 window rightwards toward the cable, at the eth Y,
        # 3mm shorter than full reach. NOTE: thin-slot geometry is UNVERIFIED (provisional).
        sx_l, sx_r = XT_CX, ETH_SLOT_CX + CABLE_W/2 - SLOT_SHORTER
        cut = cut + Pos((sx_l + sx_r)/2, ETH_SLOT_CY, THICK/2) * Box(sx_r - sx_l, CABLE_T, THICK + 2)
    else:
        # DEV: full RJ45 window
        cut = cut + Pos(ETH_CX, ETH_CY, -1) * extrude(RectangleRounded(ETH_W, ETH_H, ETH_R), THICK + 2)
    if inset:
        bore_floor = THICK - BORE_DEPTH             # counterbore floor
        shaft_top = bore_floor - MEMBRANE_T         # shaft stops 0.2mm short -> bridging skin
        for (sx, sy) in SCREWS:
            cut = cut + Pos(sx, sy, (-1 + shaft_top)/2) * Cylinder(SCREW_D/2, shaft_top + 1)
            cut = cut + Pos(sx, sy, THICK - BORE_DEPTH/2 + 0.1) * Cylinder(BORE_D/2, BORE_DEPTH + 0.2)
    else:
        # long-screw variant: plain through-hole, no counterbore, no membrane
        for (sx, sy) in SCREWS:
            cut = cut + Pos(sx, sy, THICK/2) * Cylinder(SCREW_D/2, THICK + 2)

    return types.SimpleNamespace(cap=cap - cut)


def build_xt60():
    body = extrude(xt60_face(XT_W, XT_H, XT_CHAMF), XT_LEN)
    for dy in (XT_H*0.22, -XT_H*0.22):
        body = body + Pos(0, dy, XT_LEN) * Cylinder(1.75, 3)
    return body


def verify_export(prefix, slim, inset):
    cap = build_cap(slim, inset).cap
    bb = cap.bounding_box()
    kind = ("SLEEK slim slot" if slim else "DEV full RJ45 window") + ("" if inset else " + LONG (no inset)")
    print(f"[{prefix}] {kind}  solids={len(cap.solids())}  "
          f"bbox {bb.size.X:.2f} x {bb.size.Y:.2f} x {bb.size.Z:.2f}  vol {cap.volume:.0f} mm^3")
    assert len(cap.solids()) == 1, f"expected 1 solid, got {len(cap.solids())}"
    assert abs(bb.size.Z - THICK) < 0.05
    export_step(cap, f"{prefix}.step"); export_stl(cap, f"{prefix}.stl", tolerance=0.01, angular_tolerance=0.1)
    print(f"  exported {prefix}.step / {prefix}.stl")


def xt60_window_pts():
    """Outline of the (mirrored, placed) XT60 window — for the 2D plots."""
    hw, hh, c = XT_W/2 + WIN_CLR, XT_H/2 + WIN_CLR, XT_CHAMF
    pts = np.array([(-hw, hh), (-hw, -hh+c), (-hw+c, -hh), (hw-c, -hh),
                    (hw, -hh+c), (hw, hh), (-hw, hh)])
    if MIRROR_Y:
        pts[:, 1] *= -1
    return pts + [XT_CX, XT_CY]


def top_view(prefix, slim, inset):
    fig, ax = plt.subplots(figsize=(8.5, 5))
    p = np.array(trap_pts(TOP_W, BOT_W, DEPTH) + [trap_pts(TOP_W, BOT_W, DEPTH)[0]])
    ax.plot(p[:, 0], p[:, 1], "k-", lw=2, label="cap outline (golden)")
    wp = xt60_window_pts()
    ax.add_patch(plt.Polygon(wp[:-1], closed=True, fill=True, color="#c0392b", alpha=0.4, label="XT60 window"))
    if slim:
        sx_l, sx_r = XT_CX, ETH_SLOT_CX + CABLE_W/2 - SLOT_SHORTER
        ax.add_patch(plt.Rectangle((sx_l, ETH_SLOT_CY-CABLE_T/2), sx_r - sx_l, CABLE_T,
                     fill=True, color="#2980b9", alpha=0.5, label="slim cable slot (unverified)"))
        ax.add_patch(plt.Rectangle((ETH_SLOT_CX-CABLE_W/2, ETH_SLOT_CY-CABLE_T/2), CABLE_W, CABLE_T,
                     fill=False, ec="#16a085", lw=1.2, label="cable @ eth port"))
    else:
        ax.add_patch(plt.Rectangle((ETH_CX-ETH_W/2, ETH_CY-ETH_H/2), ETH_W, ETH_H,
                     fill=True, color="#2980b9", alpha=0.4, label="ethernet window"))
    for i, (sx, sy) in enumerate(SCREWS):
        ax.add_patch(plt.Circle((sx, sy), BOSS_D/2, fill=False, ec="#7f8c8d", lw=0.8,
                     label="screw boss" if i == 0 else None))
        if inset:
            ax.add_patch(plt.Circle((sx, sy), BORE_D/2, fill=False, ec="#2c3e50", lw=0.8,
                         label=f"counterbore Ø{BORE_D:g}" if i == 0 else None))
        ax.add_patch(plt.Circle((sx, sy), SCREW_D/2, color="#2c3e50",
                     label="M2 shaft" if i == 0 else None))
    ax.annotate(f"WIDE {TOP_W:g} (+Y)", (0, DEPTH/2), ha="center", va="bottom", fontsize=8)
    ax.annotate(f"NARROW {BOT_W:g} (-Y)", (0, -DEPTH/2), ha="center", va="top", fontsize=8)
    ax.set_aspect("equal"); ax.grid(alpha=0.3)
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), fontsize=8)
    title = ("SLEEK slim slot" if slim else "DEV full RJ45 window") + ("" if inset else " + LONG (no inset)")
    ax.set_title(f"{prefix} — {title}")
    ax.set_xlabel("X (mm)"); ax.set_ylabel("Y (mm)")
    fig.savefig(f"{prefix}_top.png", dpi=140, bbox_inches="tight"); plt.close(fig)


def section_view(prefix):
    mesh = trimesh.load(f"{prefix}.stl")
    fig, axs = plt.subplots(1, 2, figsize=(13, 5))
    # 1) through the XT60 window: shell wall + window
    s = mesh.section(plane_origin=[XT_CX, 0, 0], plane_normal=[1, 0, 0])
    if s:
        for p in s.discrete:
            axs[0].plot(p[:, 1], p[:, 2], color="#1d3f8a", lw=1.6)
    axs[0].set_title(f"Section x={XT_CX:.0f} — shell {PLATE_T}+{WALL}mm + XT60 window")
    axs[0].set_xlabel("Y (mm)")
    # 2) through a screw boss: counterbore + shaft + boss (cut along Y at the screw x)
    sx, sy = SCREWS[0]
    s2 = mesh.section(plane_origin=[sx, 0, 0], plane_normal=[1, 0, 0])
    if s2:
        for p in s2.discrete:
            axs[1].plot(p[:, 1], p[:, 2], color="#8a1d3f", lw=1.6)
    axs[1].axhline(0, color="r", lw=0.8, ls=":")
    axs[1].axhline(-1, color="r", lw=0.8, ls=":")
    axs[1].annotate("device surface z=0\nthread bite to z=-1", (sy, -1), fontsize=7, color="r", va="top")
    axs[1].set_title(f"Section x={sx:.1f} — screw boss: {BORE_DEPTH}mm inset / "
                     f"{SCREW_D}mm shaft / boss {BOSS_D}")
    axs[1].set_xlabel("Y (mm)")
    for ax in axs:
        ax.axhline(0, color="0.7", lw=0.5); ax.set_aspect("equal"); ax.grid(alpha=0.3)
        ax.set_ylabel("Z (mm)"); ax.set_ylim(-2, 8)
    fig.savefig(f"{prefix}_sections.png", dpi=140, bbox_inches="tight"); plt.close(fig)


def printability(prefix):
    m = trimesh.load(f"{prefix}.stl")
    m.apply_transform(trimesh.transformations.rotation_matrix(math.pi, [1, 0, 0]))  # top-plate down
    m.apply_translation([0, 0, -m.bounds[0][2]])
    n, c = m.face_normals, m.triangles_center
    bad = (n[:, 2] < -1e-3) & (c[:, 2] > 0.6) & \
          (np.degrees(np.arccos(np.clip(np.abs(n[:, 2]), 0, 1))) < 45)
    print(f"  printability (top-plate down, cavity up): overhang faces={int(bad.sum())} "
          f"area={m.area_faces[bad].sum():.1f} mm^2 of {m.area:.0f}")


if __name__ == "__main__":
    xt = build_xt60()
    export_step(xt, "xt60.step"); export_stl(xt, "xt60.stl", tolerance=0.01, angular_tolerance=0.1)
    print("exported xt60.step / xt60.stl")
    for prefix, slim, inset in VARIANTS:
        verify_export(prefix, slim, inset)
        top_view(prefix, slim, inset); section_view(prefix); printability(prefix)
    print("\n4 variants: cap_dev / cap_sleek (inset, short screw) + cap_dev_long / cap_sleek_long (no inset, long screw)")
