"""Tests pour milpo.persistence — cycle de vie runs + persistance classifications."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, call

from milpo.inference import ApiCallLog, PipelineResult, PostInput
from milpo.persistence.classification import (
    persist_api_calls,
    persist_pipeline_predictions,
    resolve_prompt_id,
)
from milpo.persistence.runs import (
    create_run,
    fail_run,
    finish_extraction_run,
    finish_run,
    get_or_create_extraction_run,
)
from milpo.schemas import DescriptorFeatures


def _features() -> DescriptorFeatures:
    return DescriptorFeatures.model_validate({
        "resume_visuel": "resume",
        "texte_overlay": {
            "present": True,
            "type": "titre_editorial",
            "contenu_resume": "headline",
            "chiffre_dominant": False,
        },
        "logos": {
            "views": True,
            "specifique": None,
            "marque_partenaire": None,
            "gabarit_views_identifie": True,
        },
        "mise_en_page": {
            "fond": "photo_plein_cadre",
            "nombre_slides": 1,
            "structure": "slide_unique",
            "carousel_nature": "non_carousel",
        },
        "contenu_principal": {
            "personnes_visibles": False,
            "type_personne": None,
            "screenshots_film": False,
            "pochettes_album": False,
            "zoom_objet": False,
            "photos_evenement": False,
            "chiffre_marquant_visible": False,
        },
        "audio_video": {
            "voix_off_narrative": False,
            "interview_face_camera": False,
            "interview_setting": None,
            "musique_dominante": False,
            "type_montage": None,
            "montage_recap_evenement": False,
        },
        "analyse_caption": {
            "longueur": 10,
            "mentions_marques": [],
            "hashtags_format": None,
            "mention_partenariat": False,
            "sujet_resume": "topic",
        },
        "indices_brand_content": {
            "produit_mis_en_avant": False,
            "mention_partenariat_caption": False,
            "logo_marque_commerciale": False,
        },
        "elements_discriminants": [],
    })


# ── resolve_prompt_id ──────────────────────────────────────────


class ResolvePromptIdTests(unittest.TestCase):
    def test_scoped_agent_uses_scope_key(self) -> None:
        prompt_ids = {
            ("descriptor", "FEED"): 10,
            ("descriptor", "REELS"): 11,
        }
        self.assertEqual(resolve_prompt_id(prompt_ids, "descriptor", "FEED"), 10)
        self.assertEqual(resolve_prompt_id(prompt_ids, "descriptor", "REELS"), 11)

    def test_unscoped_agent_ignores_scope(self) -> None:
        prompt_ids = {("category", None): 20}
        self.assertEqual(resolve_prompt_id(prompt_ids, "category", "FEED"), 20)
        self.assertEqual(resolve_prompt_id(prompt_ids, "category", None), 20)

    def test_visual_format_uses_scope(self) -> None:
        prompt_ids = {
            ("visual_format", "FEED"): 30,
            ("visual_format", "REELS"): 31,
        }
        self.assertEqual(resolve_prompt_id(prompt_ids, "visual_format", "FEED"), 30)

    def test_returns_none_when_missing(self) -> None:
        self.assertIsNone(resolve_prompt_id({}, "category", None))


# ── persist_pipeline_predictions ───────────────────────────────


class PersistPredictionsTests(unittest.TestCase):
    def test_stores_three_axes_plus_descriptor(self) -> None:
        from milpo.schemas import PostPrediction

        features = _features()
        prediction = PostPrediction(
            ig_media_id=42,
            category="news",
            visual_format="post_news",
            strategy="awareness",
            features=features,
        )
        result = PipelineResult(prediction=prediction, api_calls=[])
        prompt_ids = {
            ("category", None): 1,
            ("visual_format", "FEED"): 2,
            ("strategy", None): 3,
            ("descriptor", "FEED"): 4,
        }

        with unittest.mock.patch("milpo.persistence.classification.store_prediction") as mock_store:
            mock_store.return_value = 99
            persist_pipeline_predictions(
                MagicMock(),
                post_id=42,
                scope="FEED",
                result=result,
                prompt_ids=prompt_ids,
                run_id=7,
                store_descriptor=True,
            )

        # 3 axes + 1 descriptor = 4 calls
        self.assertEqual(mock_store.call_count, 4)
        agents_stored = [c.args[2] for c in mock_store.call_args_list]
        self.assertIn("category", agents_stored[:3])
        self.assertIn("visual_format", agents_stored[:3])
        self.assertIn("strategy", agents_stored[:3])

    def test_skips_descriptor_when_disabled(self) -> None:
        from milpo.schemas import PostPrediction

        prediction = PostPrediction(
            ig_media_id=42,
            category="news",
            visual_format="post_news",
            strategy="awareness",
            features=_features(),
        )
        result = PipelineResult(prediction=prediction, api_calls=[])
        prompt_ids = {
            ("category", None): 1,
            ("visual_format", "FEED"): 2,
            ("strategy", None): 3,
            ("descriptor", "FEED"): 4,
        }

        with unittest.mock.patch("milpo.persistence.classification.store_prediction") as mock_store:
            mock_store.return_value = 99
            persist_pipeline_predictions(
                MagicMock(),
                post_id=42,
                scope="FEED",
                result=result,
                prompt_ids=prompt_ids,
                run_id=7,
                store_descriptor=False,
            )

        # 3 axes only, no descriptor
        self.assertEqual(mock_store.call_count, 3)


# ── persist_api_calls ──────────────────────────────────────────


class PersistApiCallsTests(unittest.TestCase):
    def test_stores_each_api_call_with_correct_prompt_id(self) -> None:
        api_calls = [
            ApiCallLog("descriptor", "gemini", 100, 50, 200),
            ApiCallLog("category", "qwen", 10, 5, 30),
        ]
        prompt_ids = {
            ("descriptor", "FEED"): 4,
            ("category", None): 1,
        }

        with unittest.mock.patch("milpo.persistence.classification.store_api_call") as mock_store:
            mock_store.return_value = 1
            total = persist_api_calls(
                MagicMock(),
                post_id=42,
                scope="FEED",
                api_calls=api_calls,
                prompt_ids=prompt_ids,
                run_id=7,
                call_type="classification",
            )

        self.assertEqual(total, 2)
        self.assertEqual(mock_store.call_count, 2)


# ── Run lifecycle ──────────────────────────────────────────────


class RunLifecycleTests(unittest.TestCase):
    def _mock_conn(self, returning: dict | None = None) -> MagicMock:
        conn = MagicMock()
        if returning:
            conn.execute.return_value.fetchone.return_value = returning
        return conn

    def test_create_run_inserts_and_returns_id(self) -> None:
        conn = self._mock_conn(returning={"id": 42})
        config = {"name": "test", "batch_size": 30}
        run_id = create_run(conn, config)
        self.assertEqual(run_id, 42)
        conn.commit.assert_called_once()

    def test_finish_run_sets_completed(self) -> None:
        conn = self._mock_conn()
        metrics = {
            "accuracy_category": 0.85,
            "accuracy_visual_format": 0.65,
            "accuracy_strategy": 0.94,
            "prompt_iterations": 3,
            "total_api_calls": 1200,
            "total_cost_usd": 2.50,
        }
        finish_run(conn, 42, metrics)
        conn.execute.assert_called_once()
        conn.commit.assert_called_once()
        sql = conn.execute.call_args[0][0]
        self.assertIn("completed", sql)

    def test_fail_run_sets_failed_with_reason(self) -> None:
        conn = self._mock_conn()
        metrics = {
            "accuracy_category": 0.50,
            "accuracy_visual_format": 0.30,
            "accuracy_strategy": 0.60,
            "prompt_iterations": 1,
            "total_api_calls": 400,
            "total_cost_usd": None,
        }
        fail_run(conn, 42, "timeout", metrics)
        conn.execute.assert_called_once()
        conn.commit.assert_called_once()
        sql = conn.execute.call_args[0][0]
        self.assertIn("failed", sql)

    def test_get_or_create_extraction_run_returns_existing(self) -> None:
        conn = self._mock_conn(returning={"id": 99})
        run_id = get_or_create_extraction_run(conn)
        self.assertEqual(run_id, 99)
        # Only one execute (the SELECT), no INSERT
        self.assertEqual(conn.execute.call_count, 1)

    def test_get_or_create_extraction_run_creates_when_absent(self) -> None:
        conn = MagicMock()
        # First SELECT returns None, second INSERT returns the new id
        conn.execute.return_value.fetchone.side_effect = [None, {"id": 100}]
        run_id = get_or_create_extraction_run(conn)
        self.assertEqual(run_id, 100)
        self.assertEqual(conn.execute.call_count, 2)

    def test_finish_extraction_run_updates_config(self) -> None:
        conn = self._mock_conn()
        finish_extraction_run(conn, 99, n_processed=50, n_skipped=10)
        conn.execute.assert_called_once()
        conn.commit.assert_called_once()
        params = conn.execute.call_args[0][1]
        payload = json.loads(params[0])
        self.assertEqual(payload["n_processed"], 50)
        self.assertEqual(payload["n_skipped_already_cached"], 10)


if __name__ == "__main__":
    unittest.main()
