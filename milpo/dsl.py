"""DSL formelle pour les règles de classification MILPO.

Grammaire BNF :

    rule        := signal_rule | disambig_rule | priority_rule
                 | fallback_rule | caption_rule
    signal_rule := SIGNAL ("+" SIGNAL)* "->" LABEL
    disambig_rule := "distinguish" LABEL LABEL "by" CRITERION
    priority_rule := "check" SIGNAL "before" SIGNAL
    fallback_rule := LABEL "last_resort"
    caption_rule := "caption" CAPTION_MODE

    SIGNAL      ∈ signal_vocabulary[scope]    # fini, ~25 par scope
    LABEL       ∈ taxonomy_labels[scope]      # fini, 42 pour FEED
    CRITERION   := free text, ≤80 chars       # seul élément non-fini
    CAPTION_MODE ∈ {"tiebreaker", "confirmer", "ignorer", "secondaire"}

Les paramètres signals et labels sont des enums finis tirés de la
taxonomie. Seul le champ `criterion` des règles disambiguation est
du texte libre (borné à 80 caractères). L'espace de recherche est
quasi-fini et dramatiquement plus contraint que la réécriture libre.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum


class RuleType(str, Enum):
    """Les 5 types de règles de la DSL."""

    SIGNAL_TO_LABEL = "signal_to_label"
    DISAMBIGUATION = "disambiguation"
    PRIORITY = "priority"
    FALLBACK = "fallback"
    CAPTION_POLICY = "caption_policy"


CAPTION_MODES = frozenset({"tiebreaker", "confirmer", "ignorer", "secondaire"})

MAX_CRITERION_LENGTH = 80


@dataclass(frozen=True)
class DSLRule:
    """Une règle typée de la DSL. Immuable.

    Selon ``rule_type``, certains champs sont requis et d'autres ignorés :

    - SIGNAL_TO_LABEL : ``signals`` (tuple[str, ...]) + ``label`` (str)
    - DISAMBIGUATION  : ``label_a`` + ``label_b`` + ``criterion`` (str ≤80 chars)
    - PRIORITY        : ``high_signal`` + ``low_signal``
    - FALLBACK        : ``label``
    - CAPTION_POLICY  : ``caption_mode`` ∈ CAPTION_MODES
    """

    rule_type: RuleType

    # signal_to_label
    signals: tuple[str, ...] | None = None
    label: str | None = None

    # disambiguation
    label_a: str | None = None
    label_b: str | None = None
    criterion: str | None = None

    # priority
    high_signal: str | None = None
    low_signal: str | None = None

    # caption_policy
    caption_mode: str | None = None

    def canonical(self) -> str:
        """Forme canonique pour le hashing. Déterministe."""
        parts = [self.rule_type.value]
        if self.rule_type == RuleType.SIGNAL_TO_LABEL:
            parts.append("+".join(sorted(self.signals or ())))
            parts.append(self.label or "")
        elif self.rule_type == RuleType.DISAMBIGUATION:
            pair = sorted([self.label_a or "", self.label_b or ""])
            parts.extend(pair)
            parts.append(self.criterion or "")
        elif self.rule_type == RuleType.PRIORITY:
            parts.append(self.high_signal or "")
            parts.append(self.low_signal or "")
        elif self.rule_type == RuleType.FALLBACK:
            parts.append(self.label or "")
        elif self.rule_type == RuleType.CAPTION_POLICY:
            parts.append(self.caption_mode or "")
        return "|".join(parts)

    def to_dict(self) -> dict:
        """Sérialisation JSON-safe pour stockage en BDD (rule_data JSONB)."""
        d: dict = {"rule_type": self.rule_type.value}
        if self.signals is not None:
            d["signals"] = list(self.signals)
        if self.label is not None:
            d["label"] = self.label
        if self.label_a is not None:
            d["label_a"] = self.label_a
        if self.label_b is not None:
            d["label_b"] = self.label_b
        if self.criterion is not None:
            d["criterion"] = self.criterion
        if self.high_signal is not None:
            d["high_signal"] = self.high_signal
        if self.low_signal is not None:
            d["low_signal"] = self.low_signal
        if self.caption_mode is not None:
            d["caption_mode"] = self.caption_mode
        return d

    @classmethod
    def from_dict(cls, d: dict) -> DSLRule:
        """Désérialisation depuis un dict JSON (rule_data JSONB)."""
        signals = tuple(d["signals"]) if "signals" in d else None
        return cls(
            rule_type=RuleType(d["rule_type"]),
            signals=signals,
            label=d.get("label"),
            label_a=d.get("label_a"),
            label_b=d.get("label_b"),
            criterion=d.get("criterion"),
            high_signal=d.get("high_signal"),
            low_signal=d.get("low_signal"),
            caption_mode=d.get("caption_mode"),
        )


# ── Validation ─────────────────────────────────────────────────────────────


def validate_rule(
    rule: DSLRule,
    signal_vocab: set[str],
    label_vocab: set[str],
) -> list[str]:
    """Valide une règle contre les vocabulaires. Retourne une liste d'erreurs (vide = valide)."""
    errors: list[str] = []

    if rule.rule_type == RuleType.SIGNAL_TO_LABEL:
        if not rule.signals:
            errors.append("signal_to_label: signals requis (non vide)")
        else:
            for sig in rule.signals:
                if sig not in signal_vocab:
                    errors.append(f"signal_to_label: signal inconnu '{sig}'")
        if not rule.label:
            errors.append("signal_to_label: label requis")
        elif rule.label not in label_vocab:
            errors.append(f"signal_to_label: label inconnu '{rule.label}'")

    elif rule.rule_type == RuleType.DISAMBIGUATION:
        if not rule.label_a:
            errors.append("disambiguation: label_a requis")
        elif rule.label_a not in label_vocab:
            errors.append(f"disambiguation: label_a inconnu '{rule.label_a}'")
        if not rule.label_b:
            errors.append("disambiguation: label_b requis")
        elif rule.label_b not in label_vocab:
            errors.append(f"disambiguation: label_b inconnu '{rule.label_b}'")
        if rule.label_a and rule.label_b and rule.label_a == rule.label_b:
            errors.append("disambiguation: label_a et label_b identiques")
        if not rule.criterion:
            errors.append("disambiguation: criterion requis")
        elif len(rule.criterion) > MAX_CRITERION_LENGTH:
            errors.append(
                f"disambiguation: criterion trop long "
                f"({len(rule.criterion)} > {MAX_CRITERION_LENGTH})"
            )

    elif rule.rule_type == RuleType.PRIORITY:
        if not rule.high_signal:
            errors.append("priority: high_signal requis")
        elif rule.high_signal not in signal_vocab:
            errors.append(f"priority: high_signal inconnu '{rule.high_signal}'")
        if not rule.low_signal:
            errors.append("priority: low_signal requis")
        elif rule.low_signal not in signal_vocab:
            errors.append(f"priority: low_signal inconnu '{rule.low_signal}'")
        if (
            rule.high_signal
            and rule.low_signal
            and rule.high_signal == rule.low_signal
        ):
            errors.append("priority: high_signal et low_signal identiques")

    elif rule.rule_type == RuleType.FALLBACK:
        if not rule.label:
            errors.append("fallback: label requis")
        elif rule.label not in label_vocab:
            errors.append(f"fallback: label inconnu '{rule.label}'")

    elif rule.rule_type == RuleType.CAPTION_POLICY:
        if not rule.caption_mode:
            errors.append("caption_policy: caption_mode requis")
        elif rule.caption_mode not in CAPTION_MODES:
            errors.append(
                f"caption_policy: caption_mode inconnu '{rule.caption_mode}' "
                f"(valides: {sorted(CAPTION_MODES)})"
            )

    else:
        errors.append(f"rule_type inconnu: {rule.rule_type}")

    return errors


