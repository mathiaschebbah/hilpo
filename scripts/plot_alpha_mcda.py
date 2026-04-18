#!/usr/bin/env python3
"""Generate MCDA figures for the alpha ablation note."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import warnings

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.ticker as mticker
import numpy as np
import psycopg
from matplotlib.colors import ListedColormap
from matplotlib.lines import Line2D
from scipy.optimize import curve_fit

from plot_ablation_alpha import ALPHA_RUN_IDS, DATABASE_DSN, RUN_SPECS_BY_ID


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "docs" / "assets" / "mcda"
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
    }
)

BLUE = "#2563EB"
BLUE_DARK = "#1E3A8A"
GREY = "#9CA3AF"
SLATE = "#475569"
RED = "#DC2626"
GREEN = "#059669"
AMBER = "#D97706"


@dataclass(frozen=True)
class ActionMetric:
    run_id: int
    cost_usd: float
    n_posts: int
    n_correct: int

    @property
    def accuracy_pct(self) -> float:
        return 100.0 * self.n_correct / self.n_posts

    @property
    def action_label(self) -> str:
        return rf"$a_{{{self.run_id}}}$"

    @property
    def surplus_q(self) -> float:
        return self.accuracy_pct - 80.0

    @property
    def average_return(self) -> float:
        return self.surplus_q / self.cost_usd

    @property
    def cost_per_post_usd(self) -> float:
        return self.cost_usd / self.n_posts


def _load_metrics() -> list[ActionMetric]:
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
        ActionMetric(
            run_id=int(run_id),
            cost_usd=float(cost_usd),
            n_posts=int(n_posts),
            n_correct=int(n_correct),
        )
        for run_id, cost_usd, n_posts, n_correct in rows
    ]
    if len(metrics) != len(ALPHA_RUN_IDS):
        raise RuntimeError("Alpha MCDA metrics are incomplete.")
    return metrics


def _dominates(left: ActionMetric, right: ActionMetric) -> bool:
    if left.run_id == right.run_id:
        return False
    same_or_lower_cost = left.cost_usd <= right.cost_usd
    same_or_higher_acc = left.accuracy_pct >= right.accuracy_pct
    strictly_better = left.cost_usd < right.cost_usd or left.accuracy_pct > right.accuracy_pct
    return same_or_lower_cost and same_or_higher_acc and strictly_better


def _dominates_cost_per_post(left: ActionMetric, right: ActionMetric) -> bool:
    if left.run_id == right.run_id:
        return False
    same_or_lower_cost = left.cost_per_post_usd <= right.cost_per_post_usd
    same_or_higher_acc = left.accuracy_pct >= right.accuracy_pct
    strictly_better = left.cost_per_post_usd < right.cost_per_post_usd or left.accuracy_pct > right.accuracy_pct
    return same_or_lower_cost and same_or_higher_acc and strictly_better


def _compute_frontier(metrics: list[ActionMetric]) -> list[ActionMetric]:
    frontier = []
    for candidate in metrics:
        if any(_dominates(other, candidate) for other in metrics):
            continue
        frontier.append(candidate)
    return frontier


def _compute_frontier_cost_per_post(metrics: list[ActionMetric]) -> list[ActionMetric]:
    frontier = []
    for candidate in metrics:
        if any(_dominates_cost_per_post(other, candidate) for other in metrics):
            continue
        frontier.append(candidate)
    return frontier


def _power_cost(q: np.ndarray, fixed_cost: float, alpha: float, gamma: float) -> np.ndarray:
    return fixed_cost + alpha * np.power(q, gamma)


def _fit_power_cost_curve(frontier: list[ActionMetric]) -> tuple[float, float, float]:
    q = np.array([metric.surplus_q for metric in frontier], dtype=float)
    c = np.array([metric.cost_usd for metric in frontier], dtype=float)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        params, _ = curve_fit(
            _power_cost,
            q,
            c,
            p0=[2.0, 0.01, 2.5],
            bounds=([0.0, 0.0, 1.0001], [10.0, 10.0, 10.0]),
        )
    return tuple(float(value) for value in params)


def plot_frontier(metrics: list[ActionMetric]) -> None:
    frontier = _compute_frontier(metrics)
    frontier_ids = {metric.run_id for metric in frontier}

    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.set_axisbelow(True)
    ax.grid(True, color="#E5E7EB", linewidth=0.6, alpha=0.8)

    ax.plot(
        [metric.cost_usd for metric in frontier],
        [metric.accuracy_pct for metric in frontier],
        color=RED,
        linestyle="--",
        linewidth=2.1,
        zorder=2,
    )

    for metric in metrics:
        is_frontier = metric.run_id in frontier_ids
        if is_frontier:
            ax.scatter(
                metric.cost_usd,
                metric.accuracy_pct,
                s=145,
                marker="o",
                facecolor=BLUE,
                edgecolor=BLUE_DARK,
                linewidth=1.1,
                zorder=4,
            )
        else:
            ax.scatter(
                metric.cost_usd,
                metric.accuracy_pct,
                s=115,
                marker="x",
                color=GREY,
                linewidths=2.0,
                zorder=4,
            )

        offset = (10, 8) if is_frontier else (8, -2)
        label = ax.annotate(
            metric.action_label,
            xy=(metric.cost_usd, metric.accuracy_pct),
            xytext=offset,
            textcoords="offset points",
            ha="left",
            va="bottom" if is_frontier else "center",
            fontsize=10.5,
            color=BLUE_DARK if is_frontier else SLATE,
            fontweight="bold" if is_frontier else "normal",
        )
        label.set_path_effects([pe.withStroke(linewidth=3.0, foreground="white")])

    ax.set_xlabel("Coût total $C(a)$ (USD)")
    ax.set_ylabel("Performance $g_2(a)$ = accuracy VF (\\%)")
    ax.set_title("Frontière de Pareto sur les 8 actions observées", fontsize=12.5, fontweight="bold")
    ax.set_xlim(1.9, 8.5)
    ax.set_ylim(81.0, 89.0)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(1.0))

    legend_elements = [
        Line2D([0], [0], marker="o", linestyle="", color=BLUE, markeredgecolor=BLUE_DARK, markerfacecolor=BLUE, markersize=9, label="Action efficace"),
        Line2D([0], [0], marker="x", linestyle="", color=GREY, markersize=9, markeredgewidth=1.8, label="Action dominée"),
        Line2D([0], [0], color=RED, linestyle="--", linewidth=2.1, label="Frontière de Pareto"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", frameon=True, edgecolor="#D1D5DB", fontsize=8.8)

    path = OUTPUT_DIR / "alpha_pareto_frontier.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    print(f"  -> {path}")
    plt.close(fig)


def plot_pareto_cost_per_post(metrics: list[ActionMetric]) -> None:
    frontier = _compute_frontier_cost_per_post(metrics)
    frontier_ids = {metric.run_id for metric in frontier}

    fig, ax = plt.subplots(figsize=(7.2, 4.8))
    ax.set_axisbelow(True)
    ax.grid(True, color="#E5E7EB", linewidth=0.6, alpha=0.8)

    ax.plot(
        [metric.cost_per_post_usd for metric in frontier],
        [metric.accuracy_pct for metric in frontier],
        color=RED,
        linestyle="--",
        linewidth=2.1,
        zorder=2,
    )

    for metric in metrics:
        is_frontier = metric.run_id in frontier_ids
        if is_frontier:
            ax.scatter(
                metric.cost_per_post_usd,
                metric.accuracy_pct,
                s=145,
                marker="o",
                facecolor=BLUE,
                edgecolor=BLUE_DARK,
                linewidth=1.1,
                zorder=4,
            )
        else:
            ax.scatter(
                metric.cost_per_post_usd,
                metric.accuracy_pct,
                s=115,
                marker="x",
                color=GREY,
                linewidths=2.0,
                zorder=4,
            )

        offset = (10, 8) if is_frontier else (8, -2)
        label = ax.annotate(
            metric.action_label,
            xy=(metric.cost_per_post_usd, metric.accuracy_pct),
            xytext=offset,
            textcoords="offset points",
            ha="left",
            va="bottom" if is_frontier else "center",
            fontsize=10.5,
            color=BLUE_DARK if is_frontier else SLATE,
            fontweight="bold" if is_frontier else "normal",
        )
        label.set_path_effects([pe.withStroke(linewidth=3.0, foreground="white")])

    ax.set_xlabel(r"Coût par post $C/n$ (USD/post)")
    ax.set_ylabel("Accuracy VF (%)")
    ax.set_title("Frontière de Pareto coût/post-performance (alpha)", fontsize=12.5, fontweight="bold")
    ax.set_xlim(0.0058, 0.0206)
    ax.set_ylim(81.0, 89.0)
    ax.yaxis.set_major_locator(mticker.MultipleLocator(1.0))
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.4f"))

    legend_elements = [
        Line2D([0], [0], marker="o", linestyle="", color=BLUE, markeredgecolor=BLUE_DARK, markerfacecolor=BLUE, markersize=9, label="Action efficace"),
        Line2D([0], [0], marker="x", linestyle="", color=GREY, markersize=9, markeredgewidth=1.8, label="Action dominée"),
        Line2D([0], [0], color=RED, linestyle="--", linewidth=2.1, label="Frontière de Pareto"),
    ]
    ax.legend(handles=legend_elements, loc="lower right", frameon=True, edgecolor="#D1D5DB", fontsize=8.8)

    path = OUTPUT_DIR / "alpha_pareto_cost_per_post.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    print(f"  -> {path}")
    plt.close(fig)


def plot_dominance_matrix(metrics: list[ActionMetric]) -> None:
    frontier_ids = {metric.run_id for metric in _compute_frontier(metrics)}
    matrix = np.array(
        [[1 if _dominates(row_metric, col_metric) else 0 for col_metric in metrics] for row_metric in metrics],
        dtype=int,
    )

    fig, ax = plt.subplots(figsize=(6.3, 5.7))
    cmap = ListedColormap(["#FFFFFF", "#DBEAFE"])
    ax.imshow(matrix, cmap=cmap, vmin=0, vmax=1)

    labels = [rf"$a_{{{metric.run_id}}}$" for metric in metrics]
    ax.set_xticks(np.arange(len(metrics)))
    ax.set_yticks(np.arange(len(metrics)))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_yticklabels(labels, fontsize=10)
    ax.set_xlabel("Action dominée")
    ax.set_ylabel("Action dominatrice")
    ax.set_title("Relation de dominance de Pareto", fontsize=12.5, fontweight="bold")

    ax.set_xticks(np.arange(-0.5, len(metrics), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(metrics), 1), minor=True)
    ax.grid(which="minor", color="#D1D5DB", linewidth=0.8)
    ax.tick_params(which="minor", bottom=False, left=False)

    for row_idx in range(matrix.shape[0]):
        for col_idx in range(matrix.shape[1]):
            if matrix[row_idx, col_idx] == 1:
                ax.text(
                    col_idx,
                    row_idx,
                    "1",
                    ha="center",
                    va="center",
                    fontsize=9.5,
                    color=BLUE_DARK,
                    fontweight="bold",
                )

    for tick_label, metric in zip(ax.get_xticklabels(), metrics):
        if metric.run_id in frontier_ids:
            tick_label.set_color(BLUE_DARK)
            tick_label.set_fontweight("bold")
    for tick_label, metric in zip(ax.get_yticklabels(), metrics):
        if metric.run_id in frontier_ids:
            tick_label.set_color(BLUE_DARK)
            tick_label.set_fontweight("bold")

    ax.text(
        0.5,
        -0.14,
        "Cellule bleue : l'action en ligne domine l'action en colonne.",
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=8.7,
        color=SLATE,
    )

    path = OUTPUT_DIR / "alpha_dominance_matrix.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    print(f"  -> {path}")
    plt.close(fig)


def plot_budget_return(metrics: list[ActionMetric]) -> None:
    frontier = _compute_frontier(metrics)
    frontier_ids = {metric.run_id for metric in frontier}
    fixed_cost, alpha, gamma = _fit_power_cost_curve(frontier)

    q_frontier = np.array([metric.surplus_q for metric in frontier], dtype=float)
    c_frontier = np.array([metric.cost_usd for metric in frontier], dtype=float)
    q_grid = np.linspace(q_frontier.min(), q_frontier.max(), 240)
    return_grid = q_grid / _power_cost(q_grid, fixed_cost, alpha, gamma)

    q_mid = 0.5 * (q_frontier[:-1] + q_frontier[1:])
    marginal_segments = np.diff(q_frontier) / np.diff(c_frontier)
    q_marginal = np.linspace(q_frontier.min(), q_frontier.max(), 260)
    marginal_grid = 1.0 / (alpha * gamma * np.power(q_marginal, gamma - 1.0))

    q_star = (fixed_cost / (alpha * (gamma - 1.0))) ** (1.0 / gamma)
    r_star = q_star / _power_cost(np.array([q_star]), fixed_cost, alpha, gamma)[0]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.8, 5.5), gridspec_kw={"width_ratios": [1.0, 1.05]})

    for ax in (ax1, ax2):
        ax.set_axisbelow(True)
        ax.grid(True, color="#E5E7EB", linewidth=0.6, alpha=0.8)

    ax1.plot(q_grid, return_grid, color=BLUE_DARK, linewidth=2.3, zorder=2)
    for metric in metrics:
        is_frontier = metric.run_id in frontier_ids
        if is_frontier:
            ax1.scatter(
                metric.surplus_q,
                metric.average_return,
                s=130,
                marker="o",
                facecolor=BLUE,
                edgecolor=BLUE_DARK,
                linewidth=1.0,
                zorder=4,
            )
            label = ax1.annotate(
                metric.action_label,
                xy=(metric.surplus_q, metric.average_return),
                xytext=(8, 8),
                textcoords="offset points",
                ha="left",
                va="bottom",
                fontsize=10.2,
                color=BLUE_DARK,
                fontweight="bold",
            )
            label.set_path_effects([pe.withStroke(linewidth=3.0, foreground="white")])
        else:
            ax1.scatter(
                metric.surplus_q,
                metric.average_return,
                s=105,
                marker="x",
                color=GREY,
                linewidths=1.8,
                zorder=3,
            )

    ax1.axvline(q_star, color=GREEN, linestyle=":", linewidth=1.2, alpha=0.9, zorder=1)
    ax1.scatter([q_star], [r_star], s=85, marker="*", color=GREEN, edgecolor="white", linewidth=0.8, zorder=5)
    ax1.annotate(
        rf"$q^\star \approx {q_star:.2f}$" "\n" rf"$r(q^\star) \approx {r_star:.2f}$ pp/\$",
        xy=(q_star, r_star),
        xytext=(12, -10),
        textcoords="offset points",
        ha="left",
        va="top",
        fontsize=8.4,
        color=GREEN,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#D1D5DB", alpha=0.95),
    )

    ax1.text(
        0.03,
        0.96,
        r"$\hat r(q)=q/\hat C(q)$",
        transform=ax1.transAxes,
        ha="left",
        va="top",
        fontsize=9.1,
        color=SLATE,
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#D1D5DB", alpha=0.95),
    )

    ax1.set_title("Rendement moyen du budget", fontsize=12.4, fontweight="bold")
    ax1.set_xlabel(r"$q = VF - 80$ (points)")
    ax1.set_ylabel(r"$r(a)=q(a)/C(a)$ (pp/\$)")
    ax1.set_xlim(q_frontier.min() - 0.35, q_frontier.max() + 0.35)
    ax1.set_ylim(0.5, 1.95)
    ax1.xaxis.set_major_locator(mticker.MultipleLocator(1.0))
    ax1.yaxis.set_major_locator(mticker.MultipleLocator(0.2))

    ax2.plot(q_marginal, marginal_grid, color=RED, linewidth=2.3, zorder=2)
    for idx, (q_left, q_right, value) in enumerate(zip(q_frontier[:-1], q_frontier[1:], marginal_segments)):
        ax2.hlines(value, q_left, q_right, color=BLUE, linewidth=3.0, zorder=3)
        ax2.scatter([(q_left + q_right) / 2.0], [value], s=55, color=BLUE, edgecolor="white", linewidth=0.8, zorder=4)
        label = "161→165" if idx == 0 else "165→171"
        txt = ax2.annotate(
            rf"{label}" "\n" rf"${value:.2f}$ pp/\$",
            xy=((q_left + q_right) / 2.0, value),
            xytext=(0, 10 if idx == 0 else -14),
            textcoords="offset points",
            ha="center",
            va="bottom" if idx == 0 else "top",
            fontsize=8.3,
            color=BLUE_DARK,
            fontweight="bold",
        )
        txt.set_path_effects([pe.withStroke(linewidth=2.6, foreground="white")])

    ax2.axvline(q_star, color=GREEN, linestyle=":", linewidth=1.2, alpha=0.9, zorder=1)
    ax2.scatter([q_star], [r_star], s=85, marker="*", color=GREEN, edgecolor="white", linewidth=0.8, zorder=5)
    ax2.annotate(
        rf"$r_m(q^\star)=r(q^\star)\approx {r_star:.2f}$ pp/\$",
        xy=(q_star, r_star),
        xytext=(10, -10),
        textcoords="offset points",
        ha="left",
        va="top",
        fontsize=8.4,
        color=GREEN,
        bbox=dict(boxstyle="round,pad=0.25", facecolor="white", edgecolor="#D1D5DB", alpha=0.95),
    )

    ax2.text(
        0.97,
        0.96,
        r"$\hat r_m(q)=1/\hat C'(q)$",
        transform=ax2.transAxes,
        ha="right",
        va="top",
        fontsize=9.1,
        color=SLATE,
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#D1D5DB", alpha=0.95),
    )

    ax2.set_title("Rendement marginal du budget", fontsize=12.4, fontweight="bold")
    ax2.set_xlabel(r"$q = VF - 80$ (points)")
    ax2.set_ylabel(r"$r_m=dq/dC$ (pp/\$)")
    ax2.set_xlim(q_frontier.min() - 0.15, q_frontier.max() + 0.35)
    ax2.set_ylim(0.6, 5.4)
    ax2.xaxis.set_major_locator(mticker.MultipleLocator(1.0))
    ax2.yaxis.set_major_locator(mticker.MultipleLocator(0.5))

    fig.suptitle("Lecture duale en rendement du budget", fontsize=14.1, fontweight="bold", y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    path = OUTPUT_DIR / "alpha_budget_return.png"
    fig.savefig(path, bbox_inches="tight")
    print(f"  -> {path}")
    plt.close(fig)


def plot_architecture_constant_returns(metrics: list[ActionMetric]) -> None:
    metric_by_id = {metric.run_id: metric for metric in metrics}

    series = [
        {
            "label": "Alma",
            "run_ids": [161, 158, 159, 160],
            "color": BLUE,
        },
        {
            "label": "Simple sans ASSIST",
            "run_ids": [165, 167],
            "color": AMBER,
        },
        {
            "label": "Simple avec ASSIST",
            "run_ids": [164, 171],
            "color": GREEN,
        },
    ]

    fig, ax = plt.subplots(figsize=(9.6, 5.6))
    ax.set_axisbelow(True)
    ax.grid(True, color="#E5E7EB", linewidth=0.6, alpha=0.8)

    for item in series:
        points = [metric_by_id[run_id] for run_id in item["run_ids"]]
        costs = np.array([metric.cost_usd for metric in points], dtype=float)
        vf = np.array([metric.accuracy_pct for metric in points], dtype=float)
        surplus = vf - 80.0

        order = np.argsort(costs)
        costs = costs[order]
        surplus = surplus[order]
        run_ids = np.array(item["run_ids"], dtype=int)[order]

        c_grid = np.linspace(costs.min(), costs.max(), 320)
        surplus_grid = np.interp(c_grid, costs, surplus)
        return_grid = surplus_grid / c_grid

        ax.plot(
            c_grid,
            return_grid,
            color=item["color"],
            linewidth=2.4,
            alpha=0.95,
            label=item["label"],
            zorder=2,
        )

        offsets = {
            ("Alma", 161): (8, 8),
            ("Alma", 158): (8, -18),
            ("Alma", 159): (8, 8),
            ("Alma", 160): (8, -18),
            ("Simple sans ASSIST", 165): (-110, 18),
            ("Simple sans ASSIST", 167): (8, -18),
            ("Simple avec ASSIST", 164): (8, 8),
            ("Simple avec ASSIST", 171): (8, -18),
        }

        for cost, surplus_value, run_id in zip(costs, surplus, run_ids):
            tier = RUN_SPECS_BY_ID[int(run_id)].tier_label
            yield_value = surplus_value / cost
            ax.scatter(
                cost,
                yield_value,
                s=95,
                color=item["color"],
                edgecolor="white",
                linewidth=0.9,
                zorder=4,
            )
            dx, dy = offsets.get((item["label"], int(run_id)), (8, 8))
            txt = ax.annotate(
                f"{tier} (run {run_id})\n{yield_value:.2f} pp/$",
                xy=(cost, yield_value),
                xytext=(dx, dy),
                textcoords="offset points",
                ha="left",
                va="bottom" if dy >= 0 else "top",
                fontsize=8.0,
                color=item["color"],
                fontweight="bold",
                linespacing=1.05,
            )
            txt.set_path_effects([pe.withStroke(linewidth=2.6, foreground="white")])

    ax.set_title("Courbe de rendement à architecture constante", fontsize=12.8, fontweight="bold")
    ax.set_xlabel("Coût total du run $C$ (USD)")
    ax.set_ylabel(r"$r(C)=(VF-80)/C$ (pp/\$)")
    ax.set_xlim(1.9, 8.4)
    ax.set_ylim(0.45, 1.95)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(0.5))
    ax.yaxis.set_major_locator(mticker.MultipleLocator(0.2))

    ax.text(
        0.03,
        0.96,
        "Courbe = interpolation linéaire de VF entre paliers observés,\npuis rendement moyen du budget $r=(VF-80)/C$.",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8.5,
        color=SLATE,
        bbox=dict(boxstyle="round,pad=0.22", facecolor="white", edgecolor="#D1D5DB", alpha=0.94),
    )

    ax.legend(loc="upper right", fontsize=8.8, frameon=True, edgecolor="#D1D5DB")

    path = OUTPUT_DIR / "alpha_architecture_constant_returns.png"
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    print(f"  -> {path}")
    plt.close(fig)


def main() -> None:
    print("Generate alpha MCDA figures...")
    metrics = _load_metrics()
    plot_frontier(metrics)
    plot_pareto_cost_per_post(metrics)
    plot_dominance_matrix(metrics)
    plot_budget_return(metrics)
    plot_architecture_constant_returns(metrics)
    print("Done.")


if __name__ == "__main__":
    main()
