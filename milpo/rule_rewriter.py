"""Critic et Editor adaptés à la DSL de règles pour l'optimisation structurée.

Le critic diagnostique les défauts des règles actuelles à la lumière des erreurs.
L'editor propose 3 PatchOps typés pour corriger le défaut identifié.

Réutilise le pattern _call_with_retry de milpo/rewriter.py.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from openai import OpenAI

from milpo.client import get_rewriter_client
from milpo.config import MODEL_CRITIC, MODEL_EDITOR
from milpo.dsl import DSLRule, RuleType, compile_rule
from milpo.dsl_vocabulary import format_signal_vocabulary_for_prompt
from milpo.errors import LLMCallError
from milpo.rewriter import ErrorCase, _call_with_retry, _format_error_batch
from milpo.rules import OpType, PatchOp, RuleState
from milpo.schemas import (
    RuleCritiquePayload,
    RulePatchesPayload,
    build_json_schema_response_format,
)

log = logging.getLogger("milpo")


# ── Prompts système ────────────────────────────────────────────────────────


RULE_CRITIC_SYSTEM = """\
Tu es un évaluateur expert d'instructions de classification multimodale.

Tu reçois :
1. Les règles actuelles d'un classifieur (liste numérotée, chaque règle est typée)
2. Le squelette fixe du prompt (pour contexte — NE PAS modifier)
3. Un batch d'erreurs de classification
4. Les descriptions taxonomiques complètes

## Ta mission

Produis exactement 1 critique décrivant le défaut le plus important des règles
actuelles à la lumière des erreurs observées. La critique doit :

- pointer un défaut concret : règle manquante, règle ambiguë, règle redondante,
  mauvais ordre de priorité, signal sous-pondéré, frontière floue entre deux labels
- indiquer l'index de la règle la plus problématique (0-based), ou null si le
  défaut est l'absence d'une règle
- s'appuyer sur au moins une erreur du batch (citer brièvement le pattern)
- être actionnable par une seule opération (ajout, suppression, remplacement,
  ou réordonnancement)

## Contraintes strictes

- Ne propose AUCUNE réécriture, AUCUNE opération — diagnostic seulement
- Ne touche pas au squelette ni aux descriptions taxonomiques
- 1 critique, 1 défaut, 1 règle cible (ou null pour ajout)

Format : JSON strict {{"critique": "...", "target_rule_index": N|null}}
"""


RULE_EDITOR_SYSTEM = """\
Tu es un ingénieur prompt expert. Tu reçois une liste de règles numérotées,
une critique diagnostic, un batch d'erreurs, et le vocabulaire de signaux/labels.

## Ta mission

Propose exactement {n_patches} opérations typées DIFFÉRENTES pour corriger le défaut
identifié par la critique. Les opérations possibles sont :

- `add_rule` : ajouter une nouvelle règle (fournir `new_rule` avec les champs typés)
- `remove_rule` : supprimer la règle à l'index `index`
- `replace_rule` : remplacer la règle à l'index `index` par `new_rule`
- `reorder_rule` : déplacer la règle à l'index `index` vers `new_position`

## Types de règles (DSL)

Chaque règle a un `rule_type` et des champs associés :
- `signal_to_label` : signals (liste de noms de signaux) + label
- `disambiguation` : label_a + label_b + criterion (≤80 caractères)
- `priority` : high_signal + low_signal
- `fallback` : label
- `caption_policy` : caption_mode ∈ {{tiebreaker, confirmer, ignorer, secondaire}}

## Vocabulaire de signaux (ENUM FINI — utiliser UNIQUEMENT ces noms)

{signal_vocabulary}

## Labels valides (ENUM FINI — utiliser UNIQUEMENT ces noms)

{label_list}

## Contraintes strictes

- Exactement {n_patches} opérations, chacune DIFFÉRENTE
- Les signaux dans new_rule.signals DOIVENT être dans le vocabulaire ci-dessus
- Les labels DOIVENT être dans la liste ci-dessus
- criterion ≤ 80 caractères
{dynamic_constraints}
- `reasoning` : 2-3 phrases expliquant quel défaut est corrigé et comment

Format : JSON strict {{"patches": [{{...}}, ...]}}
"""


# ── Dataclasses résultats ──────────────────────────────────────────────────


@dataclass
class CritiqueResult:
    critique: str
    target_rule_index: int | None
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


@dataclass
class PatchesResult:
    patches: list[tuple[PatchOp, str]]  # (PatchOp, reasoning)
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int


# ── Helpers ────────────────────────────────────────────────────────────────


def _format_rules_for_prompt(rule_state: RuleState) -> str:
    """Formate les règles numérotées pour le prompt LLM."""
    if not rule_state.rules:
        return "(aucune règle)"
    lines = []
    for i, rule in enumerate(rule_state.rules):
        compiled = compile_rule(rule)
        lines.append(f"[{i}] ({rule.rule_type.value}) {compiled}")
    return "\n".join(lines)


def _build_dynamic_constraints(rule_state: RuleState) -> str:
    """Contraintes dynamiques basées sur l'état actuel des règles."""
    constraints = []
    if rule_state.rule_count() == 1:
        constraints.append("- Ne propose PAS remove_rule (1 seule règle restante)")
    if rule_state.rule_count() >= 20:
        constraints.append("- Ne propose PAS add_rule (maximum 20 règles atteint)")
    return "\n".join(constraints) if constraints else ""


