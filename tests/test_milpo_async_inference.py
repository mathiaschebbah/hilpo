from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, patch

from milpo.async_inference import async_classify_post, async_classify_with_features
from milpo.inference import ApiCallLog, PostInput, PromptSet
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


def _prompt_set() -> PromptSet:
    return PromptSet(
        descriptor_instructions="describe",
        category_instructions="category",
        visual_format_instructions="vf",
        strategy_instructions="strategy",
        descriptor_descriptions="desc",
        category_descriptions="cat desc",
        visual_format_descriptions="vf desc",
        strategy_descriptions="str desc",
    )


def _post() -> PostInput:
    return PostInput(
        ig_media_id=1,
        media_product_type="FEED",
        media_urls=["https://example.com/img.jpg"],
        media_types=["IMAGE"],
        caption="caption",
    )


class AsyncInferenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_async_classify_with_features_uses_precomputed_features(self) -> None:
        desc_log = ApiCallLog("descriptor", "gemini", 10, 2, 20)
        classifier_logs = [
            ("news", "high", ApiCallLog("category", "qwen", 1, 1, 1)),
            ("post_news", "high", ApiCallLog("visual_format", "qwen", 1, 1, 1)),
            ("awareness", "medium", ApiCallLog("strategy", "qwen", 1, 1, 1)),
        ]

        with patch("milpo.async_inference.async_call_classifier", new=AsyncMock(side_effect=classifier_logs)):
            result = await async_classify_with_features(
                post=_post(),
                features=_features(),
                desc_log=desc_log,
                prompts=_prompt_set(),
                category_labels=["news"],
                visual_format_labels=["post_news"],
                strategy_labels=["awareness"],
                client=object(),
                semaphore=asyncio.Semaphore(4),
            )

        self.assertEqual(result.prediction.category, "news")
        self.assertEqual(result.prediction.visual_format, "post_news")
        self.assertEqual(result.prediction.strategy, "awareness")
        self.assertEqual(len(result.api_calls), 4)

    async def test_async_classify_post_calls_descriptor_then_shared_classifier_core(self) -> None:
        with patch(
            "milpo.async_inference.async_call_descriptor",
            new=AsyncMock(return_value=(_features(), ApiCallLog("descriptor", "gemini", 3, 1, 5))),
        ), patch(
            "milpo.async_inference.async_call_classifier",
            new=AsyncMock(side_effect=[
                ("news", "high", ApiCallLog("category", "qwen", 1, 1, 1)),
                ("post_news", "high", ApiCallLog("visual_format", "qwen", 1, 1, 1)),
                ("awareness", "low", ApiCallLog("strategy", "qwen", 1, 1, 1)),
            ]),
        ):
            result = await async_classify_post(
                post=_post(),
                prompts=_prompt_set(),
                category_labels=["news"],
                visual_format_labels=["post_news"],
                strategy_labels=["awareness"],
                client=object(),
                semaphore=asyncio.Semaphore(4),
            )

        self.assertEqual(result.prediction.ig_media_id, 1)
        self.assertEqual(result.prediction.strategy, "awareness")


if __name__ == "__main__":
    unittest.main()
