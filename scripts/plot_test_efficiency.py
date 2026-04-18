"""Accuracy VF en fonction du rendement moyen (pp/¢).

Deux axes de valeur : efficience (r = pp par centime) et niveau de
performance (VF absolue). Le Pareto dans cet espace sépare naturellement
le "run le plus efficient" du "run le plus précis".
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["DejaVu Serif", "Georgia", "Times New Roman"],
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "axes.facecolor": "#FAFAFA",
    "savefig.dpi": 300,
    "axes.linewidth": 0.8,
})

BLUE = "#2563EB"
BLUE_DARK = "#1E40AF"
GREY = "#9CA3AF"
RED = "#DC2626"
GREEN = "#059669"
AMBER = "#D97706"
SLATE = "#475569"

# (run_id, label, vf%, cost_usd_total, n_posts, is_normalized)
RUNS = [
    (178, "alma qwen",                   83.81, 2.36, 383, False),
    (172, "alma flash-lite",             82.72, 3.94, 405, False),
    (177, "simple fl-lite\nsans ASSIST", 87.16, 3.22, 405, False),
    (176, "simple fl-lite\nASSIST",      86.91, 3.45, 405, False),
    (182, "alma flash",                  88.15, 4.96, 405, False),
    (185, "simple flash\nsans ASSIST",   87.59, 5.21, 403, True),
    (181, "simple flash\nASSIST",        89.58, 5.49, 403, False),
    (183, "alma full-flash",             85.19, 7.83, 405, False),
]

FLOOR = 80.0  # plancher VF pour calcul q = VF - 80
OUT = "/Users/mathias/Desktop/mémoire-v2/docs"


def main():
    enriched = []
    for run_id, label, vf, cost_total, n, is_norm in RUNS:
        cpp = 100 * cost_total / n          # cents per post
        q = vf - FLOOR
        r = q / cpp if cpp > 0 else 0       # rendement moyen pp/¢
        enriched.append((run_id, label, vf, cpp, r, is_norm))

    # Pareto (max r, max VF)
    pareto = []
    for a in enriched:
        dominated = False
        for b in enriched:
            if b[0] == a[0]:
                continue
            if b[4] >= a[4] and b[2] >= a[2] and (b[4] > a[4] or b[2] > a[2]):
                dominated = True
                break
        pareto.append(not dominated)

    pareto_set = {run_id for (run_id, *_), is_p in zip(enriched, pareto) if is_p}

    fig, ax = plt.subplots(figsize=(11, 6.5))
    ax.set_axisbelow(True)
    ax.grid(True, color="#E5E7EB", linewidth=0.5, alpha=0.7)

    # Frontière Pareto (lignes reliant les points Pareto par r croissant)
    pareto_pts = sorted(
        [(r, vf, rid) for (rid, _, vf, _, r, _), is_p in zip(enriched, pareto) if is_p]
    )
    if len(pareto_pts) >= 2:
        xs = [p[0] for p in pareto_pts]
        ys = [p[1] for p in pareto_pts]
        ax.plot(xs, ys, color=RED, linestyle="--", linewidth=2.0, alpha=0.6, zorder=2)

    for (run_id, label, vf, cpp, r, is_norm) in enriched:
        is_pareto = run_id in pareto_set
        if is_pareto:
            ax.scatter(r, vf, s=230, marker="o", facecolor=BLUE,
                       edgecolor=BLUE_DARK, linewidth=1.3, zorder=5)
        elif is_norm:
            ax.scatter(r, vf, s=160, marker="D", color=AMBER,
                       edgecolor="white", linewidth=1.5, zorder=4)
        else:
            ax.scatter(r, vf, s=140, marker="X", color=GREY,
                       linewidths=1.5, zorder=4)

    label_config = {
        178: {"offset": (-10, -14), "ha": "right"},
        172: {"offset": (10, 10), "ha": "left"},
        177: {"offset": (-12, 10), "ha": "right"},
        176: {"offset": (10, -12), "ha": "left"},
        182: {"offset": (10, 10), "ha": "left"},
        185: {"offset": (-10, -12), "ha": "right"},
        181: {"offset": (-10, 12), "ha": "right"},
        183: {"offset": (10, 0), "ha": "left"},
    }

    for (run_id, label, vf, cpp, r, is_norm) in enriched:
        is_pareto = run_id in pareto_set
        cfg = label_config[run_id]
        color = BLUE_DARK if is_pareto else (AMBER if is_norm else SLATE)
        weight = "bold" if is_pareto else "normal"
        size = 9 if is_pareto else 8

        label_text = f"{label}\n({run_id})"
        if is_norm:
            label_text += "*"

        txt = ax.annotate(
            label_text,
            xy=(r, vf),
            xytext=cfg["offset"],
            textcoords="offset points",
            ha=cfg["ha"], va="center",
            fontsize=size, color=color, fontweight=weight,
            linespacing=0.9,
        )
        txt.set_path_effects([pe.withStroke(linewidth=3, foreground="white")])

    ax.set_xlabel(r"Rendement moyen  $r = (VF - 80) / \mathrm{coût/post}$  (pp par centime)",
                  fontsize=11.5, labelpad=8)
    ax.set_ylabel("Accuracy Visual Format (%)", fontsize=11.5, labelpad=8)
    ax.set_title("Test — accuracy vs efficience économique",
                 fontsize=14, fontweight="bold", pad=12)

    ax.set_xlim(2, 10)
    ax.set_ylim(81, 91)

    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=BLUE,
               markeredgecolor=BLUE_DARK, markersize=11, label="Pareto-optimal"),
        Line2D([0], [0], marker="X", color=GREY, markersize=9,
               linewidth=0, markeredgewidth=1.5, label="Dominé"),
        Line2D([0], [0], marker="D", color=AMBER, markersize=9,
               linewidth=0, markeredgewidth=1.5,
               label="* coût normalisé cache-off"),
        Line2D([0], [0], linestyle="--", color=RED, linewidth=2,
               alpha=0.6, label="Frontière efficiente"),
    ]
    ax.legend(handles=legend_elements, loc="lower left", fontsize=9,
              framealpha=0.95, edgecolor="#ddd", fancybox=False)

    ax.annotate(
        "Efficience maximale\n(plus pour moins)",
        xy=(0.98, 0.05), xycoords="axes fraction",
        ha="right", va="bottom",
        fontsize=8.5, color=SLATE, style="italic",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                  edgecolor="#ddd", linewidth=0.6),
    )
    ax.annotate(
        "Performance maximale\n(quelque soit le prix)",
        xy=(0.02, 0.95), xycoords="axes fraction",
        ha="left", va="top",
        fontsize=8.5, color=SLATE, style="italic",
        bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                  edgecolor="#ddd", linewidth=0.6),
    )

    fig.savefig(f"{OUT}/ablation_test_efficiency.png", dpi=300,
                bbox_inches="tight", facecolor="white")
    fig.savefig(f"{OUT}/ablation_test_efficiency.pdf",
                bbox_inches="tight", facecolor="white")
    print(f"  -> {OUT}/ablation_test_efficiency.png")
    print(f"  -> {OUT}/ablation_test_efficiency.pdf")

    print("\nRendement moyen :")
    for rid, label, vf, cpp, r, is_norm in sorted(enriched, key=lambda x: -x[4]):
        p = "P" if rid in pareto_set else " "
        print(f"  [{p}] run {rid:<4}  r={r:5.2f} pp/¢   VF={vf:5.2f}%   cost={cpp:.2f}¢/post"
              f"{' (normalisé)' if is_norm else ''}")

    plt.close(fig)


if __name__ == "__main__":
    main()
