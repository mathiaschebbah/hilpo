"""Figure rigoureuse publication-ready — frontière Pareto empirique.

Aucun fit, aucune courbe continue ajustée. Tout est dérivé directement des
8 observations :
- Points avec intervalles de confiance Wilson 95% (rigueur statistique)
- Frontière de Pareto piecewise linéaire (pas de smoothing)
- Coût marginal = pente de chaque segment Pareto (géométrique)
- Rayons iso-CM depuis l'origine (coût moyen géométriquement)
- Région dominée ombrée (visuel direct de la dominance)
- Sandwich Cm_gauche < CM < Cm_droite au minimum (caractérisation discrète)
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
    "font.family": "DejaVu Serif",
    "font.size": 10,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.dpi": 300,
    "axes.linewidth": 0.7,
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "legend.frameon": False,
})

# ─── Palette sobre ───────────────────────────────────────────────────────────

BLUE      = "#1D4ED8"   # Pareto
BLUE_DARK = "#1E3A8A"
GREY      = "#9CA3AF"   # dominé
GREY_DARK = "#475569"
RED       = "#DC2626"   # coût marginal
GREEN     = "#059669"   # minimum
INK       = "#0F172A"
ISO_GREY  = "#CBD5E1"


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervalle de confiance Wilson pour une proportion (plus robuste qu'une
    approximation normale aux bornes, standard en biostat / épidémiologie)."""
    if n == 0:
        return 0.0, 0.0
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return center - half, center + half


def load_runs() -> list[dict]:
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
        ci_lo, ci_hi = wilson_ci(correct, n)
        name = cfg.get("name", "")
        mode = cfg.get("pipeline_mode", "?")
        tier = cfg.get("model_tier", "?")
        no_assist = "no_assist" in name
        label = f"{mode} {tier}"
        if mode == "simple":
            label += " no-ASSIST" if no_assist else " ASSIST"
        runs.append({
            "id": rid,
            "label": label,
            "cost": float(cost),
            "vf": pct,
            "n": n,
            "correct": correct,
            "ci_lo": ci_lo * 100,
            "ci_hi": ci_hi * 100,
        })
    return runs


def pareto_frontier(runs: list[dict]) -> list[dict]:
    """Dominance empirique stricte."""
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


