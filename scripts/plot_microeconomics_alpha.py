#!/usr/bin/env python3
"""Generate micro-economics style visuals for the 8 alpha ablation runs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import textwrap

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.ticker as mticker
import numpy as np
from matplotlib.colors import Normalize
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
import psycopg
from scipy.interpolate import PchipInterpolator

from plot_ablation_alpha import ALPHA_RUN_IDS, DATABASE_DSN, RUN_SPECS_BY_ID


OUTPUT_DIR = Path("/Users/mathias/Desktop/mémoire-v2/docs/assets/micro")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
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
    }
)

BLUE = "#2563EB"
BLUE_DARK = "#1E40AF"
GREY = "#9CA3AF"
SLATE = "#475569"
RED = "#DC2626"
GREEN = "#059669"
AMBER = "#D97706"


@dataclass(frozen=True)
class RunMetric:
    run_id: int
    cost_usd: float
    n_posts: int
    n_correct: int

    @property
    def accuracy_pct(self) -> float:
        return 100.0 * self.n_correct / self.n_posts

    @property
    def spec(self):
        return RUN_SPECS_BY_ID[self.run_id]


def _load_run_metrics() -> list[RunMetric]:
    query = """
        WITH vf AS (
            SELECT
                simulation_run_id AS run_id,
                COUNT(*) AS n_posts,
                SUM(CASE WHEN match THEN 1 ELSE 0 END) AS n_correct
            FROM predictions
            WHERE agent = 'visual_format'
              AND simulation_run_id = ANY(%s)
            GROUP BY simulation_run_id
        )
        SELECT
            r.id,
            r.total_cost_usd,
            vf.n_posts,
            vf.n_correct
        FROM simulation_runs r
        JOIN vf ON vf.run_id = r.id
        WHERE r.id = ANY(%s)
        ORDER BY r.total_cost_usd
    """

    with psycopg.connect(DATABASE_DSN) as conn:
        with conn.cursor() as cur:
            cur.execute(query, (list(ALPHA_RUN_IDS), list(ALPHA_RUN_IDS)))
            rows = cur.fetchall()

    metrics = [
        RunMetric(
            run_id=int(run_id),
            cost_usd=float(cost_usd),
            n_posts=int(n_posts),
            n_correct=int(n_correct),
        )
        for run_id, cost_usd, n_posts, n_correct in rows
    ]

    if len(metrics) != len(ALPHA_RUN_IDS):
        raise RuntimeError("Alpha run metrics are incomplete.")

    return metrics


def _compute_pareto_frontier(metrics: list[RunMetric]) -> list[RunMetric]:
    frontier = []
    for candidate in metrics:
        dominated = False
        for other in metrics:
            if other.run_id == candidate.run_id:
                continue
            same_or_lower_cost = other.cost_usd <= candidate.cost_usd
            same_or_higher_acc = other.accuracy_pct >= candidate.accuracy_pct
            strictly_better = (
                other.cost_usd < candidate.cost_usd
                or other.accuracy_pct > candidate.accuracy_pct
            )
            if same_or_lower_cost and same_or_higher_acc and strictly_better:
                dominated = True
                break
        if not dominated:
            frontier.append(candidate)
    return sorted(frontier, key=lambda run: run.cost_usd)


def _architecture_label(run_id: int) -> str:
    spec = RUN_SPECS_BY_ID[run_id]
    if spec.mode_label == "Alma":
        return "Alma\n2 etages"
    if spec.assist_label == "ASSIST":
        return "Simple\n+ ASSIST"
    return "Simple\nsans ASSIST"


def _model_label(run_id: int) -> str:
    return RUN_SPECS_BY_ID[run_id].tier_label


def _display_label(run_id: int, *, width: int = 18) -> str:
    spec = RUN_SPECS_BY_ID[run_id]
    parts = [spec.mode_label, spec.tier_label]
    if spec.mode_label == "Simple" and spec.assist_label == "no-assist":
        parts.append("Sans ASSIST")
    text = " ".join(parts)
    return textwrap.fill(text, width=width, break_long_words=False, break_on_hyphens=False)


def _label_style(run_id: int) -> dict[str, object]:
    return {
        161: {"offset": (-12, -14), "ha": "right"},
        165: {"offset": (10, 8), "ha": "left"},
        164: {"offset": (10, -2), "ha": "left"},
        158: {"offset": (10, 2), "ha": "left"},
        159: {"offset": (10, -6), "ha": "left"},
        167: {"offset": (10, -8), "ha": "left"},
        171: {"offset": (8, 10), "ha": "left"},
        160: {"offset": (-10, 4), "ha": "right"},
    }[run_id]


def plot_pareto(metrics: list[RunMetric]) -> None:
    frontier = _compute_pareto_frontier(metrics)
    frontier_ids = {run.run_id for run in frontier}

    fig, ax = plt.subplots(figsize=(8.2, 5.3))
    ax.set_axisbelow(True)
    ax.grid(True, color="#E5E7EB", linewidth=0.6, alpha=0.8)

    px = [run.cost_usd for run in frontier]
    py = [run.accuracy_pct for run in frontier]
    ax.plot(px, py, color=RED, linestyle="--", linewidth=2.0, alpha=0.7, zorder=2)

    for run in metrics:
        if run.run_id in frontier_ids:
            ax.scatter(
                run.cost_usd,
                run.accuracy_pct,
                s=190,
                marker="o",
                facecolor=BLUE,
                edgecolor=BLUE_DARK,
                linewidth=1.2,
                zorder=5,
            )
        else:
            ax.scatter(
                run.cost_usd,
                run.accuracy_pct,
                s=120,
                marker="x",
                color=GREY,
                linewidths=1.8,
                zorder=4,
            )

    for run in metrics:
        cfg = _label_style(run.run_id)
        color = BLUE_DARK if run.run_id in frontier_ids else SLATE
        weight = "bold" if run.run_id in frontier_ids else "normal"
        size = 8.5 if run.run_id in frontier_ids else 7.7
        txt = ax.annotate(
            f"{_display_label(run.run_id)}\n(run {run.run_id})",
            xy=(run.cost_usd, run.accuracy_pct),
            xytext=cfg["offset"],
            textcoords="offset points",
            ha=cfg["ha"],
            va="center",
            fontsize=size,
            color=color,
            fontweight=weight,
            linespacing=0.95,
        )
        txt.set_path_effects([pe.withStroke(linewidth=3.0, foreground="white")])

    ax.set_xlabel("Coût total du run (USD)", fontsize=11.5)
    ax.set_ylabel("Accuracy Visual Format (%)", fontsize=11.5)
    ax.set_title("Frontière de Pareto coût-performance", fontsize=13, fontweight="bold")
    ax.set_xlim(1.7, 8.4)
    ax.set_ylim(81.0, 88.9)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.0f"))

    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=BLUE, markeredgecolor=BLUE_DARK, markersize=9.5, label="Pareto-optimal"),
        Line2D([0], [0], marker="x", color=GREY, markersize=9, linewidth=0, markeredgewidth=1.8, label="Dominé"),
        Line2D([0], [0], linestyle="--", color=RED, linewidth=2.0, label="Frontière efficiente"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", fontsize=9, frameon=True, edgecolor="#D1D5DB")

    path = OUTPUT_DIR / "01_pareto_cost_performance.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    print(f"  -> {path}")
    plt.close(fig)


def plot_cost_function(metrics: list[RunMetric]) -> None:
    frontier = sorted(_compute_pareto_frontier(metrics), key=lambda run: run.accuracy_pct)
    frontier_ids = {run.run_id for run in frontier}

    fig, ax = plt.subplots(figsize=(8.2, 5.3))
    ax.set_axisbelow(True)
    ax.grid(True, color="#E5E7EB", linewidth=0.6, alpha=0.8)

    for run in metrics:
        if run.run_id not in frontier_ids:
            ax.scatter(
                run.accuracy_pct,
                run.cost_usd,
                s=120,
                marker="x",
                color=GREY,
                linewidths=1.8,
                zorder=2,
            )

    x_step = [run.accuracy_pct for run in frontier]
    y_step = [run.cost_usd for run in frontier]
    ax.step(x_step, y_step, where="post", color=RED, linewidth=2.4, zorder=3)
    ax.scatter(x_step, y_step, s=160, color=BLUE, edgecolors=BLUE_DARK, linewidths=1.1, zorder=4)

    x_fill = x_step + [88.4]
    y_fill = y_step + [y_step[-1]]
    ax.fill_between(x_fill, y_fill, [8.4] * len(x_fill), step="post", color=RED, alpha=0.05, zorder=1)

    for run in frontier:
        txt = ax.annotate(
            f"{_display_label(run.run_id, width=16)}\n(run {run.run_id})",
            xy=(run.accuracy_pct, run.cost_usd),
            xytext=(8, 8),
            textcoords="offset points",
            fontsize=8.3,
            color=BLUE_DARK,
            fontweight="bold",
            ha="left",
            va="bottom",
        )
        txt.set_path_effects([pe.withStroke(linewidth=3.0, foreground="white")])

    ax.text(
        82.45,
        7.95,
        "c(y) = coût minimal observé pour atteindre au moins y",
        fontsize=9,
        color=SLATE,
        ha="left",
        va="top",
    )

    ax.set_xlabel("Accuracy VF cible (%)", fontsize=11.5)
    ax.set_ylabel("Coût minimal observé (USD)", fontsize=11.5)
    ax.set_title("Fonction de coût minimale empirique c(y)", fontsize=13, fontweight="bold")
    ax.set_xlim(81.8, 88.4)
    ax.set_ylim(2.0, 8.2)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1.0))
    ax.yaxis.set_major_locator(mticker.MultipleLocator(1.0))

    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=BLUE, markeredgecolor=BLUE_DARK, markersize=9, label="Configurations actives"),
        Line2D([0], [0], marker="x", color=GREY, markersize=9, linewidth=0, markeredgewidth=1.8, label="Configurations dominées"),
        Line2D([0], [0], color=RED, linewidth=2.4, label="Fonction de coût minimale"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=9, frameon=True, edgecolor="#D1D5DB")

    path = OUTPUT_DIR / "02_cost_function_minimum.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    print(f"  -> {path}")
    plt.close(fig)


def plot_cost_function_smooth(metrics: list[RunMetric]) -> None:
    frontier = sorted(_compute_pareto_frontier(metrics), key=lambda run: run.accuracy_pct)
    frontier_ids = {run.run_id for run in frontier}
    x = np.array([run.accuracy_pct for run in frontier], dtype=float)
    y = np.array([run.cost_usd for run in frontier], dtype=float)
    smooth = PchipInterpolator(x, y)
    x_eval = np.linspace(x.min(), x.max(), 200)
    y_eval = smooth(x_eval)

    fig, ax = plt.subplots(figsize=(8.2, 5.3))
    ax.set_axisbelow(True)
    ax.grid(True, color="#E5E7EB", linewidth=0.6, alpha=0.8)

    for run in metrics:
        if run.run_id not in frontier_ids:
            ax.scatter(
                run.accuracy_pct,
                run.cost_usd,
                s=120,
                marker="x",
                color=GREY,
                linewidths=1.8,
                zorder=2,
            )

    ax.fill_between(x_eval, y_eval, [8.4] * len(x_eval), color=RED, alpha=0.05, zorder=1)
    ax.step(x, y, where="post", color=RED, linewidth=1.6, alpha=0.45, zorder=3)
    ax.plot(x_eval, y_eval, color=RED, linewidth=2.6, zorder=4)
    ax.scatter(x, y, s=160, color=BLUE, edgecolors=BLUE_DARK, linewidths=1.1, zorder=5)

    for run in frontier:
        txt = ax.annotate(
            f"{_display_label(run.run_id, width=16)}\n(run {run.run_id})",
            xy=(run.accuracy_pct, run.cost_usd),
            xytext=(8, 8),
            textcoords="offset points",
            fontsize=8.3,
            color=BLUE_DARK,
            fontweight="bold",
            ha="left",
            va="bottom",
        )
        txt.set_path_effects([pe.withStroke(linewidth=3.0, foreground="white")])

    ax.text(
        82.45,
        7.95,
        "Courbe rouge = enveloppe lissée monotone\nGuide visuel autour de la vraie c(y) en escalier",
        fontsize=8.9,
        color=SLATE,
        ha="left",
        va="top",
    )

    ax.set_xlabel("Accuracy VF cible (%)", fontsize=11.5)
    ax.set_ylabel("Coût minimal observé (USD)", fontsize=11.5)
    ax.set_title("Fonction de coût minimale : version lissée pour lecture micro-éco", fontsize=13, fontweight="bold")
    ax.set_xlim(81.8, 88.4)
    ax.set_ylim(2.0, 8.2)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(1.0))
    ax.yaxis.set_major_locator(mticker.MultipleLocator(1.0))

    legend_elements = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=BLUE, markeredgecolor=BLUE_DARK, markersize=9, label="Configurations actives"),
        Line2D([0], [0], marker="x", color=GREY, markersize=9, linewidth=0, markeredgewidth=1.8, label="Configurations dominées"),
        Line2D([0], [0], color=RED, linewidth=2.6, label="Enveloppe lissée"),
        Line2D([0], [0], color=RED, linewidth=1.6, alpha=0.45, label="c(y) empirique en escalier"),
    ]
    ax.legend(handles=legend_elements, loc="upper left", fontsize=9, frameon=True, edgecolor="#D1D5DB")

    path = OUTPUT_DIR / "02b_cost_function_smooth.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    print(f"  -> {path}")
    plt.close(fig)


def plot_production_map(metrics: list[RunMetric]) -> None:
    metric_by_id = {run.run_id: run for run in metrics}
    rows = ["Qwen", "Flash-Lite", "Flash", "Full-Flash"]
    cols = ["Simple\nsans ASSIST", "Simple\n+ ASSIST", "Alma\n2 etages"]
    cell_runs = {
        ("Qwen", "Alma\n2 etages"): 161,
        ("Flash-Lite", "Simple\nsans ASSIST"): 165,
        ("Flash-Lite", "Simple\n+ ASSIST"): 164,
        ("Flash-Lite", "Alma\n2 etages"): 158,
        ("Flash", "Simple\nsans ASSIST"): 167,
        ("Flash", "Simple\n+ ASSIST"): 171,
        ("Flash", "Alma\n2 etages"): 159,
        ("Full-Flash", "Alma\n2 etages"): 160,
    }
    pareto_ids = {run.run_id for run in _compute_pareto_frontier(metrics)}

    norm = Normalize(vmin=min(run.accuracy_pct for run in metrics), vmax=max(run.accuracy_pct for run in metrics))
    cmap = plt.get_cmap("YlGnBu")

    fig, ax = plt.subplots(figsize=(8.5, 6.0))
    ax.set_xlim(0, len(cols))
    ax.set_ylim(0, len(rows))
    ax.set_xticks(np.arange(len(cols)) + 0.5)
    ax.set_yticks(np.arange(len(rows)) + 0.5)
    ax.set_xticklabels(cols, fontsize=9.5)
    ax.set_yticklabels(rows, fontsize=9.5)
    ax.invert_yaxis()
    ax.tick_params(length=0)
    ax.set_title("Carte de production discrète Y = f(A, M)", fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel("A (orchestration)", fontsize=11.5)
    ax.set_ylabel("M (tier modèle)", fontsize=11.5)

    for row_index, row in enumerate(rows):
        for col_index, col in enumerate(cols):
            run_id = cell_runs.get((row, col))
            if run_id is None:
                rect = Rectangle((col_index, row_index), 1, 1, facecolor="#F3F4F6", edgecolor="white", hatch="////", linewidth=1.2)
                ax.add_patch(rect)
                ax.text(
                    col_index + 0.5,
                    row_index + 0.5,
                    "non\ntesté",
                    ha="center",
                    va="center",
                    fontsize=8.0,
                    color=SLATE,
                )
                continue

            run = metric_by_id[run_id]
            rect = Rectangle(
                (col_index, row_index),
                1,
                1,
                facecolor=cmap(norm(run.accuracy_pct)),
                edgecolor="white",
                linewidth=1.5,
            )
            ax.add_patch(rect)

            txt = ax.text(
                col_index + 0.5,
                row_index + 0.53,
                f"{run.accuracy_pct:.1f}%\n${run.cost_usd:.2f}\nrun {run_id}",
                ha="center",
                va="center",
                fontsize=8.2,
                color="#0F172A",
                fontweight="bold" if run_id in pareto_ids else "normal",
                linespacing=1.15,
            )
            txt.set_path_effects([pe.withStroke(linewidth=2.5, foreground="white")])

            if run_id in pareto_ids:
                ax.scatter(
                    col_index + 0.87,
                    row_index + 0.18,
                    s=55,
                    marker="o",
                    facecolor=RED,
                    edgecolor="white",
                    linewidth=1.0,
                    zorder=5,
                )

    for x in range(len(cols) + 1):
        ax.axvline(x, color="white", linewidth=1.5)
    for y in range(len(rows) + 1):
        ax.axhline(y, color="white", linewidth=1.5)

    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, shrink=0.86)
    cbar.set_label("Accuracy VF (%)")

    ax.text(
        0.99,
        -0.13,
        "Point rouge = configuration Pareto-optimale",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=8.8,
        color=SLATE,
    )

    path = OUTPUT_DIR / "03_discrete_production_map.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    print(f"  -> {path}")
    plt.close(fig)


def _annotate_segment(ax, x0, y0, x1, y1, text, color, *, dy=0.55, dx=0.0) -> None:
    xm = (x0 + x1) / 2 + dx
    ym = (y0 + y1) / 2 + dy
    txt = ax.text(
        xm,
        ym,
        text,
        color=color,
        fontsize=8.8,
        fontweight="bold",
        ha="center",
        va="bottom",
    )
    txt.set_path_effects([pe.withStroke(linewidth=2.8, foreground="white")])


def plot_factorial_returns(metrics: list[RunMetric]) -> None:
    metric_by_id = {run.run_id: run for run in metrics}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.8, 5.9))

    ax1.set_axisbelow(True)
    ax1.grid(True, color="#E5E7EB", linewidth=0.6, alpha=0.8)

    alma_runs = [161, 158, 159, 160]
    simple_no_assist_runs = [165, 167]
    simple_assist_runs = [164, 171]

    for run_ids, color, marker, label in (
        (alma_runs, BLUE, "o", "Alma"),
        (simple_no_assist_runs, AMBER, "s", "Simple sans ASSIST"),
        (simple_assist_runs, GREEN, "D", "Simple + ASSIST"),
    ):
        xs = [metric_by_id[run_id].cost_usd for run_id in run_ids]
        ys = [metric_by_id[run_id].accuracy_pct for run_id in run_ids]
        ax1.plot(
            xs,
            ys,
            color=color,
            linewidth=2.1,
            marker=marker,
            markersize=6.5,
            markeredgecolor="white",
            markeredgewidth=0.9,
            label=label,
            zorder=3,
        )

    _annotate_segment(ax1, metric_by_id[161].cost_usd, metric_by_id[161].accuracy_pct, metric_by_id[158].cost_usd, metric_by_id[158].accuracy_pct, "+1.6 pp", BLUE, dy=0.50)
    _annotate_segment(ax1, metric_by_id[158].cost_usd, metric_by_id[158].accuracy_pct, metric_by_id[159].cost_usd, metric_by_id[159].accuracy_pct, "-0.3 pp", BLUE, dy=-0.85)
    _annotate_segment(ax1, metric_by_id[159].cost_usd, metric_by_id[159].accuracy_pct, metric_by_id[160].cost_usd, metric_by_id[160].accuracy_pct, "+3.1 pp", BLUE, dy=0.55)
    _annotate_segment(ax1, metric_by_id[165].cost_usd, metric_by_id[165].accuracy_pct, metric_by_id[167].cost_usd, metric_by_id[167].accuracy_pct, "~0 pp", AMBER, dy=0.42)
    _annotate_segment(ax1, metric_by_id[164].cost_usd, metric_by_id[164].accuracy_pct, metric_by_id[171].cost_usd, metric_by_id[171].accuracy_pct, "+3.0 pp", GREEN, dy=0.48)

    ax1.set_xlabel("M (investissement modèle, USD / run)", fontsize=11)
    ax1.set_ylabel("Accuracy Visual Format (%)", fontsize=11)
    ax1.set_title("Rendements factoriels de M\n(à architecture constante)", fontsize=12.5, fontweight="bold")
    ax1.set_xlim(2.0, 8.2)
    ax1.set_ylim(81.4, 88.9)
    ax1.xaxis.set_major_locator(mticker.MultipleLocator(1.0))
    ax1.yaxis.set_major_locator(mticker.MultipleLocator(1.0))
    ax1.legend(loc="lower right", fontsize=8.8, frameon=True, edgecolor="#D1D5DB")

    ax2.set_axisbelow(True)
    ax2.grid(True, color="#E5E7EB", linewidth=0.6, alpha=0.8)

    architecture_levels = ["Simple\nsans ASSIST", "Simple\n+ ASSIST", "Alma\n2 etages"]
    x = np.arange(len(architecture_levels))
    flash_lite_runs = [165, 164, 158]
    flash_runs = [167, 171, 160]

    for run_ids, color, marker, label in (
        (flash_lite_runs, BLUE, "o", "Modèle = Flash-Lite"),
        (flash_runs, RED, "s", "Modèle = Flash"),
    ):
        ys = [metric_by_id[run_id].accuracy_pct for run_id in run_ids]
        ax2.plot(
            x,
            ys,
            color=color,
            linewidth=2.2,
            marker=marker,
            markersize=6.5,
            markeredgecolor="white",
            markeredgewidth=0.9,
            label=label,
            zorder=3,
        )

    _annotate_segment(ax2, x[0], metric_by_id[165].accuracy_pct, x[1], metric_by_id[164].accuracy_pct, "-0.5 pp", BLUE, dy=0.55, dx=-0.03)
    _annotate_segment(ax2, x[1], metric_by_id[164].accuracy_pct, x[2], metric_by_id[158].accuracy_pct, "-1.0 pp", BLUE, dy=-1.05, dx=0.03)
    _annotate_segment(ax2, x[0], metric_by_id[167].accuracy_pct, x[1], metric_by_id[171].accuracy_pct, "+2.5 pp", RED, dy=0.62, dx=-0.02)
    _annotate_segment(ax2, x[1], metric_by_id[171].accuracy_pct, x[2], metric_by_id[160].accuracy_pct, "-1.2 pp", RED, dy=0.55, dx=0.03)

    ax2.set_xticks(x)
    ax2.set_xticklabels(architecture_levels, fontsize=9.5)
    ax2.set_xlabel("A (profondeur d'orchestration)", fontsize=11)
    ax2.set_title("Rendements factoriels de A\n(à modèle constant)", fontsize=12.5, fontweight="bold")
    ax2.set_ylim(81.4, 88.9)
    ax2.yaxis.set_major_locator(mticker.MultipleLocator(1.0))
    ax2.legend(loc="lower right", fontsize=8.8, frameon=True, edgecolor="#D1D5DB")

    ax2.text(
        0.98,
        0.04,
        "Le rendement de A dépend du tier modèle :\nnégatif à Flash-Lite, positif puis décroissant à Flash.",
        transform=ax2.transAxes,
        ha="right",
        va="bottom",
        fontsize=8.6,
        color=SLATE,
    )

    fig.suptitle("Ablation alpha (8 runs) — rendements factoriels de A et M", fontsize=14.2, fontweight="bold", y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    path = OUTPUT_DIR / "04_factorial_returns.png"
    fig.savefig(path, bbox_inches="tight")
    print(f"  -> {path}")
    plt.close(fig)


def plot_marginal_cost_per_pp(metrics: list[RunMetric]) -> None:
    metric_by_id = {run.run_id: run for run in metrics}

    frontier = sorted(_compute_pareto_frontier(metrics), key=lambda run: run.cost_usd)
    frontier_segments = []
    for left, right in zip(frontier[:-1], frontier[1:]):
        delta_cost = right.cost_usd - left.cost_usd
        delta_acc = right.accuracy_pct - left.accuracy_pct
        frontier_segments.append(
            {
                "label": f"{left.run_id} -> {right.run_id}",
                "delta_cost": delta_cost,
                "delta_acc": delta_acc,
                "marginal_cost": delta_cost / delta_acc,
            }
        )

    local_comparisons = [
        {
            "label": "ASSIST sur Flash",
            "start": 167,
            "end": 171,
            "color": GREEN,
        },
        {
            "label": "ASSIST sur Flash-Lite",
            "start": 165,
            "end": 164,
            "color": AMBER,
        },
        {
            "label": "Alma Flash -> Full-Flash",
            "start": 159,
            "end": 160,
            "color": RED,
        },
        {
            "label": "Alma Flash-Lite -> Flash",
            "start": 158,
            "end": 159,
            "color": BLUE,
        },
    ]

    for comparison in local_comparisons:
        start = metric_by_id[comparison["start"]]
        end = metric_by_id[comparison["end"]]
        delta_cost = end.cost_usd - start.cost_usd
        delta_acc = end.accuracy_pct - start.accuracy_pct
        comparison["delta_cost"] = delta_cost
        comparison["delta_acc"] = delta_acc
        comparison["marginal_cost"] = delta_cost / delta_acc

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.6, 5.8), gridspec_kw={"width_ratios": [1.0, 1.3]})

    ax1.set_axisbelow(True)
    ax1.grid(axis="x", color="#E5E7EB", linewidth=0.6, alpha=0.8)
    y_pos = np.arange(len(frontier_segments))
    values = [segment["marginal_cost"] for segment in frontier_segments]
    bars = ax1.barh(y_pos, values, height=0.48, color=[GREEN, RED], edgecolor="white", linewidth=1.2)

    for bar, segment in zip(bars, frontier_segments):
        ax1.text(
            bar.get_width() + 0.03,
            bar.get_y() + bar.get_height() / 2,
            f"${segment['marginal_cost']:.2f}/pp\n+${segment['delta_cost']:.2f} pour +{segment['delta_acc']:.1f} pp",
            ha="left",
            va="center",
            fontsize=8.5,
            color=SLATE,
            linespacing=1.25,
        )

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels([segment["label"] for segment in frontier_segments], fontsize=9)
    ax1.set_xlabel("Coût marginal par point de VF ($/pp)", fontsize=11)
    ax1.set_title("Le long de la frontière de Pareto", fontsize=12.5, fontweight="bold")
    ax1.set_xlim(0.0, 1.2)
    ax1.invert_yaxis()
    ax1.text(
        0.98,
        0.92,
        "Le second saut de performance coûte\npresque 4x plus cher par point.",
        transform=ax1.transAxes,
        ha="right",
        va="top",
        fontsize=8.7,
        color=SLATE,
    )

    ax2.set_axisbelow(True)
    ax2.grid(axis="x", color="#E5E7EB", linewidth=0.6, alpha=0.8)
    ax2.axvline(0, color=SLATE, linewidth=1.0, alpha=0.8)
    y_pos = np.arange(len(local_comparisons))
    values = [comparison["marginal_cost"] for comparison in local_comparisons]
    bars = ax2.barh(
        y_pos,
        values,
        height=0.48,
        color=[comparison["color"] for comparison in local_comparisons],
        edgecolor="white",
        linewidth=1.2,
    )

    for bar, comparison in zip(bars, local_comparisons):
        value = comparison["marginal_cost"]
        delta_cost = comparison["delta_cost"]
        delta_acc = comparison["delta_acc"]
        ha = "left" if value >= 0 else "right"
        x_text = value + 0.06 if value >= 0 else value - 0.06
        if delta_acc > 0:
            label = f"${value:.2f}/pp\n+${delta_cost:.2f} pour +{delta_acc:.1f} pp"
        else:
            label = f"surcoût inefficace\n+${delta_cost:.2f} pour {delta_acc:.1f} pp"
        ax2.text(
            x_text,
            bar.get_y() + bar.get_height() / 2,
            label,
            ha=ha,
            va="center",
            fontsize=8.5,
            color=comparison["color"],
            fontweight="bold",
            linespacing=1.2,
        )

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels([comparison["label"] for comparison in local_comparisons], fontsize=9)
    ax2.set_xlabel("Coût marginal local ($/pp)", fontsize=11)
    ax2.set_title("Entre configurations comparables", fontsize=12.5, fontweight="bold")
    ax2.set_xlim(-4.1, 1.4)
    ax2.invert_yaxis()
    ax2.text(
        0.98,
        0.92,
        "A gauche de 0 : on paie plus pour faire pire.\nA droite : gain de VF au coût indiqué par point.",
        transform=ax2.transAxes,
        ha="right",
        va="top",
        fontsize=8.7,
        color=SLATE,
    )

    fig.suptitle("Coût marginal de la performance", fontsize=14.2, fontweight="bold", y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    path = OUTPUT_DIR / "05b_marginal_cost_segments.png"
    fig.savefig(path, bbox_inches="tight")
    print(f"  -> {path}")
    plt.close(fig)


def plot_cost_curves_calibrated(metrics: list[RunMetric]) -> None:
    frontier = sorted(_compute_pareto_frontier(metrics), key=lambda run: run.accuracy_pct)
    baseline_acc = 80.0

    q = np.array([run.accuracy_pct - baseline_acc for run in frontier], dtype=float)
    c = np.array([run.cost_usd for run in frontier], dtype=float)
    cm = c / q
    q_mid = (q[:-1] + q[1:]) / 2.0
    marginal = np.diff(c) / np.diff(q)
    run_ids = [run.run_id for run in frontier]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.8, 5.7), gridspec_kw={"width_ratios": [1.15, 1.0]})

    for ax in (ax1, ax2):
        ax.set_axisbelow(True)
        ax.grid(True, color="#E5E7EB", linewidth=0.6, alpha=0.8)

    ax1.plot(q, c, color=BLUE_DARK, linewidth=2.0, zorder=2)
    ax1.scatter(q, c, s=78, color=BLUE, edgecolor="white", linewidth=1.0, zorder=3)
    ax1.scatter([q[1]], [c[1]], s=120, color=GREEN, edgecolor="white", linewidth=1.1, zorder=4)

    ray_styles = {
        161: {"color": GREY, "offset": (-26, 8)},
        165: {"color": GREEN, "offset": (10, -2)},
        171: {"color": GREY, "offset": (10, 6)},
    }
    for x, y, run_id, avg_cost in zip(q, c, run_ids, cm):
        style = ray_styles[run_id]
        ax1.plot(
            [0.0, x],
            [0.0, y],
            linestyle="--",
            linewidth=2.2 if run_id == 165 else 1.5,
            color=style["color"],
            alpha=0.95 if run_id == 165 else 0.75,
            zorder=1,
        )
        txt = ax1.annotate(
            f"run {run_id}\nCM = ${avg_cost:.2f}/pp",
            xy=(x, y),
            xytext=style["offset"],
            textcoords="offset points",
            ha="left" if style["offset"][0] >= 0 else "right",
            va="bottom",
            fontsize=8.4,
            color=style["color"] if run_id == 165 else SLATE,
            fontweight="bold" if run_id == 165 else "normal",
            linespacing=1.05,
        )
        txt.set_path_effects([pe.withStroke(linewidth=2.6, foreground="white")])

    segment_offsets = [(0, 12), (0, -16)]
    for idx, (x, y, mc) in enumerate(zip(q_mid, (c[:-1] + c[1:]) / 2.0, marginal)):
        txt = ax1.annotate(
            f"Cm = ${mc:.2f}/pp",
            xy=(x, y),
            xytext=segment_offsets[idx],
            textcoords="offset points",
            ha="center",
            va="bottom" if segment_offsets[idx][1] > 0 else "top",
            fontsize=8.3,
            color=RED,
            fontweight="bold",
        )
        txt.set_path_effects([pe.withStroke(linewidth=2.6, foreground="white")])

    ax1.annotate(
        "run 165 = minimum empirique\ndu coût moyen",
        xy=(q[1], c[1]),
        xytext=(34, -44),
        textcoords="offset points",
        arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.2),
        fontsize=8.7,
        color=GREEN,
        ha="left",
        va="top",
    )

    ax1.text(
        0.03,
        0.96,
        "Pente des rayons depuis l'origine = coût moyen CM\nPente des segments de frontière = coût marginal discret Cm",
        transform=ax1.transAxes,
        ha="left",
        va="top",
        fontsize=8.5,
        color=SLATE,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#D1D5DB", alpha=0.94),
    )

    ax1.set_title("Frontière de coût C(q)", fontsize=12.6, fontweight="bold")
    ax1.set_xlabel("q = surplus de VF au-dessus de 80% (points)")
    ax1.set_ylabel("Coût total du run C(q) (USD)")
    ax1.set_xlim(0.0, q.max() + 0.8)
    ax1.set_ylim(0.0, c.max() + 0.8)
    ax1.xaxis.set_major_locator(mticker.MultipleLocator(1.0))
    ax1.yaxis.set_major_locator(mticker.MultipleLocator(1.0))

    ax2.plot(q, cm, color="#7C3AED", linewidth=2.3, marker="o", markersize=7.2, zorder=3)
    ax2.scatter([q[1]], [cm[1]], s=120, color=GREEN, edgecolor="white", linewidth=1.1, zorder=4)

    for idx, mc in enumerate(marginal):
        ax2.hlines(mc, q[idx], q[idx + 1], color=RED, linewidth=3.0, zorder=2)
        ax2.scatter([q_mid[idx]], [mc], s=58, color=RED, edgecolor="white", linewidth=0.9, zorder=4)
    ax2.vlines(q[1], marginal[0], marginal[1], color=RED, linestyle=":", linewidth=1.2, alpha=0.9, zorder=1)

    cm_offsets = [(-8, 10), (0, 10), (0, 10)]
    for x, y, run_id, (dx, dy) in zip(q, cm, run_ids, cm_offsets):
        txt = ax2.annotate(
            f"{run_id}\n${y:.2f}",
            xy=(x, y),
            xytext=(dx, dy),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=8.3,
            color=GREEN if run_id == 165 else "#5B21B6",
            fontweight="bold" if run_id == 165 else "normal",
        )
        txt.set_path_effects([pe.withStroke(linewidth=2.4, foreground="white")])

    for x, y, label in zip(q_mid, marginal, ["161→165", "165→171"]):
        txt = ax2.annotate(
            f"{label}\n${y:.2f}",
            xy=(x, y),
            xytext=(0, -14),
            textcoords="offset points",
            ha="center",
            va="top",
            fontsize=8.1,
            color=RED,
            fontweight="bold",
        )
        txt.set_path_effects([pe.withStroke(linewidth=2.4, foreground="white")])

    ax2.annotate(
        f"Au point 165 :\nCm_gauche < CM < Cm_droite\n{marginal[0]:.2f} < {cm[1]:.2f} < {marginal[1]:.2f}",
        xy=(q[1], cm[1]),
        xytext=(0.54, 0.77),
        textcoords="axes fraction",
        arrowprops=dict(arrowstyle="->", color=GREEN, lw=1.2),
        fontsize=8.8,
        color=GREEN,
        ha="left",
        va="top",
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#D1D5DB", alpha=0.95),
    )

    ax2.set_title("Coût moyen et coût marginal discrets", fontsize=12.6, fontweight="bold")
    ax2.set_xlabel("q = surplus de VF au-dessus de 80% (points)")
    ax2.set_ylabel("Coût par point ($/pp)")
    ax2.set_xlim(q.min() - 0.5, q.max() + 0.6)
    ax2.set_ylim(0.0, 1.25)
    ax2.xaxis.set_major_locator(mticker.MultipleLocator(1.0))
    ax2.yaxis.set_major_locator(mticker.MultipleLocator(0.2))

    legend_elements = [
        Line2D([0], [0], color="#7C3AED", linewidth=2.3, marker="o", markersize=6.5, label="CM = C(q) / q"),
        Line2D([0], [0], color=RED, linewidth=3.0, marker="o", markersize=5.8, label="Cm discret = ΔC / Δq"),
        Line2D([0], [0], color=GREEN, linestyle="--", linewidth=2.0, label="run 165 mis en évidence"),
    ]
    ax2.legend(handles=legend_elements, loc="upper left", fontsize=8.6, frameon=True, edgecolor="#D1D5DB")

    fig.suptitle("Coût moyen vs coût marginal sur la frontière de Pareto", fontsize=14.2, fontweight="bold", y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    path = OUTPUT_DIR / "05_marginal_cost_per_pp.png"
    fig.savefig(path, bbox_inches="tight")
    print(f"  -> {path}")
    plt.close(fig)


def main() -> None:
    print("Generation des visuels micro-economiques alpha...")
    metrics = _load_run_metrics()
    plot_pareto(metrics)
    plot_cost_function(metrics)
    plot_cost_function_smooth(metrics)
    plot_production_map(metrics)
    plot_factorial_returns(metrics)
    plot_marginal_cost_per_pp(metrics)
    plot_cost_curves_calibrated(metrics)
    print("Done.")


if __name__ == "__main__":
    main()