# ── Compilation (DSLRule → texte prompt) ───────────────────────────────────


def _signal_display(signal: str) -> str:
    """Transforme un identifiant snake_case en texte lisible."""
    return signal.replace("_", " ")


def compile_rule(rule: DSLRule) -> str:
    """Compile une règle typée en instruction textuelle pour le prompt.

    Déterministe : même règle → même texte, toujours.
    """
    if rule.rule_type == RuleType.SIGNAL_TO_LABEL:
        signals_text = " + ".join(_signal_display(s) for s in (rule.signals or ()))
        return f"Si {signals_text} → `{rule.label}`"

    if rule.rule_type == RuleType.DISAMBIGUATION:
        return (
            f"Pour départager `{rule.label_a}` / `{rule.label_b}` : "
            f"{rule.criterion}"
        )

    if rule.rule_type == RuleType.PRIORITY:
        return (
            f"Vérifier {_signal_display(rule.high_signal or '')} "
            f"AVANT {_signal_display(rule.low_signal or '')}"
        )

    if rule.rule_type == RuleType.FALLBACK:
        return f"N'utilise `{rule.label}` qu'en dernier recours"

    if rule.rule_type == RuleType.CAPTION_POLICY:
        mode_descriptions = {
            "tiebreaker": "la caption ne sert qu'à départager en cas de doute",
            "confirmer": "la caption confirme mais ne détermine pas",
            "ignorer": "ignorer la caption, se baser uniquement sur le visuel",
            "secondaire": "la caption est un indice secondaire",
        }
        desc = mode_descriptions.get(rule.caption_mode or "", rule.caption_mode or "")
        return f"Caption : {desc}"

    raise ValueError(f"rule_type inconnu: {rule.rule_type}")


