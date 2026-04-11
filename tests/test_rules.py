"""Tests pour milpo/rules.py — RuleState, PatchOp, apply_patch."""

from __future__ import annotations

import pytest

from milpo.dsl import DSLRule, RuleType
from milpo.rules import OpType, PatchOp, RuleState, apply_patch

# ── Helpers ────────────────────────────────────────────────────────────────

SIGNALS = {"texte_actualite", "logo_views", "logo_specifique", "chiffre_dominant", "fond_couleur"}
LABELS = {"post_news", "post_mood", "post_chiffre", "post_quote", "post_article"}


def _make_state(*rules: DSLRule) -> RuleState:
    return RuleState(
        agent="visual_format",
        scope="FEED",
        skeleton="Tu es un classificateur.",
        rules=list(rules),
        signal_vocab=SIGNALS,
        label_vocab=LABELS,
    )


R_NEWS = DSLRule(
    rule_type=RuleType.SIGNAL_TO_LABEL,
    signals=("texte_actualite", "logo_views"),
    label="post_news",
)
R_CHIFFRE = DSLRule(
    rule_type=RuleType.SIGNAL_TO_LABEL,
    signals=("chiffre_dominant",),
    label="post_chiffre",
)
R_MOOD = DSLRule(rule_type=RuleType.FALLBACK, label="post_mood")


# ── RuleState ──────────────────────────────────────────────────────────────


class TestRuleState:
    def test_render_empty_rules(self):
        state = _make_state()
        assert state.render() == "Tu es un classificateur."

    def test_render_with_rules(self):
        state = _make_state(R_NEWS, R_CHIFFRE)
        rendered = state.render()
        assert "Tu es un classificateur." in rendered
        assert "1." in rendered
        assert "2." in rendered
        assert "`post_news`" in rendered
        assert "`post_chiffre`" in rendered

    def test_state_hash_deterministic(self):
        s1 = _make_state(R_NEWS, R_CHIFFRE)
        s2 = _make_state(R_NEWS, R_CHIFFRE)
        assert s1.state_hash() == s2.state_hash()

    def test_state_hash_differs_on_different_rules(self):
        s1 = _make_state(R_NEWS)
        s2 = _make_state(R_CHIFFRE)
        assert s1.state_hash() != s2.state_hash()

    def test_state_hash_differs_on_order(self):
        s1 = _make_state(R_NEWS, R_CHIFFRE)
        s2 = _make_state(R_CHIFFRE, R_NEWS)
        assert s1.state_hash() != s2.state_hash()

    def test_rule_count(self):
        assert _make_state().rule_count() == 0
        assert _make_state(R_NEWS).rule_count() == 1
        assert _make_state(R_NEWS, R_CHIFFRE).rule_count() == 2

    def test_slot_key(self):
        state = _make_state()
        assert state.slot_key() == "visual_format/FEED"


# ── apply_patch : add_rule ─────────────────────────────────────────────────


class TestApplyPatchAdd:
    def test_add_rule(self):
        state = _make_state(R_NEWS)
        op = PatchOp(op_type=OpType.ADD_RULE, new_rule=R_CHIFFRE)
        new_state = apply_patch(state, op)
        assert new_state.rule_count() == 2
        assert new_state.rules[1] == R_CHIFFRE

    def test_add_rule_no_new_rule_raises(self):
        state = _make_state(R_NEWS)
        op = PatchOp(op_type=OpType.ADD_RULE)
        with pytest.raises(ValueError, match="new_rule requis"):
            apply_patch(state, op)

    def test_add_rule_invalid_rule_raises(self):
        state = _make_state(R_NEWS)
        bad_rule = DSLRule(
            rule_type=RuleType.SIGNAL_TO_LABEL,
            signals=("signal_inexistant",),
            label="post_news",
        )
        op = PatchOp(op_type=OpType.ADD_RULE, new_rule=bad_rule)
        with pytest.raises(ValueError, match="règle invalide"):
            apply_patch(state, op)

    def test_add_does_not_mutate_original(self):
        state = _make_state(R_NEWS)
        op = PatchOp(op_type=OpType.ADD_RULE, new_rule=R_CHIFFRE)
        apply_patch(state, op)
        assert state.rule_count() == 1


