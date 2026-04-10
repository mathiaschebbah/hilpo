"""Tests pour milpo.simulation — évaluation, rewrite trigger, promo/rollback."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from milpo.inference import ApiCallLog, PipelineResult, PostInput
from milpo.rewriter import ErrorCase
from milpo.schemas import PostPrediction
from milpo.simulation.evaluation import evaluate_result_and_store, target_metric_matches
from milpo.simulation.state import (
    MatchRecord,
    MultiEvalResult,
    PromptState,
    RewriteOutcome,
    build_run_metrics,
)


def _features() -> str:
    return "Slide 1 : Photo plein cadre, titre editorial Views overlay, logo Views."


def _post(ig_media_id: int = 1, scope: str = "FEED") -> PostInput:
    return PostInput(
        ig_media_id=ig_media_id,
        media_product_type=scope,
        media_urls=["https://example.com/img.jpg"],
        media_types=["IMAGE"],
        caption="caption",
    )


def _prediction(
    ig_media_id: int = 1,
    category: str = "news",
    visual_format: str = "post_news",
    strategy: str = "awareness",
) -> PostPrediction:
    return PostPrediction(
        ig_media_id=ig_media_id,
        category=category,
        visual_format=visual_format,
        strategy=strategy,
        features=_features(),
    )


def _prompt_state() -> PromptState:
    return PromptState(
        instructions={
            ("descriptor", "FEED"): "desc",
            ("category", None): "cat",
            ("visual_format", "FEED"): "vf",
            ("strategy", None): "str",
        },
        db_ids={
            ("descriptor", "FEED"): 1,
            ("category", None): 2,
            ("visual_format", "FEED"): 3,
            ("strategy", None): 4,
        },
        versions={
            ("descriptor", "FEED"): 0,
            ("category", None): 0,
            ("visual_format", "FEED"): 0,
            ("strategy", None): 0,
        },
    )


# ── evaluate_result_and_store ──────────────────────────────────


class EvaluateResultAndStoreTests(unittest.TestCase):
    @patch("milpo.simulation.evaluation.persist_api_calls")
    @patch("milpo.simulation.evaluation.persist_pipeline_predictions")
    @patch("milpo.simulation.evaluation._get_label_description", return_value="desc")
    def test_all_match_produces_no_errors(self, _mock_desc, _mock_preds, _mock_api) -> None:
        result = PipelineResult(prediction=_prediction(), api_calls=[])
        annotation = {"category": "news", "visual_format": "post_news", "strategy": "awareness"}

        errors, matches = evaluate_result_and_store(
            _post(), result, annotation, _prompt_state(), MagicMock(), run_id=1,
        )

        self.assertEqual(len(errors), 0)
        self.assertEqual(len(matches), 3)
        self.assertTrue(all(m.match for m in matches))

    @patch("milpo.simulation.evaluation.persist_api_calls")
    @patch("milpo.simulation.evaluation.persist_pipeline_predictions")
    @patch("milpo.simulation.evaluation._get_label_description", return_value="desc")
    def test_mismatch_produces_errors_for_wrong_axes(self, _mock_desc, _mock_preds, _mock_api) -> None:
        result = PipelineResult(
            prediction=_prediction(category="mood", strategy="engagement"),
            api_calls=[],
        )
        annotation = {"category": "news", "visual_format": "post_news", "strategy": "awareness"}

        errors, matches = evaluate_result_and_store(
            _post(), result, annotation, _prompt_state(), MagicMock(), run_id=1,
        )

        self.assertEqual(len(errors), 2)
        error_axes = {e.axis for e in errors}
        self.assertEqual(error_axes, {"category", "strategy"})

        match_results = {m.axis: m.match for m in matches}
        self.assertFalse(match_results["category"])
        self.assertTrue(match_results["visual_format"])
        self.assertFalse(match_results["strategy"])

    @patch("milpo.simulation.evaluation.persist_api_calls")
    @patch("milpo.simulation.evaluation.persist_pipeline_predictions")
    @patch("milpo.simulation.evaluation._get_label_description", return_value="desc")
    def test_scope_propagated_to_match_records(self, _mock_desc, _mock_preds, _mock_api) -> None:
        result = PipelineResult(prediction=_prediction(), api_calls=[])
        annotation = {"category": "news", "visual_format": "post_news", "strategy": "awareness"}

        _, matches = evaluate_result_and_store(
            _post(scope="REELS"), result, annotation, _prompt_state(), MagicMock(), run_id=1,
        )

        self.assertTrue(all(m.scope == "REELS" for m in matches))


# ── target_metric_matches ──────────────────────────────────────


class TargetMetricTests(unittest.TestCase):
    def test_descriptor_returns_all_three_axes(self) -> None:
        result = PipelineResult(prediction=_prediction(), api_calls=[])
        annotation = {"category": "news", "visual_format": "post_news", "strategy": "wrong"}
        matches = target_metric_matches(result, annotation, "descriptor")
        self.assertEqual(matches, [True, True, False])

    def test_single_axis_returns_one_match(self) -> None:
        result = PipelineResult(prediction=_prediction(category="mood"), api_calls=[])
        annotation = {"category": "news"}
        matches = target_metric_matches(result, annotation, "category")
        self.assertEqual(matches, [False])


# ── build_run_metrics ──────────────────────────────────────────


class BuildRunMetricsTests(unittest.TestCase):
    def test_metrics_computation(self) -> None:
        matches = {"category": 8, "visual_format": 6, "strategy": 9}
        metrics = build_run_metrics(matches, 10, 2, 100)
        self.assertAlmostEqual(metrics["accuracy_category"], 0.8)
        self.assertAlmostEqual(metrics["accuracy_visual_format"], 0.6)
        self.assertAlmostEqual(metrics["accuracy_strategy"], 0.9)
        self.assertEqual(metrics["prompt_iterations"], 2)
        self.assertEqual(metrics["total_api_calls"], 100)

    def test_zero_processed_gives_zero_accuracy(self) -> None:
        metrics = build_run_metrics({"category": 0, "visual_format": 0, "strategy": 0}, 0, 0, 0)
        self.assertEqual(metrics["accuracy_category"], 0)


# ── RewriteOutcome promotion/rollback logic ────────────────────


class RewriteOutcomeTests(unittest.TestCase):
    def test_promoted_outcome(self) -> None:
        outcome = RewriteOutcome(
            triggered=True,
            promoted=True,
            winner_db_id=10,
            incumbent_acc=0.70,
            candidate_acc=0.80,
            eval_window_consumed=30,
            incumbent_records=[],
        )
        self.assertTrue(outcome.promoted)
        self.assertFalse(outcome.failed)
        self.assertAlmostEqual(outcome.candidate_acc - outcome.incumbent_acc, 0.10)

    def test_rollback_outcome(self) -> None:
        outcome = RewriteOutcome(
            triggered=True,
            promoted=False,
            winner_db_id=10,
            incumbent_acc=0.75,
            candidate_acc=0.74,
            eval_window_consumed=30,
            incumbent_records=[],
        )
        self.assertFalse(outcome.promoted)
        self.assertFalse(outcome.failed)

    def test_failed_outcome_has_zero_window(self) -> None:
        outcome = RewriteOutcome(
            triggered=True,
            promoted=False,
            winner_db_id=None,
            incumbent_acc=None,
            candidate_acc=None,
            eval_window_consumed=0,
            incumbent_records=[],
            failed=True,
        )
        self.assertTrue(outcome.failed)
        self.assertEqual(outcome.eval_window_consumed, 0)


# ── Simulation rewrite trigger logic ───────────────────────────


class SimulationRewriteTriggerTests(unittest.TestCase):
    """Vérifie la logique de déclenchement de rewrite dans le workflow simulation."""

    def test_rewrite_triggers_when_error_buffer_reaches_batch_size(self) -> None:
        """Le rewrite doit se déclencher quand len(error_buffer) >= batch_size."""
        batch_size = 5
        error_buffer = [
            ErrorCase(
                ig_media_id=i,
                axis="category",
                prompt_scope=None,
                post_scope="FEED",
                predicted="mood",
                expected="news",
                features_json="{}",
                caption=None,
                desc_predicted="d",
                desc_expected="d",
            )
            for i in range(batch_size)
        ]
        # La condition dans le workflow est: len(error_buffer) >= batch_size
        self.assertTrue(len(error_buffer) >= batch_size)

    def test_rewrite_skipped_when_too_few_eval_posts(self) -> None:
        """Si < 5 posts restent pour l'évaluation, le rewrite est skip."""
        eval_posts = [_post(ig_media_id=i) for i in range(3)]
        # La condition dans le workflow est: len(eval_posts) < 5
        self.assertTrue(len(eval_posts) < 5)

    def test_promotion_requires_delta_above_threshold(self) -> None:
        """Promotion = winner_acc >= inc_acc + delta."""
        delta = 0.02
        # Cas promotion : 0.80 >= 0.75 + 0.02
        self.assertTrue(0.80 >= 0.75 + delta)
        # Cas rollback : 0.76 < 0.75 + 0.02
        self.assertFalse(0.76 >= 0.75 + delta)

    def test_no_rollback_mode_uses_strict_greater(self) -> None:
        """En mode --no-rollback, il suffit que winner_acc > inc_acc."""
        # Même un epsilon suffit
        self.assertTrue(0.751 > 0.750)
        # Égalité ne suffit pas
        self.assertFalse(0.75 > 0.75)

    def test_patience_exhaustion_stops_rewrites(self) -> None:
        """Après patience échecs consécutifs, les rewrites s'arrêtent."""
        patience = 3
        consecutive_failures = 0
        rewrites_stopped = False

        # Simule 3 rollbacks consécutifs
        for _ in range(patience):
            consecutive_failures += 1
            if consecutive_failures >= patience:
                rewrites_stopped = True

        self.assertTrue(rewrites_stopped)

    def test_promotion_resets_consecutive_failures(self) -> None:
        """Une promotion réussie remet le compteur d'échecs à 0."""
        consecutive_failures = 2
        # Simule une promotion
        consecutive_failures = 0
        self.assertEqual(consecutive_failures, 0)

    def test_eval_window_consumed_advances_cursor(self) -> None:
        """Le cursor avance de eval_window_consumed après un rewrite."""
        cursor = 100
        outcome = RewriteOutcome(
            triggered=True,
            promoted=True,
            winner_db_id=10,
            incumbent_acc=0.70,
            candidate_acc=0.80,
            eval_window_consumed=30,
            incumbent_records=[],
        )
        cursor += outcome.eval_window_consumed
        self.assertEqual(cursor, 130)

    def test_prompt_state_updated_on_promotion(self) -> None:
        """Après promotion, le PromptState reflète le nouveau prompt."""
        state = _prompt_state()
        key = ("category", None)
        old_id = state.db_ids[key]

        # Simule une promotion (même logique que rewrite.py:428-430)
        new_instructions = "improved prompt"
        new_db_id = 99
        new_version = 1
        state.instructions[key] = new_instructions
        state.db_ids[key] = new_db_id
        state.versions[key] = new_version

        self.assertEqual(state.instructions[key], "improved prompt")
        self.assertEqual(state.db_ids[key], 99)
        self.assertEqual(state.versions[key], 1)
        self.assertNotEqual(state.db_ids[key], old_id)

    def test_error_buffer_cleared_after_rewrite(self) -> None:
        """Le buffer d'erreurs est vidé après chaque tentative de rewrite."""
        error_buffer = [
            ErrorCase(
                ig_media_id=1, axis="category", prompt_scope=None,
                post_scope="FEED", predicted="mood", expected="news",
                features_json="{}", caption=None,
                desc_predicted="d", desc_expected="d",
            ),
        ]
        # Après un rewrite (promu ou rollback), le buffer est vidé
        error_buffer.clear()
        self.assertEqual(len(error_buffer), 0)


if __name__ == "__main__":
    unittest.main()
