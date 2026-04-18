"""Triptyque d'analyse de sensibilité AMCD.

Cadrage : modèle paramétrique de préférences, PAS identification.
Trois formes d'utilité U(q) prescrites (log, sigmoïde, seuil SLA),
analyse de sensibilité au prix implicite lambda du dollar.

- Panel 1 : les 3 U(q) continues + 8 points discrets superposés
- Panel 2 : utilité nette U(q) - lambda.C par config, 3 valeurs de lambda
- Panel 3 : carte a*(lambda) — quelle config est optimale selon lambda
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import numpy as np
from matplotlib.gridspec import GridSpec

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

RUNS = [
    (161, "alma qwen",           82.2, 2.33, True),
    (165, "simple fl-lite\nsans ASSIST", 85.4, 3.05, True),
    (164, "simple fl-lite ASSIST",      84.9, 3.25, False),
    (158, "alma flash-lite",          83.8, 3.67, False),
    (159, "alma flash",               83.6, 4.62, False),
    (167, "simple flash\nsans ASSIST",   85.3, 4.92, False),
    (171, "simple flash ASSIST",        87.8, 5.18, True),
    (160, "alma full-flash",          86.7, 7.72, False),
]

VF0 = 85.0
K_SIGMOID = 0.8
VF_MIN = 80.0
VF_THRESHOLD = 85.0


def U_log(vf):
    q = np.maximum(vf - VF_MIN, 0.001)
    return np.log(1 + q) / np.log(1 + 10)


def U_sigmoid(vf):
    return 1.0 / (1.0 + np.exp(-K_SIGMOID * (vf - VF0)))


def U_threshold(vf):
    return (np.asarray(vf) >= VF_THRESHOLD).astype(float)


UTILITIES = [
    ("Log concave",   U_log,        BLUE_DARK, "-"),
    ("Sigmoide (SLA doux)", U_sigmoid, PURPLE, "-"),
    ("Seuil dur (SLA 85%)", U_threshold, RED,   "--"),
]

OUT = "/Users/mathias/Desktop/mémoire-v2/docs"


def main():
    fig = plt.figure(figsize=(17, 5.8))
    gs = GridSpec(1, 3, width_ratios=[1.1, 1.2, 1.1], wspace=0.28,
                  left=0.05, right=0.98, top=0.86, bottom=0.14)

    ax1 = fig.add_subplot(gs[0])
    ax2 = fig.add_subplot(gs[1])
    ax3 = fig.add_subplot(gs[2])

    # ── Panel 1 : fonctions d'utilité ──────────────────────────────────

    ax1.set_axisbelow(True)
    ax1.grid(True, color="#E5E7EB", linewidth=0.5, alpha=0.7)

    vf_range = np.linspace(80, 90, 400)
    for name, U_fn, color, style in UTILITIES:
        ax1.plot(vf_range, U_fn(vf_range), color=color, linewidth=2.2,
                 linestyle=style, label=name, zorder=3)

    for run_id, label, vf, cost, is_pareto in RUNS:
        u_avg = np.mean([U_fn(vf) for _, U_fn, _, _ in UTILITIES])
        marker_style = "o" if is_pareto else "X"
        size = 100 if is_pareto else 70
        ax1.axvline(vf, color=GREY, linewidth=0.4, alpha=0.3, zorder=1)
        ax1.scatter([vf]*3,
                    [U_log(vf), U_sigmoid(vf), U_threshold(vf)],
                    s=size, marker=marker_style,
                    facecolor="white" if not is_pareto else None,
                    edgecolor=[BLUE_DARK, PURPLE, RED],
                    linewidth=1.2, zorder=5)

    ax1.axvline(VF_THRESHOLD, color=GREY, linestyle=":", linewidth=1, alpha=0.6)
    ax1.text(VF_THRESHOLD + 0.08, 0.02, "seuil SLA\n= 85%",
             fontsize=7.5, color=SLATE, va="bottom")

    ax1.set_xlabel("Accuracy VF (%)", fontsize=11, labelpad=6)
    ax1.set_ylabel("Utilité U(VF)  [normalisée]", fontsize=11, labelpad=6)
    ax1.set_title("Trois formes de préférences prescrites",
                  fontsize=12, fontweight="bold", pad=10)
    ax1.set_xlim(80, 90)
    ax1.set_ylim(-0.05, 1.1)
    ax1.legend(loc="upper left", fontsize=8.5, framealpha=0.95,
               edgecolor="#ddd", fancybox=False)

    ax1.text(0.98, 0.04,
             "echelle U arbitraire\ncomparaisons relatives\nuniquement",
             transform=ax1.transAxes, ha="right", va="bottom",
             fontsize=7.5, color=SLATE, style="italic",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                       edgecolor="#ddd", linewidth=0.5))

    # ── Panel 2 : utilité nette par config (sigmoïde, 3 lambdas) ────────

    ax2.set_axisbelow(True)
    ax2.grid(axis="y", color="#E5E7EB", linewidth=0.5, alpha=0.7)

    lambdas = [0.05, 0.15, 0.30]
    lambda_colors = [GREEN, AMBER, RED]
    labels_display = [f"{r[0]}" for r in RUNS]
    vfs = np.array([r[2] for r in RUNS])
    costs = np.array([r[3] for r in RUNS])
    is_pareto_mask = np.array([r[4] for r in RUNS])

    U_vals = U_sigmoid(vfs)

    n_configs = len(RUNS)
    width = 0.27
    x = np.arange(n_configs)

    for i, (lam, c) in enumerate(zip(lambdas, lambda_colors)):
        net = U_vals - lam * costs
        offset = (i - 1) * width
        bars = ax2.bar(x + offset, net, width, color=c, edgecolor="white",
                       linewidth=0.8, label=rf"$\lambda$ = {lam}", zorder=3)
        best_idx = np.argmax(net)
        bars[best_idx].set_edgecolor("black")
        bars[best_idx].set_linewidth(2)

    for xi, is_p in zip(x, is_pareto_mask):
        if is_p:
            ax2.axvspan(xi - 0.45, xi + 0.45, color=BLUE, alpha=0.05, zorder=1)

    ax2.axhline(0, color="black", linewidth=0.5, alpha=0.5)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels_display, fontsize=8.5)
    ax2.set_xlabel("Run (configuration)", fontsize=11, labelpad=6)
    ax2.set_ylabel(r"Utilité nette  $U(VF) - \lambda \cdot C$", fontsize=11, labelpad=6)
    ax2.set_title("Qui gagne selon le prix implicite du dollar λ\n(utilité sigmoïde)",
                  fontsize=11.5, fontweight="bold", pad=10)
    ax2.legend(loc="lower left", fontsize=9, framealpha=0.95,
               edgecolor="#ddd", fancybox=False, title=r"Prix du \$")

    ax2.text(0.98, 0.97, "bord noir = config optimale\nfond bleu = Pareto-optimal",
             transform=ax2.transAxes, ha="right", va="top",
             fontsize=7.5, color=SLATE, style="italic",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                       edgecolor="#ddd", linewidth=0.5))

    # ── Panel 3 : carte a*(lambda) ──────────────────────────────────────

    ax3.set_axisbelow(True)
    ax3.grid(True, color="#E5E7EB", linewidth=0.5, alpha=0.7)

    lambda_range = np.linspace(0.01, 0.8, 400)

    for name, U_fn, color, style in UTILITIES:
        U_vals_all = U_fn(vfs)
        best_q_trace = []
        for lam in lambda_range:
            net = U_vals_all - lam * costs
            best_idx = int(np.argmax(net))
            best_q_trace.append(vfs[best_idx] - VF_MIN)
        ax3.plot(lambda_range, best_q_trace, color=color, linewidth=2.3,
                 linestyle=style, label=name, zorder=3, drawstyle="steps-post")

    pareto_qs = sorted([vf - VF_MIN for _, _, vf, _, is_p in RUNS if is_p])
    pareto_labels = {
        (vf - VF_MIN): f"{run_id}"
        for run_id, _, vf, _, is_p in RUNS if is_p
    }
    for q_p in pareto_qs:
        ax3.axhline(q_p, color=GREY, linewidth=0.5, linestyle=":", alpha=0.7, zorder=1)
        ax3.text(0.79, q_p + 0.1, f"run {pareto_labels[q_p]}  (q={q_p:.1f})",
                 fontsize=7.5, color=SLATE, ha="right", va="bottom")

    ax3.set_xlabel(r"Prix implicite du dollar  $\lambda$", fontsize=11, labelpad=6)
    ax3.set_ylabel(r"$q^* = VF(a^*) - 80$  (points de pourcentage)",
                   fontsize=11, labelpad=6)
    ax3.set_title("Quelle config est optimale selon λ ?",
                  fontsize=12, fontweight="bold", pad=10)
    ax3.set_xlim(0, 0.8)
    ax3.set_ylim(1.5, 8.5)
    ax3.legend(loc="upper right", fontsize=8.5, framealpha=0.95,
               edgecolor="#ddd", fancybox=False, title="Fonction d'utilité")

    # ── Global ─────────────────────────────────────────────────────────

    fig.suptitle(
        "Fermeture par préférences — analyse de sensibilité AMCD sur les 8 configurations",
        fontsize=13.5, fontweight="bold", y=0.97, color="#1E293B",
    )

    fig.savefig(f"{OUT}/ablation_alpha_utility.png", dpi=300, bbox_inches="tight",
                facecolor="white")
    fig.savefig(f"{OUT}/ablation_alpha_utility.pdf", bbox_inches="tight",
                facecolor="white")
    print(f"  -> {OUT}/ablation_alpha_utility.png")
    print(f"  -> {OUT}/ablation_alpha_utility.pdf")
    plt.close(fig)


if __name__ == "__main__":
    main()
