"""État du prompt à base de règles et opérations de patch pour MILPO.

Un prompt est représenté comme : skeleton (fixe) + liste ordonnée de DSLRules.
Les PatchOps manipulent cette liste de règles de façon atomique.
Le state_hash permet la détection de cycles via la liste tabou.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum

from milpo.dsl import DSLRule, compile_rule, validate_rule


class OpType(str, Enum):
    """Types d'opérations de patch."""

    ADD_RULE = "add_rule"
    REMOVE_RULE = "remove_rule"
    REPLACE_RULE = "replace_rule"
    REORDER_RULE = "reorder_rule"


OPTIMIZABLE_SLOTS: list[tuple[str, str | None]] = [
    ("visual_format", "FEED"),
    ("visual_format", "REELS"),
    ("category", None),
    ("strategy", None),
]


@dataclass
class RuleState:
    """État complet d'un slot de prompt : skeleton + règles ordonnées."""

    agent: str
    scope: str | None
    skeleton: str
    rules: list[DSLRule]
    signal_vocab: set[str] = field(default_factory=set)
    label_vocab: set[str] = field(default_factory=set)

    def render(self) -> str:
        """Rend le prompt complet : skeleton + règles numérotées compilées."""
        if not self.rules:
            return self.skeleton
        lines = [compile_rule(rule) for rule in self.rules]
        rules_block = "\n".join(f"{i + 1}. {line}" for i, line in enumerate(lines))
        return f"{self.skeleton}\n\n{rules_block}"

    def state_hash(self) -> str:
        """Hash déterministe de l'état des règles pour la détection de cycles.

        Deux RuleStates avec les mêmes règles dans le même ordre produisent
        le même hash, indépendamment du chemin pour y arriver.
        """
        canonical = json.dumps(
            [(i, rule.canonical()) for i, rule in enumerate(self.rules)],
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha256(canonical.encode()).hexdigest()[:16]

    def rule_count(self) -> int:
        return len(self.rules)

    def slot_key(self) -> str:
        """Clé unique pour le slot (pour le tabu)."""
        return f"{self.agent}/{self.scope or 'all'}"


@dataclass(frozen=True)
class PatchOp:
    """Une opération de patch typée sur la liste de règles."""

    op_type: OpType
    index: int | None = None
    new_rule: DSLRule | None = None
    new_position: int | None = None

    def to_dict(self) -> dict:
        d: dict = {"op_type": self.op_type.value}
        if self.index is not None:
            d["index"] = self.index
        if self.new_rule is not None:
            d["new_rule"] = self.new_rule.to_dict()
        if self.new_position is not None:
            d["new_position"] = self.new_position
        return d


def apply_patch(state: RuleState, op: PatchOp) -> RuleState:
    """Applique un patch à un RuleState, retourne un nouveau RuleState.

    Valide les préconditions et lève ValueError si l'opération est invalide.
    La new_rule est validée contre les vocabulaires du state.
    """
    rules = list(state.rules)

    if op.op_type == OpType.ADD_RULE:
        if op.new_rule is None:
            raise ValueError("add_rule: new_rule requis")
        errors = validate_rule(op.new_rule, state.signal_vocab, state.label_vocab)
        if errors:
            raise ValueError(f"add_rule: règle invalide — {'; '.join(errors)}")
        rules.append(op.new_rule)

    elif op.op_type == OpType.REMOVE_RULE:
        if op.index is None:
            raise ValueError("remove_rule: index requis")
        if not rules:
            raise ValueError("remove_rule: liste de règles vide")
        if len(rules) == 1:
            raise ValueError("remove_rule: impossible de supprimer la dernière règle")
        if op.index < 0 or op.index >= len(rules):
            raise ValueError(
                f"remove_rule: index {op.index} hors bornes [0, {len(rules) - 1}]"
            )
        rules.pop(op.index)

    elif op.op_type == OpType.REPLACE_RULE:
        if op.index is None:
            raise ValueError("replace_rule: index requis")
        if op.new_rule is None:
            raise ValueError("replace_rule: new_rule requis")
        if op.index < 0 or op.index >= len(rules):
            raise ValueError(
                f"replace_rule: index {op.index} hors bornes [0, {len(rules) - 1}]"
            )
        errors = validate_rule(op.new_rule, state.signal_vocab, state.label_vocab)
        if errors:
            raise ValueError(f"replace_rule: règle invalide — {'; '.join(errors)}")
        rules[op.index] = op.new_rule

    elif op.op_type == OpType.REORDER_RULE:
        if op.index is None or op.new_position is None:
            raise ValueError("reorder_rule: index et new_position requis")
        if op.index < 0 or op.index >= len(rules):
            raise ValueError(
                f"reorder_rule: index {op.index} hors bornes [0, {len(rules) - 1}]"
            )
        if op.new_position < 0 or op.new_position >= len(rules):
            raise ValueError(
                f"reorder_rule: new_position {op.new_position} hors bornes "
                f"[0, {len(rules) - 1}]"
            )
        if op.index == op.new_position:
            raise ValueError("reorder_rule: index == new_position (no-op)")
        rule = rules.pop(op.index)
        rules.insert(op.new_position, rule)

    else:
        raise ValueError(f"op_type inconnu: {op.op_type}")

    return RuleState(
        agent=state.agent,
        scope=state.scope,
        skeleton=state.skeleton,
        rules=rules,
        signal_vocab=state.signal_vocab,
        label_vocab=state.label_vocab,
    )