# ── apply_patch : remove_rule ──────────────────────────────────────────────


class TestApplyPatchRemove:
    def test_remove_rule(self):
        state = _make_state(R_NEWS, R_CHIFFRE)
        op = PatchOp(op_type=OpType.REMOVE_RULE, index=0)
        new_state = apply_patch(state, op)
        assert new_state.rule_count() == 1
        assert new_state.rules[0] == R_CHIFFRE

    def test_remove_last_rule_raises(self):
        state = _make_state(R_NEWS)
        op = PatchOp(op_type=OpType.REMOVE_RULE, index=0)
        with pytest.raises(ValueError, match="dernière règle"):
            apply_patch(state, op)

    def test_remove_from_empty_raises(self):
        state = _make_state()
        op = PatchOp(op_type=OpType.REMOVE_RULE, index=0)
        with pytest.raises(ValueError, match="vide"):
            apply_patch(state, op)

    def test_remove_out_of_bounds_raises(self):
        state = _make_state(R_NEWS, R_CHIFFRE)
        op = PatchOp(op_type=OpType.REMOVE_RULE, index=5)
        with pytest.raises(ValueError, match="hors bornes"):
            apply_patch(state, op)

    def test_remove_no_index_raises(self):
        state = _make_state(R_NEWS, R_CHIFFRE)
        op = PatchOp(op_type=OpType.REMOVE_RULE)
        with pytest.raises(ValueError, match="index requis"):
            apply_patch(state, op)


# ── apply_patch : replace_rule ─────────────────────────────────────────────


class TestApplyPatchReplace:
    def test_replace_rule(self):
        state = _make_state(R_NEWS, R_MOOD)
        op = PatchOp(op_type=OpType.REPLACE_RULE, index=0, new_rule=R_CHIFFRE)
        new_state = apply_patch(state, op)
        assert new_state.rules[0] == R_CHIFFRE
        assert new_state.rules[1] == R_MOOD

    def test_replace_out_of_bounds_raises(self):
        state = _make_state(R_NEWS)
        op = PatchOp(op_type=OpType.REPLACE_RULE, index=5, new_rule=R_CHIFFRE)
        with pytest.raises(ValueError, match="hors bornes"):
            apply_patch(state, op)

    def test_replace_invalid_rule_raises(self):
        state = _make_state(R_NEWS)
        bad = DSLRule(rule_type=RuleType.FALLBACK, label="inconnu")
        op = PatchOp(op_type=OpType.REPLACE_RULE, index=0, new_rule=bad)
        with pytest.raises(ValueError, match="règle invalide"):
            apply_patch(state, op)


# ── apply_patch : reorder_rule ─────────────────────────────────────────────


class TestApplyPatchReorder:
    def test_reorder_rule(self):
        state = _make_state(R_NEWS, R_CHIFFRE, R_MOOD)
        op = PatchOp(op_type=OpType.REORDER_RULE, index=0, new_position=2)
        new_state = apply_patch(state, op)
        assert new_state.rules[0] == R_CHIFFRE
        assert new_state.rules[1] == R_MOOD
        assert new_state.rules[2] == R_NEWS

    def test_reorder_same_position_raises(self):
        state = _make_state(R_NEWS, R_CHIFFRE)
        op = PatchOp(op_type=OpType.REORDER_RULE, index=0, new_position=0)
        with pytest.raises(ValueError, match="no-op"):
            apply_patch(state, op)

    def test_reorder_out_of_bounds_raises(self):
        state = _make_state(R_NEWS, R_CHIFFRE)
        op = PatchOp(op_type=OpType.REORDER_RULE, index=0, new_position=10)
        with pytest.raises(ValueError, match="hors bornes"):
            apply_patch(state, op)


# ── PatchOp serialization ─────────────────────────────────────────────────


class TestPatchOpSerialization:
    def test_to_dict(self):
        op = PatchOp(op_type=OpType.ADD_RULE, new_rule=R_NEWS)
        d = op.to_dict()
        assert d["op_type"] == "add_rule"
        assert "new_rule" in d
        assert d["new_rule"]["rule_type"] == "signal_to_label"
