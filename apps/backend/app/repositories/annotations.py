from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class AnnotationRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def upsert(
        self,
        ig_media_id: int,
        category_id: int,
        visual_format_id: int,
        strategy: str,
        annotator: str,
    ) -> dict:
        result = await self.db.execute(
            text("""
                INSERT INTO annotations
                    (ig_media_id, category_id, visual_format_id, strategy, annotator)
                VALUES
                    (:ig_media_id, :category_id, :visual_format_id, :strategy, :annotator)
                ON CONFLICT (ig_media_id, annotator) DO UPDATE SET
                    category_id = EXCLUDED.category_id,
                    visual_format_id = EXCLUDED.visual_format_id,
                    strategy = EXCLUDED.strategy,
                    created_at = NOW()
                RETURNING id, ig_media_id, category_id, visual_format_id,
                          strategy, annotator, created_at
            """),
            {
                "ig_media_id": ig_media_id,
                "category_id": category_id,
                "visual_format_id": visual_format_id,
                "strategy": strategy,
                "annotator": annotator,
            },
        )
        await self.db.commit()
        return dict(result.mappings().first())
