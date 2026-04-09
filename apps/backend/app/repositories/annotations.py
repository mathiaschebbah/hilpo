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
        doubtful: bool = False,
    ) -> dict:
        result = await self.db.execute(
            text("""
                INSERT INTO annotations
                    (ig_media_id, category_id, visual_format_id, strategy, annotator, doubtful)
                VALUES
                    (:ig_media_id, :category_id, :visual_format_id, :strategy, :annotator, :doubtful)
                ON CONFLICT (ig_media_id, annotator) DO UPDATE SET
                    category_id = EXCLUDED.category_id,
                    visual_format_id = EXCLUDED.visual_format_id,
                    strategy = EXCLUDED.strategy,
                    doubtful = EXCLUDED.doubtful,
                    created_at = NOW()
                RETURNING id, ig_media_id, category_id, visual_format_id,
                          strategy, doubtful, annotator, created_at
            """),
            {
                "ig_media_id": ig_media_id,
                "category_id": category_id,
                "visual_format_id": visual_format_id,
                "strategy": strategy,
                "annotator": annotator,
                "doubtful": doubtful,
            },
        )
        await self.db.commit()
        return dict(result.mappings().first())

    async def bulk_upsert(
        self,
        items: list[dict],
        annotator: str,
    ) -> list[dict]:
        """UPSERT multiple annotations en une transaction.

        Chaque item doit contenir : ig_media_id (int), category_id, visual_format_id,
        strategy, doubtful. Le champ annotator est appliqué à tous.
        Retourne la liste des rows créées ou mises à jour dans l'ordre d'entrée.
        """
        if not items:
            return []

        rows: list[dict] = []
        for item in items:
            result = await self.db.execute(
                text("""
                    INSERT INTO annotations
                        (ig_media_id, category_id, visual_format_id, strategy, annotator, doubtful)
                    VALUES
                        (:ig_media_id, :category_id, :visual_format_id, :strategy, :annotator, :doubtful)
                    ON CONFLICT (ig_media_id, annotator) DO UPDATE SET
                        category_id = EXCLUDED.category_id,
                        visual_format_id = EXCLUDED.visual_format_id,
                        strategy = EXCLUDED.strategy,
                        doubtful = EXCLUDED.doubtful,
                        created_at = NOW()
                    RETURNING id, ig_media_id, category_id, visual_format_id,
                              strategy, doubtful, annotator, created_at
                """),
                {
                    "ig_media_id": item["ig_media_id"],
                    "category_id": item["category_id"],
                    "visual_format_id": item["visual_format_id"],
                    "strategy": item["strategy"],
                    "annotator": annotator,
                    "doubtful": item.get("doubtful", False),
                },
            )
            rows.append(dict(result.mappings().first()))

        await self.db.commit()
        return rows