def make_plot(runs: list[dict], pareto: list[dict], out_path: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 7.5))

    # ─── 1. Région dominée ombrée ────────────────────────────────────────
    # À droite et en dessous de la frontière Pareto
    x_min, x_max = 1.8, 9.0
    y_min, y_max = 81.0, 89.5

    pareto_x = [r["cost"] for r in pareto]
    pareto_y = [r["vf"] for r in pareto]

    fill_x = [pareto_x[0]]
    fill_y = [y_min]
    for px, py in zip(pareto_x, pareto_y):
        fill_x.append(px)
        fill_y.append(py)
    fill_x.extend([x_max, x_max])
    fill_y.extend([pareto_y[-1], y_min])

    ax.fill(fill_x, fill_y, color="#FEE2E2", alpha=0.25, zorder=1,
            linewidth=0, label=None)
    ax.text(6.8, 82.3, "région dominée", color="#B91C1C", fontsize=9,
            style="italic", alpha=0.7, zorder=2)

    # ─── 2. Rayons iso-CM depuis l'origine ───────────────────────────────
    # Un rayon de pente k passe par des points où CM = k
    # Trois rayons de référence : la pente CM du min (0.57), et ±
    for cm_val, linestyle, alpha in [(0.57, "--", 0.6),
                                       (1.05, ":", 0.4)]:
        # Le rayon en coord (cost, vf) : vf = 80 + cost / cm_val
        xs = np.array([0, x_max])
        ys = 80.0 + xs / cm_val
        mask = (ys >= y_min) & (ys <= y_max)
        if mask.any():
            ax.plot(xs, ys, color=ISO_GREY, linestyle=linestyle, linewidth=0.9,
                    alpha=alpha, zorder=2)
            # Label du rayon à l'extrémité visible
            for xi, yi in zip(xs, ys):
                if y_min <= yi <= y_max:
                    if xi == x_max:
                        ax.text(xi - 0.05, yi + 0.08, f"CM = ${cm_val:.2f}/pp",
                                color=GREY_DARK, fontsize=7.5, style="italic",
                                ha="right", va="bottom", alpha=0.7, zorder=2)
                        break

    # ─── 3. Frontière de Pareto piecewise linéaire + pentes Cm ──────────
    ax.plot(pareto_x, pareto_y, color=BLUE, linewidth=2.2, zorder=5, alpha=0.85)

    # Annotation du coût marginal sur chaque segment (la pente = Cm)
    for i in range(len(pareto) - 1):
        a, b = pareto[i], pareto[i + 1]
        dc = b["cost"] - a["cost"]
        dv = b["vf"] - a["vf"]
        cm_segment = dc / dv if dv > 0 else float("inf")
        mx = (a["cost"] + b["cost"]) / 2
        my = (a["vf"] + b["vf"]) / 2

        txt = ax.annotate(
            f"Cm = ${cm_segment:.2f}/pp\n(+{dv:.1f}pp pour +${dc:.2f})",
            xy=(mx, my),
            xytext=(0, -25),
            textcoords="offset points",
            ha="center", va="top",
            fontsize=8.5, color=RED, fontweight="bold",
            linespacing=1.2,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor=RED, linewidth=0.8, alpha=0.95),
            zorder=7,
        )

    # ─── 4. Points de données avec CI Wilson 95% ────────────────────────
    for r in runs:
        is_pareto = any(p["id"] == r["id"] for p in pareto)

        # Error bar verticale (CI sur accuracy)
        ax.errorbar(
            r["cost"], r["vf"],
            yerr=[[r["vf"] - r["ci_lo"]], [r["ci_hi"] - r["vf"]]],
            fmt="none",
            ecolor=BLUE if is_pareto else GREY,
            elinewidth=0.8, capsize=3, capthick=0.8,
            alpha=0.55, zorder=4,
        )

        if is_pareto:
            ax.scatter(r["cost"], r["vf"], s=130, marker="o",
                       facecolor=BLUE, edgecolor=BLUE_DARK, linewidth=1.2,
                       zorder=6)
        else:
            ax.scatter(r["cost"], r["vf"], s=95, marker="s",
                       facecolor="white", edgecolor=GREY, linewidth=1.2,
                       zorder=6)

    # ─── 5. Labels des points ────────────────────────────────────────────
    offsets = {
        158: (10, 0, "left"),       # alma flash-lite
        159: (10, -4, "left"),      # alma flash
        160: (-10, 2, "right"),     # alma full-flash
        161: (10, 0, "left"),       # alma qwen
        164: (-10, 0, "right"),     # simple fl ASSIST
        165: (10, 12, "left"),      # simple fl no-assist (Pareto min)
        167: (10, -3, "left"),      # simple flash no-assist
        171: (-8, 14, "right"),     # simple flash ASSIST
    }

    for r in runs:
        is_pareto = any(p["id"] == r["id"] for p in pareto)
        dx, dy, ha = offsets[r["id"]]
        color = BLUE_DARK if is_pareto else GREY_DARK
        weight = "bold" if is_pareto else "normal"
        txt = ax.annotate(
            f"{r['label']}\n(run {r['id']})",
            xy=(r["cost"], r["vf"]),
            xytext=(dx, dy),
            textcoords="offset points",
            ha=ha, va="center",
            fontsize=8.5, color=color, fontweight=weight,
            linespacing=1.0,
        )
        txt.set_path_effects([pe.withStroke(linewidth=2.5, foreground="white")])

    # ─── 6. Mise en évidence du minimum empirique du coût moyen ─────────
    min_run = min(pareto, key=lambda r: r["cost"] / (r["vf"] - 80))
    cm_min = min_run["cost"] / (min_run["vf"] - 80)

    # Rayon vert pointé vers le minimum
    xs_min = np.array([0, min_run["cost"] * 1.05])
    ys_min = 80.0 + xs_min / cm_min
    ax.plot(xs_min, ys_min, color=GREEN, linestyle="--",
            linewidth=1.3, alpha=0.8, zorder=3)

    # Marqueur sur le point minimum
    ax.scatter(min_run["cost"], min_run["vf"], s=260, marker="o",
               facecolor="none", edgecolor=GREEN, linewidth=2.0, zorder=7)

    # Annotation du sandwich
    cm_left = None
    cm_right = None
    for i in range(len(pareto) - 1):
        if pareto[i + 1]["id"] == min_run["id"]:
            a = pareto[i]
            cm_left = (min_run["cost"] - a["cost"]) / (min_run["vf"] - a["vf"])
        if pareto[i]["id"] == min_run["id"]:
            b = pareto[i + 1]
            cm_right = (b["cost"] - min_run["cost"]) / (b["vf"] - min_run["vf"])

    sandwich_text = (
        f"minimum empirique du coût moyen\n"
        f"run {min_run['id']} : CM = \\${cm_min:.2f}/pp\n\n"
        f"Cm(gauche) = \\${cm_left:.2f}\n"
        f"   <  CM = \\${cm_min:.2f}\n"
        f"   <  Cm(droite) = \\${cm_right:.2f}"
    )
    ax.annotate(
        sandwich_text,
        xy=(min_run["cost"], min_run["vf"]),
        xytext=(80, -110),
        textcoords="offset points",
        fontsize=8.5,
        color=GREEN,
        fontweight="normal",
        bbox=dict(boxstyle="round,pad=0.5", facecolor="#F0FDF4",
                  edgecolor=GREEN, linewidth=0.9),
        arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.0,
                        connectionstyle="arc3,rad=0.25"),
        zorder=9,
        linespacing=1.3,
        ha="left",
    )

    # ─── 7. Axes et légende ──────────────────────────────────────────────
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_xlabel("Coût total du run (USD, n = 390 posts)", fontsize=11.5, color=INK)
    ax.set_ylabel("Accuracy Visual Format (%, IC Wilson 95%)", fontsize=11.5, color=INK)
    ax.set_title(
        "Frontière de Pareto empirique — coût vs performance",
        fontsize=13.5, fontweight="bold", color=INK, pad=14,
    )

    ax.grid(True, color="#F1F5F9", linewidth=0.6, zorder=0)
    ax.set_axisbelow(True)

    # Légende custom
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=BLUE,
               markeredgecolor=BLUE_DARK, markersize=10, label="Pareto-optimal"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor="white",
               markeredgecolor=GREY, markersize=9, markeredgewidth=1.2,
               label="Dominé"),
        Line2D([0], [0], color=BLUE, linewidth=2.2, label="Frontière (piecewise linéaire)"),
        Line2D([0], [0], color=ISO_GREY, linestyle=":", linewidth=1.0,
               label="Rayons iso-CM (pente = $/pp)"),
        Line2D([0], [0], color=GREEN, linestyle="--", linewidth=1.3,
               label="Minimum empirique du CM"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=8.5,
              ncol=1, bbox_to_anchor=(0.01, 0.99))

    # Note méthodologique en bas
    fig.text(
        0.5, 0.01,
        "Aucune courbe continue ajustée. Cm = pente des segments Pareto. "
        "CM = pente des rayons depuis l'origine (q = VF% − 80). "
        "Intervalles de confiance Wilson 95% sur l'accuracy (n = 377–390).",
        fontsize=8, color=GREY_DARK, style="italic", ha="center",
    )

    fig.tight_layout(rect=[0, 0.03, 1, 1])
    fig.savefig(out_path + ".png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(out_path + ".pdf", bbox_inches="tight", facecolor="white")
    print(f"  -> {out_path}.png")
    print(f"  -> {out_path}.pdf")
    plt.close(fig)


def main():
    runs = load_runs()
    pareto = pareto_frontier(runs)

    print("Runs chargés (triés par coût) :")
    for r in runs:
        flag = "★" if any(p["id"] == r["id"] for p in pareto) else " "
        print(f"  {flag} run {r['id']:3d} | {r['label']:28s} | "
              f"cost=${r['cost']:.2f} | VF={r['vf']:5.1f}% "
              f"[CI: {r['ci_lo']:.1f}-{r['ci_hi']:.1f}]")
    print()

    out = str(PROJECT_ROOT / "docs" / "ablation_alpha_rigorous")
    make_plot(runs, pareto, out)


if __name__ == "__main__":
    main()
