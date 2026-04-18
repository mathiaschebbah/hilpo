"""Figure finale 2 panneaux — style clean + rendements marginaux.

Panneau gauche : frontière de Pareto coût-performance (style propre)
Panneau droit  : coût marginal discret Cm(q) en fonction escalier
"""

from __future__ import annotations

import os
from pathlib import Path

import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import psycopg
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")
DATABASE_DSN = os.environ.get(
    "HILPO_DATABASE_DSN", "postgresql://hilpo:hilpo@localhost:5433/hilpo"
)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.dpi": 300,
    "axes.linewidth": 0.8,
    "xtick.major.width": 0.7,
    "ytick.major.width": 0.7,
    "legend.frameon": True,
    "legend.edgecolor": "#E5E7EB",
})

BLUE      = "#2563EB"
BLUE_DARK = "#1E3A8A"
GREY      = "#9CA3AF"
GREY_DARK = "#475569"
RED       = "#DC2626"
RED_DARK  = "#991B1B"
GREEN     = "#059669"
INK       = "#0F172A"


def load_runs():
    ids = (158, 159, 160, 161, 164, 165, 167, 171)
    query = """
        SELECT r.id, r.config, r.total_cost_usd,
               (SELECT count(*) FROM predictions p
                WHERE p.simulation_run_id = r.id AND p.agent = 'visual_format') AS n,
               (SELECT count(*) FROM predictions p
                WHERE p.simulation_run_id = r.id
                  AND p.agent = 'visual_format' AND p.match) AS correct
        FROM simulation_runs r
        WHERE r.id = ANY(%s)
        ORDER BY r.total_cost_usd
    """
    with psycopg.connect(DATABASE_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (list(ids),))
            rows = cur.fetchall()

    runs = []
    for rid, cfg, cost, n, correct in rows:
        pct = 100.0 * correct / n
        name = cfg.get("name", "")
        mode = cfg.get("pipeline_mode", "?").capitalize()
        tier = cfg.get("model_tier", "?")
        # Format nom
        tier_map = {"flash-lite": "Flash-Lite", "flash": "Flash",
                    "full-flash": "Full-Flash", "qwen": "Qwen"}
        tier_label = tier_map.get(tier, tier.capitalize())
        label = f"{mode} {tier_label}"
        if mode == "Simple" and "no_assist" in name:
            label += "\nSans ASSIST"
        runs.append({
            "id": rid, "label": label,
            "cost": float(cost), "vf": pct, "n": n,
        })
    return runs


def pareto_frontier(runs):
    pareto = []
    for a in runs:
        dominated = False
        for b in runs:
            if a["id"] == b["id"]:
                continue
            if b["cost"] <= a["cost"] and b["vf"] >= a["vf"] and (
                b["cost"] < a["cost"] or b["vf"] > a["vf"]
            ):
                dominated = True
                break
        if not dominated:
            pareto.append(a)
    return sorted(pareto, key=lambda r: r["cost"])


