"""Tests pour milpo/dsl.py — DSL formelle de règles."""

from __future__ import annotations

import pytest

from milpo.dsl import (
    CAPTION_MODES,
    DSLRule,
    RuleType,
    compile_rule,
    parse_rule_from_text,
    validate_rule,
)

# ── Fixtures ───────────────────────────────────────────────────────────────

SIGNAL_VOCAB = {
    "texte_overlay_present",
    "texte_overlay_absent",
    "texte_actualite",
    "logo_views",
    "logo_specifique",
    "chiffre_dominant",
    "calque_couleur",
    "fond_couleur",
    "carousel_structure",
    "texte_par_slide",
}

LABEL_VOCAB = {
    "post_mood",
    "post_news",
    "post_quote",
    "post_chiffre",
    "post_selection",
    "post_interview",
    "post_article",
    "post_ourviews",
}


# ── validate_rule ──────────────────────────────────────────────────────────


class TestValidateRule:
    def test_valid_signal_to_label(self):
        rule = DSLRule(
            rule_type=RuleType.SIGNAL_TO_LABEL,
            signals=("texte_actualite", "logo_views"),
            label="post_news",
        )
        assert validate_rule(rule, SIGNAL_VOCAB, LABEL_VOCAB) == []

    def test_invalid_signal(self):
        rule = DSLRule(
            rule_type=RuleType.SIGNAL_TO_LABEL,
            signals=("signal_inexistant",),
            label="post_news",
        )
        errors = validate_rule(rule, SIGNAL_VOCAB, LABEL_VOCAB)
        assert len(errors) == 1
        assert "signal inconnu" in errors[0]

    def test_invalid_label(self):
        rule = DSLRule(
            rule_type=RuleType.SIGNAL_TO_LABEL,
            signals=("texte_actualite",),
            label="format_inexistant",
        )
        errors = validate_rule(rule, SIGNAL_VOCAB, LABEL_VOCAB)
        assert len(errors) == 1
        assert "label inconnu" in errors[0]

    def test_signal_to_label_empty_signals(self):
        rule = DSLRule(
            rule_type=RuleType.SIGNAL_TO_LABEL,
            signals=(),
            label="post_news",
        )
        errors = validate_rule(rule, SIGNAL_VOCAB, LABEL_VOCAB)
        assert any("signals requis" in e for e in errors)

    def test_valid_disambiguation(self):
        rule = DSLRule(
            rule_type=RuleType.DISAMBIGUATION,
            label_a="post_quote",
            label_b="post_interview",
            criterion="alternance citation + shooting",
        )
        assert validate_rule(rule, SIGNAL_VOCAB, LABEL_VOCAB) == []

    def test_disambiguation_same_labels(self):
        rule = DSLRule(
            rule_type=RuleType.DISAMBIGUATION,
            label_a="post_quote",
            label_b="post_quote",
            criterion="test",
        )
        errors = validate_rule(rule, SIGNAL_VOCAB, LABEL_VOCAB)
        assert any("identiques" in e for e in errors)

    def test_disambiguation_criterion_too_long(self):
        rule = DSLRule(
            rule_type=RuleType.DISAMBIGUATION,
            label_a="post_quote",
            label_b="post_interview",
            criterion="x" * 81,
        )
        errors = validate_rule(rule, SIGNAL_VOCAB, LABEL_VOCAB)
        assert any("trop long" in e for e in errors)

    def test_valid_priority(self):
        rule = DSLRule(
            rule_type=RuleType.PRIORITY,
            high_signal="logo_specifique",
            low_signal="carousel_structure",
        )
        assert validate_rule(rule, SIGNAL_VOCAB, LABEL_VOCAB) == []

    def test_priority_same_signals(self):
        rule = DSLRule(
            rule_type=RuleType.PRIORITY,
            high_signal="logo_views",
            low_signal="logo_views",
        )
        errors = validate_rule(rule, SIGNAL_VOCAB, LABEL_VOCAB)
        assert any("identiques" in e for e in errors)

    def test_valid_fallback(self):
        rule = DSLRule(rule_type=RuleType.FALLBACK, label="post_mood")
        assert validate_rule(rule, SIGNAL_VOCAB, LABEL_VOCAB) == []

    def test_fallback_invalid_label(self):
        rule = DSLRule(rule_type=RuleType.FALLBACK, label="inconnu")
        errors = validate_rule(rule, SIGNAL_VOCAB, LABEL_VOCAB)
        assert any("label inconnu" in e for e in errors)

    def test_valid_caption_policy(self):
        rule = DSLRule(rule_type=RuleType.CAPTION_POLICY, caption_mode="tiebreaker")
        assert validate_rule(rule, SIGNAL_VOCAB, LABEL_VOCAB) == []

    def test_invalid_caption_mode(self):
        rule = DSLRule(rule_type=RuleType.CAPTION_POLICY, caption_mode="invalid_mode")
        errors = validate_rule(rule, SIGNAL_VOCAB, LABEL_VOCAB)
        assert any("caption_mode inconnu" in e for e in errors)


# ── compile_rule ───────────────────────────────────────────────────────────


