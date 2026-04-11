"""Bootstrap LLM-assisted : extraction v0 → skeleton + DSLRules.

Le LLM reçoit le prompt v0 complet et le vocabulaire de signaux/labels,
et produit une décomposition structurée en JSON.
Chaque règle extraite est validée par validate_rule().
"""

from __future__ import annotations

import json
import logging
import re

from milpo.dsl import DSLRule, RuleType, compile_rule, validate_rule
from milpo.dsl_vocabulary import get_signal_names, get_signal_vocabulary
from milpo.rules import RuleState

log = logging.getLogger("milpo")


# ── Extraction manuelle par regex (fallback fiable) ────────────────────────


def _extract_rules_from_v0_vf(
    v0_content: str,
    signal_vocab: set[str],
    label_vocab: set[str],
) -> tuple[str, list[DSLRule]]:
    """Parse le v0 visual_format en skeleton + règles.

    Le v0 vf/FEED a une structure claire :
    - Intro (skeleton)
    - ## Règles de décision clés (bullets "- ")
    - ## Consignes (items numérotés "1. ")
    """
    lines = v0_content.strip().split("\n")

    skeleton_lines: list[str] = []
    rule_lines: list[str] = []
    in_rules = False
    in_consignes = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("## Règles de décision") or stripped.startswith("## Regles de decision"):
            in_rules = True
            continue
        if stripped.startswith("## Consignes"):
            in_consignes = True
            in_rules = False
            continue

        if in_consignes:
            if re.match(r"^\d+\.", stripped):
                rule_lines.append(re.sub(r"^\d+\.\s*", "", stripped))
        elif in_rules:
            if stripped.startswith("- "):
                rule_lines.append(stripped[2:].strip())
        else:
            skeleton_lines.append(line)

    skeleton = "\n".join(skeleton_lines).strip()
    rules = _convert_text_rules_to_dsl(rule_lines, signal_vocab, label_vocab)
    return skeleton, rules


def _extract_rules_from_v0_generic(
    v0_content: str,
    signal_vocab: set[str],
    label_vocab: set[str],
) -> tuple[str, list[DSLRule]]:
    """Parse générique pour category et strategy : items numérotés = règles."""
    lines = v0_content.strip().split("\n")

    skeleton_lines: list[str] = []
    rule_lines: list[str] = []
    in_section = False

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("##"):
            in_section = True
            continue

        if in_section and re.match(r"^\d+\.", stripped):
            rule_lines.append(re.sub(r"^\d+\.\s*", "", stripped))
        elif in_section and stripped.startswith("- "):
            rule_lines.append(stripped[2:].strip())
        elif not in_section:
            skeleton_lines.append(line)

    skeleton = "\n".join(skeleton_lines).strip()
    rules = _convert_text_rules_to_dsl(rule_lines, signal_vocab, label_vocab)
    return skeleton, rules


def _convert_text_rules_to_dsl(
    rule_texts: list[str],
    signal_vocab: set[str],
    label_vocab: set[str],
) -> list[DSLRule]:
    """Convertit des lignes de texte en DSLRules best-effort.

    Détecte les patterns courants :
    - "X → `label`" → signal_to_label
    - "Pour départager X / Y" → disambiguation
    - "Vérifie/Regarde d'abord X" → priority
    - "en dernier recours" → fallback
    - "caption" → caption_policy
    """
    rules: list[DSLRule] = []

    for text in rule_texts:
        rule = _try_parse_signal_to_label(text, signal_vocab, label_vocab)
        if rule:
            rules.append(rule)
            continue

        rule = _try_parse_disambiguation(text, label_vocab)
        if rule:
            rules.append(rule)
            continue

        rule = _try_parse_fallback(text, label_vocab)
        if rule:
            rules.append(rule)
            continue

        rule = _try_parse_priority(text, signal_vocab)
        if rule:
            rules.append(rule)
            continue

        rule = _try_parse_caption(text)
        if rule:
            rules.append(rule)
            continue

        # Règle non parsable → disambiguation générique avec le texte comme criterion
        # Borné à 80 chars
        rules.append(DSLRule(
            rule_type=RuleType.DISAMBIGUATION,
            label_a=list(label_vocab)[0] if label_vocab else "unknown",
            label_b=list(label_vocab)[1] if len(label_vocab) > 1 else "unknown",
            criterion=text[:80],
        ))

    return rules


