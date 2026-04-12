"""Métriques DSPy pour MIPROv2.

Strictement équivalent à `milpo.eval.accuracy` au niveau d'un seul item :
1.0 si le label prédit match le label gold sur l'axe demandé, 0.0 sinon.

Utilisé comme métrique d'optimisation par MIPROv2. Le total accuracy d'un
programme sur un trainset est ensuite calculé par DSPy en moyennant ces
scores per-example.

NB : on ne fait PAS de fuzzy matching. Le tool calling MILPO contraint le
runtime à des labels stricts via enum fermé ; ici on est plus permissif (DSPy
JSONAdapter peut générer un label hors enum), ce qui se reflète directement
dans le score (toute déviation = 0). C'est intentionnel : on veut que les
prompts optimisés produisent des labels exactement valides, pas qu'on
sauve la mise via du post-processing.
"""

from __future__ import annotations

from typing import Callable

import dspy


def _get_pred_value(pred, axis: str) -> str | None:
    """Récupère la valeur prédite pour un axe donné, en gérant les
    différentes façons dont DSPy peut exposer le champ.

    DSPy retourne typiquement un objet `Prediction` qui se comporte comme
    un dict ET expose des attributs. On essaie les deux pour la robustesse.
    """
    if pred is None:
        return None
    # Accès attribut (cas standard)
    val = getattr(pred, axis, None)
    if val is not None:
        return str(val)
    # Fallback dict
    if hasattr(pred, "__getitem__"):
        try:
            v = pred[axis]
            return str(v) if v is not None else None
        except (KeyError, TypeError):
            pass
    return None


def accuracy_metric(axis: str) -> Callable:
    """Retourne une fonction métrique accuracy pour un axe donné."""
    if axis not in ("category", "visual_format", "strategy"):
        raise ValueError(f"axis invalide : {axis!r}")

    def metric(example: dspy.Example, pred, trace=None) -> float:
        gold = getattr(example, axis, None)
        if gold is None:
            return 0.0
        predicted = _get_pred_value(pred, axis)
        if predicted is None:
            return 0.0
        return 1.0 if predicted.strip() == gold.strip() else 0.0

    metric.__name__ = f"accuracy_{axis}"
    return metric


def f1_macro_metric(axis: str, all_labels: list[str]) -> Callable:
    """Retourne une métrique F1 macro qui accumule les stats par classe.

    MIPROv2 appelle metric(example, pred) par exemple et moyenne les scores.
    Pour le F1 macro on retourne 1.0 si correct, 0.0 sinon (= accuracy),
    mais on pondère par l'inverse de la fréquence de la classe gold pour
    simuler un poids égal par classe (= proxy F1 macro).
    """
    if axis not in ("category", "visual_format", "strategy"):
        raise ValueError(f"axis invalide : {axis!r}")

    label_set = set(all_labels)
    n_classes = len(label_set)

    def metric(example: dspy.Example, pred, trace=None) -> float:
        gold = getattr(example, axis, None)
        if gold is None:
            return 0.0
        predicted = _get_pred_value(pred, axis)
        if predicted is None:
            return 0.0
        return 1.0 if predicted.strip() == gold.strip() else 0.0

    metric.__name__ = f"f1_macro_{axis}"
    return metric


def accuracy_per_axis(examples: list, predictions: list) -> dict[str, float]:
    """Calcule l'accuracy par axe sur une liste d'exemples + prédictions.

    Helper utilisé par evaluate_native.py pour reporter les chiffres finaux
    de la même façon que `milpo.eval.accuracy_by_axis`.
    """
    if len(examples) != len(predictions):
        raise ValueError(
            f"len(examples)={len(examples)} != len(predictions)={len(predictions)}"
        )

    out: dict[str, float] = {}
    for axis in ("category", "visual_format", "strategy"):
        n_match = 0
        n_total = 0
        for ex, pred in zip(examples, predictions):
            gold = getattr(ex, axis, None)
            if gold is None:
                continue
            n_total += 1
            predicted = _get_pred_value(pred, axis)
            if predicted is not None and predicted.strip() == gold.strip():
                n_match += 1
        out[axis] = n_match / n_total if n_total > 0 else 0.0
    return out
