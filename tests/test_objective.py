"""Tests pour milpo/objective.py — macro_f1 et compute_j."""

from __future__ import annotations

import pytest

from milpo.objective import (
    WEIGHT_CAT,
    WEIGHT_STRAT,
    WEIGHT_VF,
    accuracy,
    compute_j,
    compute_j_components,
    macro_f1,
)


class TestMacroF1:
    def test_all_correct(self):
        y_true = ["a", "b", "c", "a", "b"]
        y_pred = ["a", "b", "c", "a", "b"]
        assert macro_f1(y_true, y_pred) == pytest.approx(1.0)

    def test_all_wrong(self):
        y_true = ["a", "b", "c"]
        y_pred = ["b", "c", "a"]
        assert macro_f1(y_true, y_pred) == pytest.approx(0.0)

    def test_partial(self):
        # 2 classes: "a" (2 correct) and "b" (0 correct)
        y_true = ["a", "a", "b"]
        y_pred = ["a", "a", "a"]
        # class a: tp=2, fp=1, fn=0 → P=2/3, R=1 → F1=4/5=0.8
        # class b: tp=0, fp=0, fn=1 → P=0, R=0 → F1=0
        # macroF1 = (0.8 + 0) / 2 = 0.4
        assert macro_f1(y_true, y_pred) == pytest.approx(0.4)

    def test_empty_lists(self):
        assert macro_f1([], []) == 0.0

    def test_single_class_all_correct(self):
        y_true = ["a", "a", "a"]
        y_pred = ["a", "a", "a"]
        assert macro_f1(y_true, y_pred) == pytest.approx(1.0)

    def test_mismatched_length(self):
        assert macro_f1(["a", "b"], ["a"]) == 0.0


class TestAccuracy:
    def test_all_correct(self):
        assert accuracy(["a", "b"], ["a", "b"]) == pytest.approx(1.0)

    def test_all_wrong(self):
        assert accuracy(["a", "b"], ["b", "a"]) == pytest.approx(0.0)

    def test_half(self):
        assert accuracy(["a", "b"], ["a", "a"]) == pytest.approx(0.5)

    def test_empty(self):
        assert accuracy([], []) == 0.0


class TestComputeJ:
    def test_all_correct(self):
        t = ["a", "b", "c"]
        j = compute_j(t, t, t, t, t, t)
        assert j == pytest.approx(1.0)

    def test_all_wrong(self):
        true = ["a", "b", "c"]
        pred = ["b", "c", "a"]
        j = compute_j(true, pred, true, pred, true, pred)
        assert j == pytest.approx(0.0)

    def test_weights_sum_to_one(self):
        assert WEIGHT_VF + WEIGHT_CAT + WEIGHT_STRAT == pytest.approx(1.0)

    def test_only_vf_correct(self):
        correct = ["a", "a"]
        wrong = ["b", "c"]
        j = compute_j(correct, correct, wrong, ["c", "a"], wrong, ["c", "a"])
        # macroF1_vf = 1.0, macroF1_cat ≈ 0, acc_strat = 0
        assert j == pytest.approx(WEIGHT_VF * 1.0, abs=0.01)

    def test_only_strat_correct(self):
        wrong = ["a", "b", "c"]
        wrong_pred = ["b", "c", "a"]
        strat_true = ["x", "x"]
        strat_pred = ["x", "x"]
        j = compute_j(wrong, wrong_pred, wrong, wrong_pred, strat_true, strat_pred)
        assert j == pytest.approx(WEIGHT_STRAT * 1.0)

    def test_components_match_j(self):
        vt, vp = ["a", "b", "a"], ["a", "b", "b"]
        ct, cp = ["x", "y"], ["x", "x"]
        st, sp = ["o", "b", "o"], ["o", "o", "o"]
        components = compute_j_components(vt, vp, ct, cp, st, sp)
        j_direct = compute_j(vt, vp, ct, cp, st, sp)
        assert components["J"] == pytest.approx(j_direct)