class TestCompileRule:
    def test_compile_signal_to_label(self):
        rule = DSLRule(
            rule_type=RuleType.SIGNAL_TO_LABEL,
            signals=("texte_actualite", "logo_views"),
            label="post_news",
        )
        text = compile_rule(rule)
        assert "texte actualite" in text
        assert "logo views" in text
        assert "`post_news`" in text
        assert "→" in text

    def test_compile_disambiguation(self):
        rule = DSLRule(
            rule_type=RuleType.DISAMBIGUATION,
            label_a="post_quote",
            label_b="post_interview",
            criterion="alternance citation + shooting",
        )
        text = compile_rule(rule)
        assert "`post_quote`" in text
        assert "`post_interview`" in text
        assert "alternance" in text
        assert "départager" in text

    def test_compile_priority(self):
        rule = DSLRule(
            rule_type=RuleType.PRIORITY,
            high_signal="logo_specifique",
            low_signal="carousel_structure",
        )
        text = compile_rule(rule)
        assert "logo specifique" in text
        assert "carousel structure" in text
        assert "AVANT" in text

    def test_compile_fallback(self):
        rule = DSLRule(rule_type=RuleType.FALLBACK, label="post_mood")
        text = compile_rule(rule)
        assert "`post_mood`" in text
        assert "dernier recours" in text

    def test_compile_caption_policy(self):
        rule = DSLRule(rule_type=RuleType.CAPTION_POLICY, caption_mode="tiebreaker")
        text = compile_rule(rule)
        assert "Caption" in text
        assert "départager" in text

    def test_compile_deterministic(self):
        rule = DSLRule(
            rule_type=RuleType.SIGNAL_TO_LABEL,
            signals=("texte_actualite", "logo_views"),
            label="post_news",
        )
        assert compile_rule(rule) == compile_rule(rule)


# ── parse_rule_from_text (round-trip) ──────────────────────────────────────


class TestParseRule:
    def test_roundtrip_signal_to_label(self):
        original = DSLRule(
            rule_type=RuleType.SIGNAL_TO_LABEL,
            signals=("texte_actualite", "logo_views"),
            label="post_news",
        )
        compiled = compile_rule(original)
        parsed = parse_rule_from_text(compiled, SIGNAL_VOCAB, LABEL_VOCAB)
        assert parsed is not None
        assert parsed.rule_type == RuleType.SIGNAL_TO_LABEL
        assert set(parsed.signals) == set(original.signals)
        assert parsed.label == original.label

    def test_roundtrip_disambiguation(self):
        original = DSLRule(
            rule_type=RuleType.DISAMBIGUATION,
            label_a="post_quote",
            label_b="post_interview",
            criterion="alternance citation + shooting",
        )
        compiled = compile_rule(original)
        parsed = parse_rule_from_text(compiled, SIGNAL_VOCAB, LABEL_VOCAB)
        assert parsed is not None
        assert parsed.rule_type == RuleType.DISAMBIGUATION
        assert parsed.label_a == "post_quote"
        assert parsed.label_b == "post_interview"

    def test_roundtrip_priority(self):
        original = DSLRule(
            rule_type=RuleType.PRIORITY,
            high_signal="logo_specifique",
            low_signal="carousel_structure",
        )
        compiled = compile_rule(original)
        parsed = parse_rule_from_text(compiled, SIGNAL_VOCAB, LABEL_VOCAB)
        assert parsed is not None
        assert parsed.rule_type == RuleType.PRIORITY
        assert parsed.high_signal == "logo_specifique"

    def test_roundtrip_fallback(self):
        original = DSLRule(rule_type=RuleType.FALLBACK, label="post_mood")
        compiled = compile_rule(original)
        parsed = parse_rule_from_text(compiled, SIGNAL_VOCAB, LABEL_VOCAB)
        assert parsed is not None
        assert parsed.rule_type == RuleType.FALLBACK
        assert parsed.label == "post_mood"

    def test_roundtrip_caption(self):
        original = DSLRule(rule_type=RuleType.CAPTION_POLICY, caption_mode="tiebreaker")
        compiled = compile_rule(original)
        parsed = parse_rule_from_text(compiled, SIGNAL_VOCAB, LABEL_VOCAB)
        assert parsed is not None
        assert parsed.rule_type == RuleType.CAPTION_POLICY
        assert parsed.caption_mode == "tiebreaker"

    def test_unparsable_returns_none(self):
        assert parse_rule_from_text("blah blah", SIGNAL_VOCAB, LABEL_VOCAB) is None

    def test_parse_with_bullet_prefix(self):
        original = DSLRule(rule_type=RuleType.FALLBACK, label="post_mood")
        compiled = "- " + compile_rule(original)
        parsed = parse_rule_from_text(compiled, SIGNAL_VOCAB, LABEL_VOCAB)
        assert parsed is not None
        assert parsed.label == "post_mood"


# ── DSLRule serialization ──────────────────────────────────────────────────


class TestDSLRuleSerialization:
    def test_to_dict_from_dict_roundtrip(self):
        rule = DSLRule(
            rule_type=RuleType.SIGNAL_TO_LABEL,
            signals=("texte_actualite", "logo_views"),
            label="post_news",
        )
        d = rule.to_dict()
        restored = DSLRule.from_dict(d)
        assert restored == rule

    def test_canonical_deterministic(self):
        rule = DSLRule(
            rule_type=RuleType.SIGNAL_TO_LABEL,
            signals=("logo_views", "texte_actualite"),
            label="post_news",
        )
        assert rule.canonical() == rule.canonical()

    def test_canonical_signal_order_independent(self):
        r1 = DSLRule(
            rule_type=RuleType.SIGNAL_TO_LABEL,
            signals=("texte_actualite", "logo_views"),
            label="post_news",
        )
        r2 = DSLRule(
            rule_type=RuleType.SIGNAL_TO_LABEL,
            signals=("logo_views", "texte_actualite"),
            label="post_news",
        )
        assert r1.canonical() == r2.canonical()

    def test_canonical_differs_on_different_label(self):
        r1 = DSLRule(
            rule_type=RuleType.SIGNAL_TO_LABEL,
            signals=("texte_actualite",),
            label="post_news",
        )
        r2 = DSLRule(
            rule_type=RuleType.SIGNAL_TO_LABEL,
            signals=("texte_actualite",),
            label="post_mood",
        )
        assert r1.canonical() != r2.canonical()