def make_plot(runs, pareto, out_path):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6.5),
                                     gridspec_kw={"width_ratios": [1.6, 1]})

    # ══════════════════════════════════════════════════════════════════════
    # PANNEAU GAUCHE : Frontière de Pareto coût-performance
    # ══════════════════════════════════════════════════════════════════════

    ax1.set_axisbelow(True)
    ax1.grid(True, color="#F1F5F9", linewidth=0.6)

    # Frontière piecewise linéaire
    px = [r["cost"] for r in pareto]
    py = [r["vf"] for r in pareto]
    ax1.plot(px, py, color=RED, linestyle="--", linewidth=2.2, zorder=3, alpha=0.75)

    # Annotations coût marginal sur chaque segment
    for i in range(len(pareto) - 1):
        a, b = pareto[i], pareto[i + 1]
        dc = b["cost"] - a["cost"]
        dv = b["vf"] - a["vf"]
        cm = dc / dv
        mx = (a["cost"] + b["cost"]) / 2
        my = (a["vf"] + b["vf"]) / 2

        txt = ax1.annotate(
            f"Cm = \\${cm:.2f}/pp",
            xy=(mx, my),
            xytext=(0, -22),
            textcoords="offset points",
            ha="center", va="top",
            fontsize=9.5, color=RED_DARK, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor=RED, linewidth=0.9, alpha=0.95),
            zorder=6,
        )

    # Points
    for r in runs:
        is_pareto = any(p["id"] == r["id"] for p in pareto)
        if is_pareto:
            ax1.scatter(r["cost"], r["vf"], s=180, marker="o",
                       facecolor=BLUE, edgecolor=BLUE_DARK, linewidth=1.3,
                       zorder=5, label="_nolegend_")
        else:
            ax1.scatter(r["cost"], r["vf"], s=140, marker="X",
                       color=GREY, linewidths=2, zorder=5, label="_nolegend_")

    # Labels des points (positions optimisées)
    offsets = {
        161: (12, -4, "left"),
        165: (-14, 22, "right"),
        171: (12, 12, "left"),
        164: (-12, -18, "right"),
        158: (12, -14, "left"),
        159: (12, -6, "left"),
        167: (12, 0, "left"),
        160: (-12, 0, "right"),
    }
    for r in runs:
        is_pareto = any(p["id"] == r["id"] for p in pareto)
        dx, dy, ha = offsets[r["id"]]
        color = BLUE_DARK if is_pareto else GREY_DARK
        weight = "bold" if is_pareto else "normal"
        txt = ax1.annotate(
            f"{r['label']}\n(run {r['id']})",
            xy=(r["cost"], r["vf"]),
            xytext=(dx, dy),
            textcoords="offset points",
            ha=ha, va="center",
            fontsize=9, color=color, fontweight=weight,
            linespacing=1.1,
        )
        txt.set_path_effects([pe.withStroke(linewidth=2.8, foreground="white")])

    ax1.set_xlim(1.8, 8.5)
    ax1.set_ylim(81, 89.5)
    ax1.set_xlabel("Coût total du run (USD)", fontsize=12, color=INK, labelpad=8)
    ax1.set_ylabel("Accuracy VF (%)", fontsize=12, color=INK, labelpad=8)
    ax1.set_title("Frontière de Pareto coût-performance",
                  fontsize=13, fontweight="bold", color=INK, pad=12)

    from matplotlib.lines import Line2D
    leg = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=BLUE,
               markeredgecolor=BLUE_DARK, markersize=11, label="Pareto-optimal"),
        Line2D([0], [0], marker="X", color=GREY, markersize=10,
               linewidth=0, markeredgewidth=1.8, label="Dominé"),
        Line2D([0], [0], linestyle="--", color=RED, linewidth=2.2,
               label="Frontière de Pareto"),
    ]
    ax1.legend(handles=leg, loc="lower right", fontsize=10)

    # ══════════════════════════════════════════════════════════════════════
    # PANNEAU DROIT : Cm(q) en fonction escalier + CM moyenne
    # ══════════════════════════════════════════════════════════════════════

    ax2.set_axisbelow(True)
    ax2.grid(True, color="#F1F5F9", linewidth=0.6)

    # q = points de VF au-dessus de 80%
    q_vals = [r["vf"] - 80 for r in pareto]
    cm_vals = []
    for i in range(len(pareto) - 1):
        dc = pareto[i + 1]["cost"] - pareto[i]["cost"]
        dv = pareto[i + 1]["vf"] - pareto[i]["vf"]
        cm_vals.append(dc / dv)

    # Step function Cm
    for i, cm in enumerate(cm_vals):
        x_start = q_vals[i]
        x_end = q_vals[i + 1]
        ax2.plot([x_start, x_end], [cm, cm], color=RED, linewidth=3, zorder=5)
        # Transition verticale
        if i < len(cm_vals) - 1:
            ax2.plot([x_end, x_end], [cm, cm_vals[i + 1]],
                    color=RED, linewidth=1.5, linestyle=":", zorder=4)
        # Label Cm au milieu du palier
        mid_x = (x_start + x_end) / 2
        ax2.annotate(
            f"Cm = \\${cm:.2f}/pp",
            xy=(mid_x, cm),
            xytext=(0, 12),
            textcoords="offset points",
            ha="center", va="bottom",
            fontsize=10, color=RED_DARK, fontweight="bold",
        )

    # Points de transition (ronds aux extrémités des paliers)
    for i, cm in enumerate(cm_vals):
        ax2.scatter(q_vals[i], cm, s=50, color=RED, zorder=6, edgecolor="white", linewidth=1.2)
        ax2.scatter(q_vals[i + 1], cm, s=50, color=RED, zorder=6, edgecolor="white", linewidth=1.2)

    # Coût moyen CM aux points Pareto
    for p in pareto:
        q = p["vf"] - 80
        cm_avg = p["cost"] / q
        ax2.scatter(q, cm_avg, s=100, marker="o",
                   facecolor=BLUE, edgecolor=BLUE_DARK, linewidth=1.2, zorder=5)
        # Label run id
        ax2.annotate(
            f"run {p['id']}\nCM=\\${cm_avg:.2f}",
            xy=(q, cm_avg),
            xytext=(10, -2),
            textcoords="offset points",
            ha="left", va="center",
            fontsize=8.5, color=BLUE_DARK, fontweight="bold",
            linespacing=1.1,
        )

    # Lignes pointillées reliant les CM
    q_pareto = [p["vf"] - 80 for p in pareto]
    cm_pareto = [p["cost"] / (p["vf"] - 80) for p in pareto]
    ax2.plot(q_pareto, cm_pareto, color=BLUE, linestyle="-", linewidth=1.5,
             alpha=0.5, zorder=3)

    # Mise en évidence du minimum CM
    min_idx = int(np.argmin(cm_pareto))
    min_run = pareto[min_idx]
    ax2.axvline(min_run["vf"] - 80, color=GREEN, linestyle=":",
                linewidth=1.3, alpha=0.6, zorder=2)
    ax2.annotate(
        f"minimum CM\n(run {min_run['id']})",
        xy=(min_run["vf"] - 80, 0.4),
        xytext=(10, 0),
        textcoords="offset points",
        fontsize=9, color=GREEN, fontweight="bold",
        style="italic",
    )

    ax2.set_xlim(1, 8.5)
    ax2.set_ylim(0, 1.2)
    ax2.set_xlabel("q = gain VF au-dessus de 80 % (points)",
                   fontsize=12, color=INK, labelpad=8)
    ax2.set_ylabel("Coût ($/pp)", fontsize=12, color=INK, labelpad=8)
    ax2.set_title("Coût marginal (Cm) et coût moyen (CM)",
                  fontsize=13, fontweight="bold", color=INK, pad=12)

    leg2 = [
        Line2D([0], [0], color=RED, linewidth=3, label="Cm (coût marginal)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=BLUE,
               markeredgecolor=BLUE_DARK, markersize=9, label="CM (coût moyen)"),
    ]
    ax2.legend(handles=leg2, loc="upper left", fontsize=10)

    # ══════════════════════════════════════════════════════════════════════
    # Titre global
    # ══════════════════════════════════════════════════════════════════════

    fig.suptitle(
        "Ablation alpha — 8 configurations sur 390 posts",
        fontsize=14.5, fontweight="bold", color=INK, y=0.99,
    )

    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    fig.savefig(out_path + ".png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(out_path + ".pdf", bbox_inches="tight", facecolor="white")
    print(f"  -> {out_path}.png")
    print(f"  -> {out_path}.pdf")
    plt.close(fig)


def main():
    runs = load_runs()
    pareto = pareto_frontier(runs)

    for r in runs:
        flag = "*" if any(p["id"] == r["id"] for p in pareto) else " "
        print(f"  {flag} run {r['id']:3d} | {r['label']:25s} | "
              f"cost=${r['cost']:.2f} | VF={r['vf']:.1f}%")

    out = str(PROJECT_ROOT / "docs" / "ablation_alpha_final")
    make_plot(runs, pareto, out)


if __name__ == "__main__":
    main()
