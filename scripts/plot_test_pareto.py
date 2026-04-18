"""Frontière de Pareto coût/post vs accuracy VF — dataset test.

Reprend le style de plot_best.py (alpha) mais :
- axe X : coût par post (¢/post) au lieu de coût total
- 7 runs Google AI + run 185 normalisé cache-off (~$5.21) pour neutraliser
  l'activation du context caching implicite survenue pendant la session.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.ticker as mticker
import numpy as np
from matplotlib.gridspec import GridSpec

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
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
})

BLUE = "#2563EB"
BLUE_DARK = "#1E40AF"
GREY = "#9CA3AF"
RED = "#DC2626"
GREEN = "#059669"
AMBER = "#D97706"
SLATE = "#475569"

# (run_id, label, vf%, cost_usd_total, n_posts, is_pareto, is_normalized)
RUNS = [
    (178, "alma qwen",                   83.81, 2.36, 383, True,  False),
    (172, "alma flash-lite",             82.72, 3.94, 405, False, False),
    (177, "simple fl-lite\nsans ASSIST", 87.16, 3.22, 405, True,  False),
    (176, "simple fl-lite\nASSIST",      86.91, 3.45, 405, False, False),
    (182, "alma flash",                  88.15, 4.96, 405, True,  False),
    (185, "simple flash\nsans ASSIST",   87.59, 5.21, 403, False, True),   # prorata cache-off
    (181, "simple flash\nASSIST",        89.58, 5.49, 403, True,  False),
    (183, "alma full-flash",             85.19, 7.83, 405, False, False),
]

OUT = "/Users/mathias/Desktop/mémoire-v2/docs"


def main():
    fig = plt.figure(figsize=(14, 6.2))
    gs = GridSpec(1, 2, width_ratios=[2.2, 1], wspace=0.35, left=0.07, right=0.96,
                  top=0.88, bottom=0.12)

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])

    # Enrichir avec coût par post
    runs_enriched = []
    for run_id, label, vf, cost_total, n_posts, is_pareto, is_norm in RUNS:
        cents_per_post = 100 * cost_total / n_posts
        runs_enriched.append((run_id, label, vf, cost_total, n_posts,
                              is_pareto, is_norm, cents_per_post))

    # Frontière Pareto triée par coût croissant
    pareto_points = sorted(
        [(r[7], r[2]) for r in runs_enriched if r[5]]
    )

    # ── Panel 1 : Pareto ─────────────────────────────────────────────────

    ax1.set_axisbelow(True)
    ax1.grid(True, color="#E5E7EB", linewidth=0.5, alpha=0.7)

    # Ligne frontière
    px, py = zip(*pareto_points)
    ax1.plot(px, py, color=RED, linestyle="--", linewidth=2.0, alpha=0.6, zorder=2)

    # Zone dominée (sous la frontière)
    ax1.fill_between(
        [px[0] - 0.1] + list(px) + [px[-1] + 0.3],
        [py[0]] + list(py) + [py[-1]],
        [80] * (len(px) + 2),
        alpha=0.04, color=RED, zorder=1,
    )

    for run_id, label, vf, cost, n_posts, is_pareto, is_norm, cpp in runs_enriched:
        if is_pareto:
            ax1.scatter(cpp, vf, s=200, marker="o", facecolor=BLUE,
                       edgecolor=BLUE_DARK, linewidth=1.2, zorder=5)
        else:
            # Marqueur spécial pour le run normalisé
            if is_norm:
                ax1.scatter(cpp, vf, s=140, marker="D", color=AMBER,
                           edgecolor="white", linewidth=1.5, zorder=4)
            else:
                ax1.scatter(cpp, vf, s=130, marker="X", color=GREY,
                           linewidths=1.5, zorder=4)

    label_config = {
        178: {"offset": (-12, -10), "ha": "right"},
        172: {"offset": (10, -10), "ha": "left"},
        177: {"offset": (-10, 10), "ha": "right"},
        176: {"offset": (10, -12), "ha": "left"},
        182: {"offset": (-12, 10), "ha": "right"},
        185: {"offset": (12, -10), "ha": "left"},
        181: {"offset": (8, 10), "ha": "left"},
        183: {"offset": (-8, 4), "ha": "right"},
    }

    for run_id, label, vf, cost, n_posts, is_pareto, is_norm, cpp in runs_enriched:
        cfg = label_config[run_id]
        color = BLUE_DARK if is_pareto else (AMBER if is_norm else SLATE)
        weight = "bold" if is_pareto else "normal"
        size = 8.5 if is_pareto else 7.5

        label_text = f"{label}\n({run_id})"
        if is_norm:
            label_text += "*"

        txt = ax1.annotate(
            label_text,
            xy=(cpp, vf),
            xytext=cfg["offset"],
            textcoords="offset points",
            ha=cfg["ha"], va="center",
            fontsize=size, color=color, fontweight=weight,
            linespacing=0.9,
        )
        txt.set_path_effects([pe.withStroke(linewidth=3, foreground="white")])

    # Rendements marginaux sur la frontière
    for i in range(len(pareto_points) - 1):
        x0, y0 = pareto_points[i]
        x1, y1 = pareto_points[i + 1]
        delta_cost = x1 - x0
        delta_vf = y1 - y0
        marginal = delta_cost / delta_vf if delta_vf > 0 else float("inf")

        mid_x = (x0 + x1) / 2
        mid_y = (y0 + y1) / 2

        ax1.annotate(
            f"{marginal:.2f}¢/pp",
            xy=(mid_x, mid_y),
            xytext=(0, -18),
            textcoords="offset points",
            ha="center", va="top",
            fontsize=8, color=RED, fontweight="bold",
            fontstyle="italic",
            bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                     edgecolor=RED, alpha=0.9, linewidth=0.8),
        )

    ax1.set_xlabel("Coût par post (¢/post)", fontsize=11.5, labelpad=8)
    ax1.set_ylabel("Accuracy Visual Format (%)", fontsize=11.5, labelpad=8)
    ax1.set_title("Frontière de Pareto coût-performance",
                  fontsize=13, fontweight="bold", pad=12)

    ax1.set_xlim(0.4, 2.1)
    ax1.set_ylim(81, 91)
    ax1.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))

    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=BLUE,
               markeredgecolor=BLUE_DARK, markersize=10, label="Pareto-optimal"),
        Line2D([0], [0], marker="X", color=GREY, markersize=9,
               linewidth=0, markeredgewidth=1.5, label="Dominé"),
        Line2D([0], [0], marker="D", color=AMBER, markersize=9,
               linewidth=0, markeredgewidth=1.5,
               label="* coût normalisé cache-off"),
        Line2D([0], [0], linestyle="--", color=RED, linewidth=2,
               alpha=0.6, label="Frontière efficiente"),
    ]
    ax1.legend(handles=legend_elements, loc="lower right", fontsize=8.5,
              framealpha=0.95, edgecolor="#ddd", fancybox=False)

    # ── Panel 2 : Rendements marginaux pairés ────────────────────────────

    ax2.set_axisbelow(True)
    ax2.grid(axis="x", color="#E5E7EB", linewidth=0.5, alpha=0.7)

    transitions = []
    for i in range(len(pareto_points) - 1):
        x0, y0 = pareto_points[i]
        x1, y1 = pareto_points[i + 1]
        delta_vf = y1 - y0
        delta_cost = x1 - x0
        marginal = delta_cost / delta_vf if delta_vf > 0 else float("inf")
        transitions.append({
            "delta_vf": delta_vf,
            "delta_cost": delta_cost,
            "marginal": marginal,
        })

    pareto_labels_short = ["qwen", "fl-lite no-A", "flash", "flash ASSIST"]
    bar_labels = [
        f"{pareto_labels_short[i]}\n-> {pareto_labels_short[i+1]}"
        for i in range(len(transitions))
    ]
    marginals = [t["marginal"] for t in transitions]
    delta_vfs = [t["delta_vf"] for t in transitions]
    delta_costs = [t["delta_cost"] for t in transitions]

    y_pos = np.arange(len(transitions))
    palette = [GREEN, AMBER, RED]
    colors = [palette[min(i, len(palette) - 1)] for i in range(len(transitions))]

    bars = ax2.barh(y_pos, marginals, height=0.5, color=colors, edgecolor="white",
                    linewidth=1.5, zorder=3)

    for i, (bar, m, dv, dc) in enumerate(zip(bars, marginals, delta_vfs, delta_costs)):
        ax2.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height() / 2,
                f"{m:.2f}¢/pp\n+{dv:.1f}pp pour +{dc:.2f}¢",
                va="center", ha="left", fontsize=8.5, color=colors[i],
                fontweight="bold", linespacing=1.3)

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels(bar_labels, fontsize=8.5)
    ax2.set_xlabel("Coût marginal par point (¢/pp)", fontsize=11, labelpad=8)
    ax2.set_title("Rendements marginaux\ndécroissants",
                  fontsize=13, fontweight="bold", pad=12)
    ax2.invert_yaxis()

    xmax = max(marginals) * 1.8
    ax2.set_xlim(0, xmax)

    if len(marginals) >= 2:
        ratio = marginals[-1] / marginals[0]
        ax2.annotate(
            f"×{ratio:.1f}",
            xy=(0.6, 0.5), fontsize=22, fontweight="bold",
            color=SLATE, ha="center", va="center",
            xycoords="axes fraction", alpha=0.15,
        )

    # ── Global ───────────────────────────────────────────────────────────

    fig.suptitle(
        "Ablation test — 8 configurations, 405 posts",
        fontsize=14.5, fontweight="bold", y=0.97, color="#1E293B",
    )

    fig.savefig(f"{OUT}/ablation_test_main.png", dpi=300, bbox_inches="tight",
               facecolor="white")
    fig.savefig(f"{OUT}/ablation_test_main.pdf", bbox_inches="tight",
               facecolor="white")
    print(f"  -> {OUT}/ablation_test_main.png")
    print(f"  -> {OUT}/ablation_test_main.pdf")
    plt.close(fig)


if __name__ == "__main__":
    main()
