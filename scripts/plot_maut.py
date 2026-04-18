"""MAUT piecewise linear + comparaison ELECTRE III.

Multi-Attribute Utility Theory (Keeney & Raiffa 1976), école américaine
compensatoire, appliquée aux 8 configurations alpha. Fonctions d'utilité
marginales piecewise linear calibrées à partir de points d'ancrage
substantifs (seuil SLA, plancher inacceptable, cible idéale).

3 panels :
  1. Les 6 fonctions u_j(g_j) avec les 8 configs projetées
  2. Score u(a) trié — classement MAUT
  3. Scatter rang MAUT vs rang ELECTRE III — convergence / divergence
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
from matplotlib.gridspec import GridSpec

sys.path.insert(0, str(Path(__file__).parent))
from electre_iii import (
    NAMES, PERF, WEIGHTS,
    build_credibility_matrix, distillation_descendante,
    distillation_ascendante, final_ranking,
)

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["DejaVu Serif", "Georgia", "Times New Roman"],
    "font.size": 9.5,
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
TEAL = "#0D9488"
ORANGE = "#EA580C"

# Points d'ancrage piecewise linear (substantifs)
ANCHORS = [
    # VF (max) — seuil SLA 85%
    {"name": "VF accuracy (%)",    "direction": 1,
     "pts": [(80, 0), (83, 30), (85, 60), (87, 85), (90, 100)]},
    # CAT (max)
    {"name": "Cat accuracy (%)",   "direction": 1,
     "pts": [(85, 0), (89, 30), (92, 70), (94, 90), (95, 100)]},
    # STRAT (max)
    {"name": "Strat accuracy (%)", "direction": 1,
     "pts": [(94, 0), (96, 40), (97.5, 75), (98.5, 95), (99, 100)]},
    # COST (min) — convexe décroissante
    {"name": "Coût total ($)",     "direction": -1,
     "pts": [(2, 100), (3, 80), (4, 60), (5, 40), (6, 25), (8, 0)]},
    # FIAB (max)
    {"name": "Fiabilité",          "direction": 1,
     "pts": [(0.90, 0), (0.97, 50), (0.99, 80), (1.00, 100)]},
    # NbAPI (min)
    {"name": "Nb appels API / post", "direction": -1,
     "pts": [(1, 100), (2, 70), (3, 40), (4, 0)]},
]

OUT = "/Users/mathias/Desktop/mémoire-v2/docs"


def u_piecewise(value, anchor):
    pts = anchor["pts"]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return float(np.interp(value, xs, ys))


def maut_score(perf_row):
    s = 0.0
    for j, anchor in enumerate(ANCHORS):
        u = u_piecewise(perf_row[j], anchor)
        s += WEIGHTS[j] * u
    return s


def main():
    n_alt = len(NAMES)
    n_crit = len(ANCHORS)

    u_marginals = np.zeros((n_alt, n_crit))
    for i in range(n_alt):
        for j in range(n_crit):
            u_marginals[i, j] = u_piecewise(PERF[i, j], ANCHORS[j])

    maut_scores = np.array([maut_score(PERF[i]) for i in range(n_alt)])

    order_maut = np.argsort(-maut_scores)
    rank_maut = {a: r + 1 for r, a in enumerate(order_maut)}

    S = build_credibility_matrix()
    desc = distillation_descendante(S)
    asc = distillation_ascendante(S)
    final = final_ranking(desc, asc)
    rank_electre = {a: i + 1 for i, (_, a) in enumerate(final)}

    # ── Figure ─────────────────────────────────────────────────────────

    fig = plt.figure(figsize=(18, 11))
    gs = GridSpec(3, 3, figure=fig, hspace=0.55, wspace=0.32,
                  left=0.06, right=0.97, top=0.93, bottom=0.07,
                  height_ratios=[1, 1, 1.1])

    # ── Panel A : 6 fonctions u_j piecewise (2x3 grid) ──────────────

    for j, anchor in enumerate(ANCHORS):
        row = j // 3
        col = j % 3
        ax = fig.add_subplot(gs[row, col])
        ax.set_axisbelow(True)
        ax.grid(True, color="#E5E7EB", linewidth=0.5, alpha=0.7)

        pts = anchor["pts"]
        xs = np.array([p[0] for p in pts])
        ys = np.array([p[1] for p in pts])

        x_fine = np.linspace(xs.min(), xs.max(), 200)
        y_fine = np.array([u_piecewise(x, anchor) for x in x_fine])
        ax.plot(x_fine, y_fine, color=BLUE_DARK, linewidth=2.0, zorder=3)
        ax.scatter(xs, ys, s=80, color=BLUE, edgecolor="white",
                   linewidth=1.5, zorder=5, label="ancrages")

        vals = PERF[:, j]
        u_vals = np.array([u_piecewise(v, anchor) for v in vals])
        ax.scatter(vals, u_vals, s=90, marker="X", color=ORANGE,
                   edgecolor="white", linewidth=1.2, zorder=6,
                   label="configs observées")

        ax.set_title(f"$u_{{{j+1}}}$ : {anchor['name']}",
                     fontsize=10.5, fontweight="bold", pad=6)
        ax.set_ylabel("Utilité  $u_j$  [0–100]", fontsize=9)
        ax.set_xlabel(anchor["name"], fontsize=9)
        ax.set_ylim(-5, 108)

        for x_ancr, y_ancr in pts:
            ax.plot([x_ancr, x_ancr], [0, y_ancr], color=GREY,
                    linestyle=":", linewidth=0.5, alpha=0.5, zorder=2)

    # ── Panel B : scores MAUT trié (row 2, span 2 cols) ──────────────

    axB = fig.add_subplot(gs[2, :2])
    axB.set_axisbelow(True)
    axB.grid(axis="x", color="#E5E7EB", linewidth=0.5, alpha=0.7)

    order = order_maut
    names_sorted = [NAMES[a] for a in order]
    scores_sorted = maut_scores[order]

    colors = []
    for s in scores_sorted:
        if s == scores_sorted[0]:
            colors.append(GREEN)
        elif s >= scores_sorted[0] - 5:
            colors.append(TEAL)
        elif s >= scores_sorted[0] - 15:
            colors.append(AMBER)
        else:
            colors.append(GREY)

    y_pos = np.arange(n_alt)
    bars = axB.barh(y_pos, scores_sorted, color=colors, edgecolor="white",
                    linewidth=1.0, zorder=3)

    for i, (bar, s, a) in enumerate(zip(bars, scores_sorted, order)):
        axB.text(bar.get_width() + 1, bar.get_y() + bar.get_height() / 2,
                 f"u = {s:.1f}    (ELECTRE rang {rank_electre[a]})",
                 va="center", ha="left", fontsize=8.5, color=SLATE,
                 fontweight="bold")

    axB.set_yticks(y_pos)
    axB.set_yticklabels([f"{i+1}. {n}" for i, n in enumerate(names_sorted)],
                       fontsize=9)
    axB.invert_yaxis()
    axB.set_xlabel(r"Score MAUT  $u(a) = \sum_j w_j \cdot u_j(g_j(a))$",
                   fontsize=10.5, labelpad=6)
    axB.set_title("Classement MAUT additif (compensatoire)",
                  fontsize=11.5, fontweight="bold", pad=10)
    axB.set_xlim(0, max(scores_sorted) * 1.35)

    # ── Panel C : scatter rang MAUT vs rang ELECTRE ───────────────────

    axC = fig.add_subplot(gs[2, 2])
    axC.set_axisbelow(True)
    axC.grid(True, color="#E5E7EB", linewidth=0.5, alpha=0.7)

    axC.plot([0, n_alt + 1], [0, n_alt + 1], color=GREY, linewidth=1.2,
             linestyle="--", alpha=0.6, zorder=2, label="accord parfait")

    for a in range(n_alt):
        r_m = rank_maut[a]
        r_e = rank_electre[a]
        agree = r_m == r_e
        col = GREEN if agree else RED
        axC.scatter(r_m, r_e, s=150, color=col, edgecolor="white",
                    linewidth=1.5, zorder=5, alpha=0.85)
        short = NAMES[a].replace("flash-lite", "fl")
        short = short.replace("no-assist", "no-a").replace("ASSIST", "ast")
        dx, dy = (0.15, 0.15) if agree else (0.2, -0.25)
        axC.annotate(short, (r_m, r_e), xytext=(dx, dy),
                     textcoords="offset points", fontsize=7.5, color=SLATE)

    axC.set_xlabel("Rang MAUT", fontsize=10.5, labelpad=6)
    axC.set_ylabel("Rang ELECTRE III", fontsize=10.5, labelpad=6)
    axC.set_title("Convergence des deux écoles",
                  fontsize=11.5, fontweight="bold", pad=10)
    axC.set_xlim(0.3, n_alt + 0.7)
    axC.set_ylim(0.3, n_alt + 0.7)
    axC.set_xticks(range(1, n_alt + 1))
    axC.set_yticks(range(1, n_alt + 1))
    axC.invert_yaxis()
    axC.legend(loc="lower right", fontsize=8, framealpha=0.95,
               edgecolor="#ddd", fancybox=False)

    # ── Global ────────────────────────────────────────────────────────

    fig.suptitle(
        "Multi-Attribute Utility Theory (MAUT) — 8 configurations alpha",
        fontsize=14, fontweight="bold", y=0.98, color="#1E293B",
    )

    fig.savefig(f"{OUT}/ablation_alpha_maut.png", dpi=300, bbox_inches="tight",
                facecolor="white")
    fig.savefig(f"{OUT}/ablation_alpha_maut.pdf", bbox_inches="tight",
                facecolor="white")
    print(f"  -> {OUT}/ablation_alpha_maut.png")
    print(f"  -> {OUT}/ablation_alpha_maut.pdf")

    print("\nClassement MAUT :")
    for r, a in enumerate(order_maut):
        print(f"  {r+1}. {NAMES[a]:30s}  u={maut_scores[a]:.2f}  "
              f"(ELECTRE rang {rank_electre[a]})")

    agreements = sum(1 for a in range(n_alt) if rank_maut[a] == rank_electre[a])
    print(f"\nAccords MAUT-ELECTRE : {agreements}/{n_alt}")
    plt.close(fig)


if __name__ == "__main__":
    main()