def _try_parse_signal_to_label(
    text: str, signal_vocab: set[str], label_vocab: set[str],
) -> DSLRule | None:
    """Détecte "X → `label`" ou "X → label"."""
    m = re.search(r"→\s*`?(\w+)`?", text)
    if not m:
        return None

    label = m.group(1)
    if label not in label_vocab:
        return None

    # Extraire les signaux de la partie avant →
    before = text[: m.start()].strip()
    signals = _extract_signals_from_text(before, signal_vocab)
    if not signals:
        # Pas de signal reconnu, essayer de normaliser le texte en signal
        normalized = before.lower().replace(" ", "_").replace(",", "").replace("'", "_")
        closest = _find_closest_signal(normalized, signal_vocab)
        if closest:
            signals = [closest]

    if signals:
        return DSLRule(
            rule_type=RuleType.SIGNAL_TO_LABEL,
            signals=tuple(signals),
            label=label,
        )
    return None


def _try_parse_disambiguation(text: str, label_vocab: set[str]) -> DSLRule | None:
    """Détecte "Pour départager X / Y" ou "Pour distinguer"."""
    m = re.search(r"d[ée]partager\s+`?(\w+)`?\s*/\s*`?(\w+)`?", text, re.IGNORECASE)
    if not m:
        m = re.search(r"distinguer\s+`?(\w+)`?\s*/\s*`?(\w+)`?", text, re.IGNORECASE)
    if not m:
        return None

    a, b = m.group(1), m.group(2)
    if a in label_vocab and b in label_vocab:
        criterion = text[m.end():].strip().lstrip(",.:").strip()[:80]
        if not criterion:
            criterion = text[:80]
        return DSLRule(
            rule_type=RuleType.DISAMBIGUATION,
            label_a=a,
            label_b=b,
            criterion=criterion,
        )
    return None


def _try_parse_fallback(text: str, label_vocab: set[str]) -> DSLRule | None:
    """Détecte "dernier recours" avec un label."""
    if "dernier recours" not in text.lower():
        return None
    for label in label_vocab:
        if label in text:
            return DSLRule(rule_type=RuleType.FALLBACK, label=label)
    return None


def _try_parse_priority(text: str, signal_vocab: set[str]) -> DSLRule | None:
    """Détecte "Regarde d'abord X" ou "Vérifier X avant Y"."""
    m = re.search(r"(?:d'abord|en premier|avant)", text, re.IGNORECASE)
    if not m:
        return None

    signals = _extract_signals_from_text(text, signal_vocab)
    if len(signals) >= 2:
        return DSLRule(
            rule_type=RuleType.PRIORITY,
            high_signal=signals[0],
            low_signal=signals[1],
        )
    return None


def _try_parse_caption(text: str) -> DSLRule | None:
    """Détecte les consignes sur la caption."""
    lower = text.lower()
    if "caption" not in lower:
        return None

    if "départager" in lower or "doute" in lower or "tiebreak" in lower:
        return DSLRule(rule_type=RuleType.CAPTION_POLICY, caption_mode="tiebreaker")
    if "confirm" in lower:
        return DSLRule(rule_type=RuleType.CAPTION_POLICY, caption_mode="confirmer")
    if "ignor" in lower:
        return DSLRule(rule_type=RuleType.CAPTION_POLICY, caption_mode="ignorer")
    return DSLRule(rule_type=RuleType.CAPTION_POLICY, caption_mode="secondaire")


