from __future__ import annotations

import unittest

from milpo.importing import normalize_media_row, normalize_post_row


class ImportingNormalizationTests(unittest.TestCase):
    def test_normalize_post_row_coerces_booleans_and_empty_shortcode(self) -> None:
        normalized = normalize_post_row({
            "ig_media_id": "1",
            "shortcode": "",
            "ig_user_id": "2",
            "caption": "caption",
            "timestamp": "2026-01-01",
            "media_type": "IMAGE",
            "media_product_type": "FEED",
            "followed_post": "true",
            "suspected": "false",
            "authors_checked": "true",
            "inserted_at": "2026-01-01",
            "boosted_post": "false",
        })

        self.assertIsNone(normalized["shortcode"])
        self.assertTrue(normalized["followed_post"])
        self.assertFalse(normalized["suspected_bool"])
        self.assertTrue(normalized["authors_checked_bool"])
        self.assertFalse(normalized["boosted_post_bool"])

    def test_normalize_media_row_coerces_numeric_fields_and_empty_urls(self) -> None:
        normalized = normalize_media_row({
            "ig_media_id": "1",
            "parent_ig_media_id": "1",
            "media_order": "0",
            "media_type": "IMAGE",
            "width": "1080",
            "height": "",
            "duration": "12.5",
            "media_url": "",
            "thumbnail_url": "https://example.com/thumb.jpg",
        })

        self.assertEqual(normalized["width"], 1080)
        self.assertIsNone(normalized["height"])
        self.assertEqual(normalized["duration"], 12.5)
        self.assertIsNone(normalized["media_url"])
        self.assertEqual(normalized["thumbnail_url"], "https://example.com/thumb.jpg")


if __name__ == "__main__":
    unittest.main()
