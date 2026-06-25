"""TRUE 1:1 top-view PDF per variant for physical overlay calibration.
Print at 100% (NO 'fit to page'); lay the real cap on it; mismatch reads in mm."""
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import build_cap as B

MARGIN = 6
xr, yr = B.TOP_W/2 + MARGIN, B.DEPTH/2 + MARGIN


def pdf(prefix, slim, inset):
    fig = plt.figure(figsize=((2*xr)/25.4, (2*yr)/25.4))
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(-xr, xr); ax.set_ylim(-yr, yr)
    ax.set_aspect("equal"); ax.axis("off")
    p = np.array(B.trap_pts(B.TOP_W, B.BOT_W, B.DEPTH) + [B.trap_pts(B.TOP_W, B.BOT_W, B.DEPTH)[0]])
    ax.plot(p[:, 0], p[:, 1], "k-", lw=1.0)
    wp = B.xt60_window_pts(); ax.plot(wp[:, 0], wp[:, 1], "-", color="#c0392b", lw=1.0)
    if slim:
        sx_l, sx_r = B.XT_CX, B.ETH_SLOT_CX + B.CABLE_W/2 - B.SLOT_SHORTER
        ax.add_patch(plt.Rectangle((sx_l, B.ETH_SLOT_CY-B.CABLE_T/2), sx_r - sx_l, B.CABLE_T, fill=False, ec="#2980b9", lw=1.0))
    else:
        ax.add_patch(plt.Rectangle((B.ETH_CX-B.ETH_W/2, B.ETH_CY-B.ETH_H/2), B.ETH_W, B.ETH_H, fill=False, ec="#2980b9", lw=1.0))
    for sx, sy in B.SCREWS:
        if inset:
            ax.add_patch(plt.Circle((sx, sy), B.BORE_D/2, fill=False, ec="#2c3e50", lw=1.0))
        ax.add_patch(plt.Circle((sx, sy), B.SCREW_D/2, fill=False, ec="#2c3e50", lw=1.0))
        ax.plot([sx-2.5, sx+2.5], [sy, sy], color="#2c3e50", lw=0.5)
        ax.plot([sx, sx], [sy-2.5, sy+2.5], color="#2c3e50", lw=0.5)
    bx, by = -xr+2, -yr+2
    ax.plot([bx, bx+10], [by, by], "k-", lw=2)
    ax.plot([bx, bx], [by-.6, by+.6], "k-", lw=2); ax.plot([bx+10, bx+10], [by-.6, by+.6], "k-", lw=2)
    ax.text(bx+5, by+.8, "10 mm", ha="center", va="bottom", fontsize=5)
    fig.savefig(f"{prefix}_1to1.pdf"); plt.close(fig)
    print(f"wrote {prefix}_1to1.pdf")


if __name__ == "__main__":
    for prefix, slim, inset in B.VARIANTS:
        pdf(prefix, slim, inset)
