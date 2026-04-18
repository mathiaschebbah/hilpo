"""Figure théorique micro-éco : C(q) power-law + CM(q)/Cm(q).

Paramétrisation GPT-5.4 calibrée exactement sur les 3 points Pareto :
  C(q) = F + a q^gamma  avec F=2.3047, a=0.001650, gamma=3.628

Propriétés vérifiées :
- C'(q) > 0 (coût croissant)
- C''(q) > 0 (rendements décroissants)
- CM(q) en U, minimum où CM = Cm
- q* ≈ 5.64, CM(q*) = Cm(q*) ≈ 0.564 $/pp
- Run 165 à q=5.4 est très proche du minimum théorique
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
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
})

BLUE = "#2563EB"
BLUE_DARK = "#1E40AF"
GREY = "#9CA3AF"
RED = "#DC2626"
GREEN = "#059669"
AMBER = "#D97706"
SLATE = "#475569"
PURPLE = "#7C3AED"

F = 2.3047
A = 0.001650
GAMMA = 3.628

Q_STAR = 5.64
CM_STAR = 0.564

RUNS = [
    (161, "alma qwen",                82.2, 2.33, True),
    (165, "simple fl-lite\nsans ASSIST", 85.4, 3.05, True),
    (164, "simple fl-lite\nASSIST",      84.9, 3.25, False),
    (158, "alma flash-lite",          83.8, 3.67, False),
    (159, "alma flash",               83.6, 4.62, False),
    (167, "simple flash\nsans ASSIST",   85.3, 4.92, False),
    (171, "simple flash\nASSIST",        87.8, 5.18, True),
    (160, "alma full-flash",          86.7, 7.72, False),
]

OUT = "/Users/mathias/Desktop/mémoire-v2/docs"


def C(q):
    return F + A * np.power(q, GAMMA)


def CM(q):
    return F / q + A * np.power(q, GAMMA - 1)


def Cm(q):
    return A * GAMMA * np.power(q, GAMMA - 1)


def main():
    fig = plt.figure(figsize=(15, 6.2))
    gs = GridSpec(1, 2, width_ratios=[1, 1], wspace=0.28, left=0.06, right=0.97,
                  top=0.86, bottom=0.13)

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])

    # ── Panel 1 : C(q) courbe continue + points ──────────────────────────

    ax1.set_axisbelow(True)
    ax1.grid(True, color="#E5E7EB", linewidth=0.5, alpha=0.7)

    q_range = np.linspace(1.5, 8.5, 400)
    C_theo = C(q_range)
    ax1.plot(q_range, C_theo, color=BLUE_DARK, linewidth=2.2, zorder=3,
             label=r"$C(q) = 2.305 + 0.00165\,q^{3.63}$")

    for run_id, label, vf, cost, is_pareto in RUNS:
        q = vf - 80
        if is_pareto:
            ax1.scatter(q, cost, s=200, marker="o", facecolor=BLUE,
                       edgecolor=BLUE_DARK, linewidth=1.5, zorder=6)
        else:
            ax1.scatter(q, cost, s=130, marker="X", color=GREY,
                       linewidths=1.5, zorder=5)

    label_config = {
        161: {"offset": (-10, -18), "ha": "right"},
        165: {"offset": (-12, 10), "ha": "right"},
        164: {"offset": (10, -2), "ha": "left"},
        158: {"offset": (10, 4), "ha": "left"},
        159: {"offset": (10, -6), "ha": "left"},
        167: {"offset": (10, -8), "ha": "left"},
        171: {"offset": (-10, 10), "ha": "right"},
        160: {"offset": (-10, 4), "ha": "right"},
    }

    for run_id, label, vf, cost, is_pareto in RUNS:
        q = vf - 80
        cfg = label_config[run_id]
        color = BLUE_DARK if is_pareto else SLATE
        weight = "bold" if is_pareto else "normal"
        size = 8.5 if is_pareto else 7.5

        txt = ax1.annotate(
            f"{label}\n({run_id})",
            xy=(q, cost),
            xytext=cfg["offset"],
            textcoords="offset points",
            ha=cfg["ha"], va="center",
            fontsize=size, color=color, fontweight=weight,
            linespacing=0.9,
        )
        txt.set_path_effects([pe.withStroke(linewidth=3, foreground="white")])

    ax1.set_xlabel("q = accuracy VF − 80 (points de pourcentage)", fontsize=11.5, labelpad=8)
    ax1.set_ylabel("Coût total C(q) (USD)", fontsize=11.5, labelpad=8)
    ax1.set_title("Fonction de coût théorique — calibration sur 3 points Pareto",
                  fontsize=12.5, fontweight="bold", pad=12)

    ax1.set_xlim(1.5, 8.5)
    ax1.set_ylim(2, 8.5)

    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], color=BLUE_DARK, linewidth=2.2,
               label=r"$C(q) = F + aq^{\gamma}$ (calibré)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=BLUE,
               markeredgecolor=BLUE_DARK, markersize=10, label="Pareto-optimal"),
        Line2D([0], [0], marker="X", color=GREY, markersize=9,
               linewidth=0, markeredgewidth=1.5, label="Dominé (au-dessus)"),
    ]
    ax1.legend(handles=legend_elements, loc="upper left", fontsize=9,
              framealpha=0.95, edgecolor="#ddd", fancybox=False)

    ax1.text(0.98, 0.05,
             "F = 2.305  ·  a = 1.65×10⁻³  ·  γ = 3.63\nC′(q) > 0  ·  C″(q) > 0",
             transform=ax1.transAxes, ha="right", va="bottom",
             fontsize=8.5, color=SLATE, style="italic",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                      edgecolor="#ddd", linewidth=0.6))

    # ── Panel 2 : CM(q) et Cm(q) ─────────────────────────────────────────

    ax2.set_axisbelow(True)
    ax2.grid(True, color="#E5E7EB", linewidth=0.5, alpha=0.7)

    q_micro = np.linspace(1.5, 8.5, 400)
    CM_theo = CM(q_micro)
    Cm_theo = Cm(q_micro)

    ax2.plot(q_micro, CM_theo, color=BLUE_DARK, linewidth=2.3, zorder=4,
             label=r"CM(q) = $F/q + aq^{\gamma-1}$")
    ax2.plot(q_micro, Cm_theo, color=RED, linewidth=2.3, zorder=4, linestyle="-",
             label=r"Cm(q) = $a\gamma\, q^{\gamma-1}$")

    ax2.axvline(Q_STAR, color=GREEN, linestyle=":", linewidth=1.5, alpha=0.7, zorder=2)
    ax2.scatter([Q_STAR], [CM_STAR], s=180, marker="*", color=GREEN,
                edgecolor="white", linewidth=1.5, zorder=7,
                label=f"q* = {Q_STAR:.2f}  ·  CM(q*) = Cm(q*) = {CM_STAR:.3f}")

    ax2.annotate(
        f"Minimum de CM\nq* = {Q_STAR:.2f}",
        xy=(Q_STAR, CM_STAR),
        xytext=(Q_STAR - 1.2, CM_STAR + 0.4),
        fontsize=9, color=GREEN, fontweight="bold",
        ha="right", va="bottom",
        arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.2,
                       connectionstyle="arc3,rad=-0.2"),
        bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                 edgecolor=GREEN, alpha=0.9, linewidth=0.8),
    )

    for run_id, label, vf, cost, is_pareto in RUNS:
        if not is_pareto:
            continue
        q = vf - 80
        cm_val = cost / q
        ax2.scatter(q, cm_val, s=140, marker="o", facecolor=BLUE,
                   edgecolor=BLUE_DARK, linewidth=1.5, zorder=6)
        short = {161: "alma qwen", 165: "simple fl-lite\nsans ASSIST", 171: "simple flash\nASSIST"}[run_id]
        offset = {161: (10, 10), 165: (12, -20), 171: (-10, 12)}[run_id]
        ha = {161: "left", 165: "left", 171: "right"}[run_id]
        txt = ax2.annotate(
            f"{short}\nCM = {cm_val:.3f}",
            xy=(q, cm_val),
            xytext=offset,
            textcoords="offset points",
            fontsize=8, color=BLUE_DARK, fontweight="bold",
            ha=ha, va="center", linespacing=0.95,
        )
        txt.set_path_effects([pe.withStroke(linewidth=3, foreground="white")])

    ax2.set_xlabel("q = accuracy VF − 80 (points de pourcentage)", fontsize=11.5, labelpad=8)
    ax2.set_ylabel("Coût moyen / marginal ($/pp)", fontsize=11.5, labelpad=8)
    ax2.set_title("Coût moyen et coût marginal — CM(q*) = Cm(q*)",
                  fontsize=12.5, fontweight="bold", pad=12)

    ax2.set_xlim(1.5, 8.5)
    ax2.set_ylim(0, 2.2)
    ax2.legend(loc="upper right", fontsize=8.8, framealpha=0.95,
              edgecolor="#ddd", fancybox=False)

    ax2.text(0.02, 0.97,
             "CM en U\nCm croissante\nCM = Cm au minimum",
             transform=ax2.transAxes, ha="left", va="top",
             fontsize=8.5, color=SLATE, style="italic",
             bbox=dict(boxstyle="round,pad=0.4", facecolor="white",
                      edgecolor="#ddd", linewidth=0.6))

    # ── Global ───────────────────────────────────────────────────────────

    fig.suptitle(
        "Ablation alpha (390 posts) — lecture microéconomique : rendements décroissants",
        fontsize=14, fontweight="bold", y=0.97, color="#1E293B",
    )

    fig.savefig(f"{OUT}/ablation_alpha_theoretical.png", dpi=300, bbox_inches="tight",
               facecolor="white")
    fig.savefig(f"{OUT}/ablation_alpha_theoretical.pdf", bbox_inches="tight",
               facecolor="white")
    print(f"  -> {OUT}/ablation_alpha_theoretical.png")
    print(f"  -> {OUT}/ablation_alpha_theoretical.pdf")
    plt.close(fig)


if __name__ == "__main__":
    main()