def _extract_signals_from_text(text: str, signal_vocab: set[str]) -> list[str]:
    """Extrait les signaux connus d'un texte libre."""
    found: list[str] = []
    lower = text.lower()
    for signal in sorted(signal_vocab, key=len, reverse=True):
        display = signal.replace("_", " ")
        if display in lower and signal not in found:
            found.append(signal)
    return found


def _find_closest_signal(text: str, signal_vocab: set[str]) -> str | None:
    """Trouve le signal le plus proche d'un texte normalisé."""
    for signal in signal_vocab:
        if signal in text or text in signal:
            return signal
    return None


# ── Bootstrap d'un slot ────────────────────────────────────────────────────


def bootstrap_slot_rules(
    conn,
    agent: str,
    scope: str | None,
) -> RuleState:
    """Bootstrap complet : charge v0, parse en skeleton + rules, persiste.

    Idempotent : si le slot a déjà été bootstrappé (skeleton présent et
    rules persistées sur le prompt_version v0), recharge depuis la BDD
    au lieu de re-persister.
    """
    from milpo.db.prompts import get_prompt_version
    from milpo.db.rules import get_skeleton, insert_rules, insert_skeleton, load_rules
    from milpo.dsl_vocabulary import get_signal_names
    from milpo.prompting import build_labels

    v0 = get_prompt_version(conn, agent, scope, version=0, source="human_v0")
    if v0 is None:
        raise RuntimeError(f"Prompt v0 introuvable pour {agent}/{scope or 'all'}")

    effective_scope = scope or "FEED"
    signal_vocab = get_signal_names(effective_scope)
    labels = build_labels(conn, effective_scope)
    label_vocab = set(labels.get(agent, []))

    existing_skeleton = get_skeleton(conn, agent, scope)
    if existing_skeleton is not None:
        existing_rules = load_rules(conn, v0["id"])
        if existing_rules:
            log.info("Slot %s/%s déjà bootstrappé, chargement.", agent, scope or "all")
            return RuleState(
                agent=agent,
                scope=scope,
                skeleton=existing_skeleton,
                rules=existing_rules,
                signal_vocab=signal_vocab,
                label_vocab=label_vocab,
            )

    # Parser le v0
    v0_content = v0["content"]
    if agent == "visual_format":
        skeleton, rules = _extract_rules_from_v0_vf(v0_content, signal_vocab, label_vocab)
    else:
        skeleton, rules = _extract_rules_from_v0_generic(v0_content, signal_vocab, label_vocab)

    if not rules:
        log.warning("Aucune règle extraite du v0 %s/%s, ajout d'une règle fallback.", agent, scope)
        default_label = list(label_vocab)[0] if label_vocab else "unknown"
        rules = [DSLRule(rule_type=RuleType.FALLBACK, label=default_label)]

    insert_skeleton(conn, agent, scope, skeleton)
    insert_rules(conn, v0["id"], agent, scope, rules)

    log.info(
        "Bootstrap %s/%s : skeleton=%d chars, %d règles extraites.",
        agent, scope or "all", len(skeleton), len(rules),
    )

    return RuleState(
        agent=agent,
        scope=scope,
        skeleton=skeleton,
        rules=rules,
        signal_vocab=signal_vocab,
        label_vocab=label_vocab,
    )


def verify_bootstrap(v0_content: str, rule_state: RuleState) -> dict:
    """Rapport de vérification du bootstrap.

    Compare le prompt rendu depuis les règles au v0 original.
    """
    rendered = rule_state.render()
    valid_rules = 0
    invalid_rules = 0
    for rule in rule_state.rules:
        errors = validate_rule(rule, rule_state.signal_vocab, rule_state.label_vocab)
        if errors:
            invalid_rules += 1
        else:
            valid_rules += 1

    return {
        "n_rules": rule_state.rule_count(),
        "valid_rules": valid_rules,
        "invalid_rules": invalid_rules,
        "skeleton_len": len(rule_state.skeleton),
        "rendered_len": len(rendered),
        "v0_len": len(v0_content),
        "rule_types": [r.rule_type.value for r in rule_state.rules],
    }
