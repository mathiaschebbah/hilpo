"""Tests TDD pour la résistance de SR aux bras de tailles inégales.

Quand des posts timeout dans async_multi_evaluate, certains bras
ont moins de résultats. SR doit quand même fonctionner.
"""

from __future__ import annotations

import unittest

from milpo.bandits import successive_rejects
from milpo.simulation.rewrite import _align_candidate_arms


class AlignCandidateArmsTests(unittest.TestCase):
    """_align_candidate_arms tronque les bras à la taille minimale."""

    def test_equal_arms_unchanged(self) -> None:
        arms = {1: [True, False, True], 2: [False, True, True]}
        aligned = _align_candidate_arms(arms)
        self.assertEqual(aligned, arms)

    def test_unequal_arms_truncated_to_min(self) -> None:
        arms = {1: [True, False, True, True], 2: [False, True]}
        aligned = _align_candidate_arms(arms)
        self.assertEqual(len(aligned[1]), 2)
        self.assertEqual(len(aligned[2]), 2)

    def test_one_empty_arm_removed(self) -> None:
        arms = {1: [True, False], 2: [], 3: [False, True]}
        aligned = _align_candidate_arms(arms)
        self.assertNotIn(2, aligned)
        self.assertEqual(len(aligned[1]), 2)
        self.assertEqual(len(aligned[3]), 2)

    def test_all_empty_returns_empty(self) -> None:
        arms = {1: [], 2: []}
        aligned = _align_candidate_arms(arms)
        self.assertEqual(aligned, {})

    def test_single_arm_kept(self) -> None:
        arms = {1: [True, False, True]}
        aligned = _align_candidate_arms(arms)
        self.assertEqual(aligned, {1: [True, False, True]})

    def test_aligned_arms_pass_sr(self) -> None:
        """After alignment, SR should not crash."""
        arms = {1: [True, False, True, True], 2: [False, True], 3: [True, True, False]}
        aligned = _align_candidate_arms(arms)
        # All remaining arms should have length 2
        result = successive_rejects(aligned, k=1)
        self.assertIsNotNone(result.winner_arm_id)


class SRDirectUnequal(unittest.TestCase):
    """Vérifie que SR crashe bien sans alignement (baseline du test)."""

    def test_sr_crashes_on_unequal(self) -> None:
        arms = {1: [True, False, True], 2: [False, True]}
        with self.assertRaises(ValueError):
            successive_rejects(arms, k=1)


if __name__ == "__main__":
    unittest.main()
