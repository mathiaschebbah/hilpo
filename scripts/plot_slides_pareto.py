"""Generate Anthropic-styled Pareto plots for slides — alpha & test, each a standalone PNG."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.ticker as mticker
from matplotlib.lines import Line2D

OUT = Path("/Users/mathias/Desktop/mémoire-v2/docs/claude_writes/slides/assets")
OUT.mkdir(parents=True, exist_ok=True)

CREAM = "#F0EEE6"
CREAM_PANEL = "#FDFCF6"
INK = "#141413"
MUTED = "#6B6B65"
GRID = "#D7D3C6"
ACCENT = "#CC785C"
ACCENT_DARK = "#BD5D3A"
DOMINATED = "#9A968A"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["DejaVu Serif", "Georgia", "Times New Roman"],
    "font.size": 13,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.edgecolor": INK,
    "axes.linewidth": 1.1,
    "figure.facecolor": CREAM,
    "axes.facecolor": CREAM_PANEL,
    "savefig.dpi": 220,
    "savefig.facecolor": CREAM,
    "xtick.major.width": 0.9,
    "ytick.major.width": 0.9,
    "xtick.color": INK,
    "ytick.color": INK,
})


@dataclass(frozen=True)
class Run:
    run_id: int
    label: str
    vf: float
    cpp: float            # centimes per post
    is_pareto: bool
    note: str | None = None


ALPHA = [
    Run(161, "alma qwen",                   82.2, 0.62, True,  None),
    Run(158, "alma fl-lite",                83.8, 0.94, False, None),
    Run(159, "alma flash",                  83.6, 1.18, False, None),
    Run(160, "alma full-flash",             86.7, 1.98, False, None),
    Run(164, "simple fl-lite ASSIST",       84.9, 0.83, False, None),
    Run(165, "simple fl-lite sans ASSIST",  85.4, 0.78, True,  "sweet spot · 85.4% @ 0.78¢"),
    Run(167, "simple flash",                85.3, 1.27, False, None),
    Run(171, "simple flash ASSIST",         87.8, 1.34, True,  "acc max · 87.8% @ 1.34¢"),
]

TEST = [
    Run(172, "alma fl-lite",                82.72, 0.973, False, None),
    Run(176, "simple fl-lite ASSIST",       86.91, 0.852, False, None),
    Run(177, "simple fl-lite sans ASSIST",  87.16, 0.795, True,  "sweet spot · 87.2% @ 0.79¢"),
    Run(178, "alma qwen",                   83.81, 0.616, True,  None),
    Run(181, "simple flash ASSIST",         89.58, 1.362, True,  "acc max · 89.6% @ 1.36¢"),
    Run(182, "alma flash",                  88.15, 1.225, True,  None),
    Run(183, "alma full-flash",             85.19, 1.933, False, None),
    Run(185, "simple flash sans ASSIST",    87.59, 1.293, False, None),
]


def _plot(runs: list[Run], title: str, out_name: str, *,
          xlim: tuple[float, float], ylim: tuple[float, float],
          label_offsets: dict[int, tuple[float, float, str]]) -> None:
    fig, ax = plt.subplots(figsize=(15.5, 6.0))

    ax.set_axisbelow(True)
    ax.grid(True, color=GRID, linewidth=0.6, alpha=0.7, linestyle=(0, (2, 3)))

    # Frontière Pareto
    pareto = sorted([r for r in runs if r.is_pareto], key=lambda r: r.cpp)
    px = [r.cpp for r in pareto]
    py = [r.vf for r in pareto]
    ax.plot(px, py, color=ACCENT, linestyle=(0, (5, 3)), linewidth=2.3, alpha=0.9, zorder=2)

    # Points dominés
    for r in runs:
        if r.is_pareto:
            continue
        ax.scatter(r.cpp, r.vf, s=95, marker="o",
                   facecolor=DOMINATED, edgecolor="white", linewidth=1.2, zorder=3)

    # Points Pareto
    for r in runs:
        if not r.is_pareto:
            continue
        is_sweet = r.note is not None and "sweet spot" in r.note
        if is_sweet:
            ax.scatter(r.cpp, r.vf, s=340, marker="o",
                       facecolor=ACCENT, edgecolor=ACCENT_DARK, linewidth=2.2, zorder=5)
            ax.scatter(r.cpp, r.vf, s=120, marker="*",
                       facecolor="white", edgecolor="none", zorder=6)
        else:
            ax.scatter(r.cpp, r.vf, s=180, marker="o",
                       facecolor=ACCENT, edgecolor=ACCENT_DARK, linewidth=1.6, zorder=5)

    # Labels
    for r in runs:
        dx, dy, ha = label_offsets.get(r.run_id, (9, 0, "left"))
        is_sweet = r.note is not None and "sweet spot" in r.note
        is_acc_max = r.note is not None and "acc max" in r.note
        color = ACCENT_DARK if r.is_pareto else MUTED
        weight = "bold" if r.is_pareto else "normal"
        size = 12.5 if r.is_pareto else 11
        main = f"{r.run_id} · {r.label}"
        txt = ax.annotate(
            main,
            xy=(r.cpp, r.vf),
            xytext=(dx, dy),
            textcoords="offset points",
            ha=ha,
            va="center",
            fontsize=size,
            color=color,
            fontweight=weight,
        )
        txt.set_path_effects([pe.withStroke(linewidth=3.2, foreground=CREAM_PANEL)])

        if r.note:
            sub = r.note
            txt2 = ax.annotate(
                sub,
                xy=(r.cpp, r.vf),
                xytext=(dx, dy - 14),
                textcoords="offset points",
                ha=ha,
                va="center",
                fontsize=10.5,
                color=MUTED,
                fontstyle="italic",
            )
            txt2.set_path_effects([pe.withStroke(linewidth=3.0, foreground=CREAM_PANEL)])

    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_xlabel("Coût par post (centimes)", fontsize=13.5, color=INK)
    ax.set_ylabel("Accuracy Visual Format (%)", fontsize=13.5, color=INK)
    ax.xaxis.set_major_locator(mticker.MultipleLocator(0.25))
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:.2f}¢"))
    ax.yaxis.set_major_locator(mticker.MultipleLocator(1))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v)}"))
    ax.tick_params(axis="both", labelsize=11.5, pad=5)

    legend_elements = [
        Line2D([0], [0], marker="*", color="w", markerfacecolor=ACCENT,
               markeredgecolor=ACCENT_DARK, markersize=16,
               markeredgewidth=1.2, linewidth=0, label="Sweet spot"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=ACCENT,
               markeredgecolor=ACCENT_DARK, markersize=12, label="Pareto-optimal"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor=DOMINATED,
               markeredgecolor="white", markersize=10, label="Dominé"),
        Line2D([0], [0], color=ACCENT, linestyle=(0, (5, 3)), linewidth=2.3, label="Frontière Pareto"),
    ]
    leg = ax.legend(handles=legend_elements, loc="lower right", fontsize=11,
                    frameon=True, edgecolor=GRID, facecolor=CREAM_PANEL)
    leg.get_frame().set_linewidth(0.8)

    # No title — the slide already has an H2 title above the image.

    plt.tight_layout()
    out_path = OUT / out_name
    fig.savefig(out_path, bbox_inches="tight", facecolor=CREAM)
    plt.close(fig)
    print(f"  -> {out_path}")


ALPHA_OFFSETS = {
    161: (14, 6, "left"),
    165: (16, 0, "left"),
    171: (14, 0, "left"),
    158: (12, 0, "left"),
    159: (12, 0, "left"),
    160: (-12, 8, "right"),
    164: (-12, 0, "right"),
    167: (12, 0, "left"),
}

TEST_OFFSETS = {
    178: (14, 4, "left"),
    177: (16, 0, "left"),
    182: (14, 2, "left"),
    181: (14, 0, "left"),
    176: (-2, -28, "right"),
    172: (14, 0, "left"),
    185: (14, -14, "left"),
    183: (-12, 0, "right"),
}


def main() -> None:
    print("Generating Pareto plots for slides...")
    _plot(
        ALPHA,
        "Alpha — frontière de Pareto coût × accuracy",
        "pareto_alpha.png",
        xlim=(0.45, 2.15),
        ylim=(81.4, 89.0),
        label_offsets=ALPHA_OFFSETS,
    )
    _plot(
        TEST,
        "Test — même winner Pareto",
        "pareto_test.png",
        xlim=(0.45, 2.15),
        ylim=(81.8, 90.4),
        label_offsets=TEST_OFFSETS,
    )
    print("Done.")


if __name__ == "__main__":
    main()
