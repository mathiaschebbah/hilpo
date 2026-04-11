"""Objectif composite J pour l'optimisation structurée MILPO.

J = 0.6 · macroF1(visual_format)
  + 0.25 · macroF1(category)
  + 0.15 · accuracy(strategy)

Justification des poids :
- visual_format (0.6) : axe le plus difficile (65.4% B0), longue traîne 42 classes
- category (0.25) : 15 classes, macroF1 protège la longue traîne
- strategy (0.15) : binaire (Organic/Brand Content), 94.5% B0, accuracy suffit
"""

from __future__ import annotations

from collections import Counter

WEIGHT_VF = 0.60
WEIGHT_CAT = 0.25
WEIGHT_STRAT = 0.15


def macro_f1(y_true: list[str], y_pred: list[str]) -> float:
    """Calcule le macro-F1 : moyenne non pondérée des F1 par classe.

    Implémentation manuelle (pas de dépendance sklearn).
    Classes présentes dans y_true mais jamais prédites → F1=0 pour cette classe.
    """
    if not y_true or not y_pred or len(y_true) != len(y_pred):
        return 0.0

    classes = set(y_true)
    if not classes:
        return 0.0

    f1_scores: list[float] = []
    for cls in classes:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p == cls)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != cls and p == cls)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p != cls)

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0

        if precision + recall > 0:
            f1_scores.append(2 * precision * recall / (precision + recall))
        else:
            f1_scores.append(0.0)

    return sum(f1_scores) / len(f1_scores) if f1_scores else 0.0


def accuracy(y_true: list[str], y_pred: list[str]) -> float:
    """Taux de prédictions correctes."""
    if not y_true or not y_pred or len(y_true) != len(y_pred):
        return 0.0
    return sum(1 for t, p in zip(y_true, y_pred) if t == p) / len(y_true)


def compute_j(
    vf_true: list[str],
    vf_pred: list[str],
    cat_true: list[str],
    cat_pred: list[str],
    strat_true: list[str],
    strat_pred: list[str],
) -> float:
    """Calcule l'objectif composite J.

    Returns:
        J ∈ [0, 1]. Plus élevé = meilleur.
    """
    j_vf = macro_f1(vf_true, vf_pred)
    j_cat = macro_f1(cat_true, cat_pred)
    j_strat = accuracy(strat_true, strat_pred)

    return WEIGHT_VF * j_vf + WEIGHT_CAT * j_cat + WEIGHT_STRAT * j_strat


def compute_j_components(
    vf_true: list[str],
    vf_pred: list[str],
    cat_true: list[str],
    cat_pred: list[str],
    strat_true: list[str],
    strat_pred: list[str],
) -> dict[str, float]:
    """Retourne les composantes détaillées de J pour le logging."""
    return {
        "macroF1_vf": macro_f1(vf_true, vf_pred),
        "macroF1_cat": macro_f1(cat_true, cat_pred),
        "acc_strat": accuracy(strat_true, strat_pred),
        "J": compute_j(vf_true, vf_pred, cat_true, cat_pred, strat_true, strat_pred),
    }
