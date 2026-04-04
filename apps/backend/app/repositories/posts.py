from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class PostRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_next_unannotated(self, annotator: str) -> dict | None:
        result = await self.db.execute(
            text("""
                SELECT
                    p.ig_media_id, p.shortcode, p.caption, p.timestamp,
                    p.media_type, p.media_product_type,
                    h.category_id, c.name AS heuristic_category,
                    h.visual_format_id, vf.name AS heuristic_visual_format,
                    h.strategy AS heuristic_strategy,
                    h.subcategory AS heuristic_subcategory
                FROM sample_posts sp
                JOIN posts p ON p.ig_media_id = sp.ig_media_id
                LEFT JOIN heuristic_labels h ON h.ig_media_id = p.ig_media_id
                LEFT JOIN categories c ON c.id = h.category_id
                LEFT JOIN visual_formats vf ON vf.id = h.visual_format_id
                LEFT JOIN annotations a
                    ON a.ig_media_id = p.ig_media_id AND a.annotator = :annotator
                WHERE a.id IS NULL
                ORDER BY RANDOM()
                LIMIT 1
            """),
            {"annotator": annotator},
        )
        row = result.mappings().first()
        return dict(row) if row else None

    async def find_media_by_post(self, ig_media_id: int) -> list[dict]:
        result = await self.db.execute(
            text("""
                SELECT media_url, thumbnail_url, media_type,
                       media_order, width, height
                FROM post_media
                WHERE parent_ig_media_id = :post_id
                ORDER BY media_order
            """),
            {"post_id": ig_media_id},
        )
        return [dict(r) for r in result.mappings().all()]

    async def count_progress(self, annotator: str) -> dict:
        result = await self.db.execute(
            text("""
                SELECT
                    COUNT(sp.ig_media_id) AS total,
                    COUNT(a.id) AS annotated
                FROM sample_posts sp
                LEFT JOIN annotations a
                    ON a.ig_media_id = sp.ig_media_id AND a.annotator = :annotator
            """),
            {"annotator": annotator},
        )
        return dict(result.mappings().first())

    async def find_all_categories(self) -> list[dict]:
        result = await self.db.execute(
            text("SELECT id, name FROM categories ORDER BY name")
        )
        return [dict(r) for r in result.mappings().all()]

    async def find_all_visual_formats(self) -> list[dict]:
        result = await self.db.execute(
            text("SELECT id, name FROM visual_formats ORDER BY name")
        )
        return [dict(r) for r in result.mappings().all()]