# ── Parsing (texte → DSLRule) — pour le bootstrap ─────────────────────────


_ARROW_RE = re.compile(r"^Si\s+(.+?)\s*→\s*`([^`]+)`$")
_DISAMBIG_RE = re.compile(
    r"^Pour départager\s+`([^`]+)`\s*/\s*`([^`]+)`\s*:\s*(.+)$"
)
_PRIORITY_RE = re.compile(
    r"^Vérifier\s+(.+?)\s+AVANT\s+(.+)$"
)
_FALLBACK_RE = re.compile(
    r"^N'utilise\s+`([^`]+)`\s+qu'en dernier recours$"
)
_CAPTION_RE = re.compile(r"^Caption\s*:\s*(.+)$")


def _normalize_signal(text: str) -> str:
    """Normalise un texte de signal en identifiant snake_case."""
    return text.strip().lower().replace(" ", "_").replace("-", "_")


def parse_rule_from_text(
    text: str,
    signal_vocab: set[str],
    label_vocab: set[str],
) -> DSLRule | None:
    """Tente de parser une ligne de texte compilé en DSLRule.

    Retourne None si le texte ne correspond à aucun pattern connu.
    Utilisé principalement pour le round-trip testing du compilateur.
    """
    text = text.strip()
    if text.startswith("- "):
        text = text[2:].strip()

    # signal_to_label
    m = _ARROW_RE.match(text)
    if m:
        signals_text, label = m.group(1), m.group(2)
        signals = tuple(
            _normalize_signal(s) for s in signals_text.split("+")
        )
        if label in label_vocab and all(s in signal_vocab for s in signals):
            return DSLRule(
                rule_type=RuleType.SIGNAL_TO_LABEL,
                signals=signals,
                label=label,
            )
        return None

    # disambiguation
    m = _DISAMBIG_RE.match(text)
    if m:
        label_a, label_b, criterion = m.group(1), m.group(2), m.group(3)
        if label_a in label_vocab and label_b in label_vocab:
            return DSLRule(
                rule_type=RuleType.DISAMBIGUATION,
                label_a=label_a,
                label_b=label_b,
                criterion=criterion.strip(),
            )
        return None

    # priority
    m = _PRIORITY_RE.match(text)
    if m:
        high_text, low_text = m.group(1), m.group(2)
        high = _normalize_signal(high_text)
        low = _normalize_signal(low_text)
        if high in signal_vocab and low in signal_vocab:
            return DSLRule(
                rule_type=RuleType.PRIORITY,
                high_signal=high,
                low_signal=low,
            )
        return None

    # fallback
    m = _FALLBACK_RE.match(text)
    if m:
        label = m.group(1)
        if label in label_vocab:
            return DSLRule(rule_type=RuleType.FALLBACK, label=label)
        return None

    # caption_policy
    m = _CAPTION_RE.match(text)
    if m:
        desc = m.group(1).strip()
        mode_by_desc = {
            "la caption ne sert qu'à départager en cas de doute": "tiebreaker",
            "la caption confirme mais ne détermine pas": "confirmer",
            "ignorer la caption, se baser uniquement sur le visuel": "ignorer",
            "la caption est un indice secondaire": "secondaire",
        }
        mode = mode_by_desc.get(desc)
        if mode:
            return DSLRule(rule_type=RuleType.CAPTION_POLICY, caption_mode=mode)
        return None

    return None