def _dsl_rule_from_payload(payload_rule) -> DSLRule:
    """Convertit un DSLRulePayload en DSLRule."""
    signals = tuple(payload_rule.signals) if payload_rule.signals else None
    return DSLRule(
        rule_type=RuleType(payload_rule.rule_type),
        signals=signals,
        label=payload_rule.label,
        label_a=payload_rule.label_a,
        label_b=payload_rule.label_b,
        criterion=payload_rule.criterion,
        high_signal=payload_rule.high_signal,
        low_signal=payload_rule.low_signal,
        caption_mode=payload_rule.caption_mode,
    )


# ── Critic ─────────────────────────────────────────────────────────────────


def rule_critique(
    rule_state: RuleState,
    errors: list[ErrorCase],
    all_descriptions: str,
    model: str = MODEL_CRITIC,
    client: OpenAI | None = None,
) -> CritiqueResult:
    """Étape critique : diagnostique le défaut le plus important des règles."""
    if client is None:
        client = get_rewriter_client()

    target_label = f"{rule_state.agent}/{rule_state.scope or 'all'}"
    rules_text = _format_rules_for_prompt(rule_state)

    user_content = f"""## Cible du diagnostic

{target_label}

## Règles actuelles ({rule_state.rule_count()} règles)

{rules_text}

## Squelette (fixe — pour contexte)

```
{rule_state.skeleton}
```

## Batch d'erreurs ({len(errors)} erreurs)

{_format_error_batch(errors)}

## Descriptions taxonomiques (référence)

{all_descriptions}

---

Diagnostique le défaut le plus important des règles actuelles. 1 critique, 1 index cible."""

    response_format = build_json_schema_response_format(
        "rule_critique_payload",
        RuleCritiquePayload.model_json_schema(),
    )

    content, in_tok, out_tok, latency_ms = _call_with_retry(
        client, model, RULE_CRITIC_SYSTEM, user_content, response_format,
        label=f"RuleCritic[{target_label}]",
        temperature=0.3,
    )
    payload = RuleCritiquePayload.model_validate_json(content)

    return CritiqueResult(
        critique=payload.critique,
        target_rule_index=payload.target_rule_index,
        model=model,
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_ms=latency_ms,
    )


# ── Editor ─────────────────────────────────────────────────────────────────


def rule_edit(
    rule_state: RuleState,
    critique: str,
    target_rule_index: int | None,
    errors: list[ErrorCase],
    all_descriptions: str,
    n_patches: int = 3,
    model: str = MODEL_EDITOR,
    client: OpenAI | None = None,
) -> PatchesResult:
    """Étape édition : propose n_patches PatchOps typés pour corriger le défaut."""
    if client is None:
        client = get_rewriter_client()

    target_label = f"{rule_state.agent}/{rule_state.scope or 'all'}"
    rules_text = _format_rules_for_prompt(rule_state)
    scope = rule_state.scope or "FEED"
    signal_vocab_text = format_signal_vocabulary_for_prompt(scope)
    label_list = ", ".join(sorted(rule_state.label_vocab))
    dynamic_constraints = _build_dynamic_constraints(rule_state)

    system = RULE_EDITOR_SYSTEM.format(
        n_patches=n_patches,
        signal_vocabulary=signal_vocab_text,
        label_list=label_list,
        dynamic_constraints=dynamic_constraints,
    )

    target_info = (
        f"Index ciblé par la critique : {target_rule_index}"
        if target_rule_index is not None
        else "Aucune règle existante ciblée (ajout probable)"
    )

    user_content = f"""## Cible du rewrite

{target_label}

## Règles actuelles ({rule_state.rule_count()} règles)

{rules_text}

## Critique (diagnostic)

{critique}

{target_info}

## Batch d'erreurs ({len(errors)} erreurs)

{_format_error_batch(errors)}

## Descriptions taxonomiques (fixes)

{all_descriptions}

---

Propose exactement {n_patches} opérations typées DIFFÉRENTES pour corriger ce défaut."""

    response_format = build_json_schema_response_format(
        "rule_patches_payload",
        RulePatchesPayload.model_json_schema(),
    )

    content, in_tok, out_tok, latency_ms = _call_with_retry(
        client, model, system, user_content, response_format,
        label=f"RuleEditor[{target_label}]",
        temperature=0.7,
    )
    payload = RulePatchesPayload.model_validate_json(content)

    patches: list[tuple[PatchOp, str]] = []
    for p in payload.patches:
        new_rule = _dsl_rule_from_payload(p.new_rule) if p.new_rule else None
        patch_op = PatchOp(
            op_type=OpType(p.op_type),
            index=p.index,
            new_rule=new_rule,
            new_position=p.new_position,
        )
        patches.append((patch_op, p.reasoning))

    return PatchesResult(
        patches=patches,
        model=model,
        input_tokens=in_tok,
        output_tokens=out_tok,
        latency_ms=latency_ms,
    )
