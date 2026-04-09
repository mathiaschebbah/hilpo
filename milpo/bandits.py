"""Best arm identification pour la boucle ProTeGi de MILPO.

Implémentation post-hoc de Successive Rejects (Audibert & Bubeck 2010, COLT) :
    https://proceedings.mlr.press/v9/audibert10a.html

ProTeGi (Pryzant et al. 2023, EMNLP) recommande Successive Rejects pour la
sélection des candidats post-édition parce que c'est *parameter-free* —
contrairement à UCB-E qui requiert la connaissance d'un paramètre H₁ lié à la
hardness du problème, et qui est typiquement inconnu en pratique.

## Variante post-hoc

L'algorithme original SR alloue dynamiquement un budget de pulls par phase et
élimine progressivement le bras de plus faible moyenne empirique courante. Pour
notre cas (eval_window fixé à l'avance, tous les bras voient les mêmes posts),
on utilise une version *post-hoc* : tous les candidats sont évalués sur le même
eval_window puis classés par accuracy moyenne ; on simule l'élimination
progressive en éliminant à chaque phase le bras de score minimal parmi ceux
qui restent. Le résultat coïncide avec un argmax sur la moyenne empirique, mais
on conserve la trace des K-1 phases d'élimination pour pouvoir l'auditer en
BDD (table rewrite_beam_candidates.sr_phase).

Cette simplification est honnête : elle ne perd pas d'optimalité parce que tous
les bras ont strictement le même nombre d'observations.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SRPhaseResult:
    """Élimination à une phase donnée."""

    phase: int                # 1..K-1
    eliminated_arm_id: int
    eliminated_score: float


@dataclass
class SRResult:
    """Résultat complet d'un Successive Rejects."""

    winner_arm_id: int
    winner_score: float
    phases: list[SRPhaseResult]
    final_scores: dict[int, float]


def _accuracy(matches: list[bool]) -> float:
    if not matches:
        return 0.0
    return sum(matches) / len(matches)


def successive_rejects(
    candidates: dict[int, list[bool]],
    k: int = 1,
) -> SRResult:
    """Successive Rejects post-hoc sur des bras déjà évalués.

    Args:
        candidates: dict {arm_id: list of booleans} où chaque liste est la
            séquence de matches d'un candidat sur le même eval_window.
            Toutes les listes doivent avoir la même longueur (sinon ValueError).
        k: nombre de bras à garder en sortie (top-k). k=1 par défaut renvoie
            uniquement le meilleur. k>1 renvoie le top-k mais le winner reste
            le top-1 dans SRResult.winner_arm_id.

    Returns:
        SRResult avec winner_arm_id (top-1), winner_score, l'historique
        d'élimination phase par phase, et les scores finaux par bras.

    Raises:
        ValueError si candidates est vide ou si les listes n'ont pas la même
        longueur ou si k > len(candidates).
    """
    if not candidates:
        raise ValueError("successive_rejects: aucun candidat")
    if k < 1:
        raise ValueError("successive_rejects: k doit être >= 1")
    if k > len(candidates):
        raise ValueError(
            f"successive_rejects: k={k} > nombre de candidats ({len(candidates)})"
        )

    sample_sizes = {len(matches) for matches in candidates.values()}
    if len(sample_sizes) > 1:
        raise ValueError(
            f"successive_rejects: bras avec sample sizes différents {sample_sizes}"
        )

    final_scores = {arm_id: _accuracy(m) for arm_id, m in candidates.items()}

    # Cas dégénéré : un seul candidat
    if len(candidates) == 1:
        only_id = next(iter(candidates))
        return SRResult(
            winner_arm_id=only_id,
            winner_score=final_scores[only_id],
            phases=[],
            final_scores=final_scores,
        )

    # Élimination progressive : à chaque phase on retire le bras de score min
    # parmi ceux qui restent. Tie-break déterministe par arm_id (le plus petit
    # arm_id est éliminé en cas d'égalité — choix arbitraire mais reproductible).
    remaining = dict(final_scores)
    phases: list[SRPhaseResult] = []
    phase_num = 1
    while len(remaining) > k:
        # Le pire bras = score minimal, tie-break par arm_id ascendant
        worst_id = min(remaining, key=lambda aid: (remaining[aid], aid))
        phases.append(SRPhaseResult(
            phase=phase_num,
            eliminated_arm_id=worst_id,
            eliminated_score=remaining[worst_id],
        ))
        del remaining[worst_id]
        phase_num += 1

    # Le winner est le top-1 parmi les bras restants
    winner_id = max(remaining, key=lambda aid: (remaining[aid], -aid))
    return SRResult(
        winner_arm_id=winner_id,
        winner_score=remaining[winner_id],
        phases=phases,
        final_scores=final_scores,
    )
