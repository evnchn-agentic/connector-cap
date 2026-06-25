"""Shaded top + bottom renders of each cap variant for mobile review.
matplotlib Poly3DCollection with light-based face shading. No GL deps.
Writes render_<prefix>_top.png / _bottom.png for every VARIANT."""
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import trimesh
import build_cap as B


def shade(mesh, base_rgb, light=(0.4, -0.5, 0.8)):
    L = np.array(light, float); L /= np.linalg.norm(L)
    b = np.clip(mesh.face_normals @ L, 0, 1) * 0.7 + 0.3
    return np.array(base_rgb)[None, :] * b[:, None]


def render(prefix, view, fname, title):
    cap = trimesh.load(f"{prefix}.stl")
    fig = plt.figure(figsize=(7.5, 6)); ax = fig.add_subplot(111, projection="3d")
    tris = cap.vertices[cap.faces]
    ax.add_collection3d(Poly3DCollection(tris, facecolors=shade(cap, (0.62, 0.72, 0.90)),
                        edgecolors=(0, 0, 0, 0.08), linewidths=0.1))
    v = cap.vertices
    ax.set_xlim(v[:, 0].min(), v[:, 0].max()); ax.set_ylim(v[:, 1].min(), v[:, 1].max())
    ax.set_zlim(v[:, 2].min(), v[:, 2].max())
    ax.set_box_aspect((B.TOP_W, B.DEPTH, B.THICK)); ax.view_init(elev=view[0], azim=view[1])
    ax.set_axis_off(); ax.set_title(title, color="#e6e6e6", fontsize=12)
    fig.patch.set_facecolor("#1b1b1f")
    fig.savefig(fname, dpi=150, facecolor="#1b1b1f", bbox_inches="tight"); plt.close(fig)
    print("wrote", fname)


if __name__ == "__main__":
    for prefix, slim, inset in B.VARIANTS:
        tag = ("SLEEK slim" if slim else "DEV full-RJ45") + ("" if inset else " LONG")
        render(prefix, (72, -90), f"render_{prefix}_top.png", f"{tag} — TOP (windows, counterbores)")
        render(prefix, (-72, -90), f"render_{prefix}_bottom.png", f"{tag} — BOTTOM (cavity, bosses)")
