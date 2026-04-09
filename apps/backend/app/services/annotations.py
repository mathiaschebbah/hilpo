from app.repositories.annotations import AnnotationRepository
from app.schemas.annotations import (
    AnnotationCreate,
    AnnotationOut,
    BulkAnnotationCreate,
    BulkAnnotationResult,
)


class AnnotationService:
    def __init__(self, repository: AnnotationRepository):
        self.repository = repository

    async def create(self, data: AnnotationCreate, annotator: str) -> AnnotationOut:
        row = await self.repository.upsert(
            ig_media_id=int(data.ig_media_id),
            category_id=data.category_id,
            visual_format_id=data.visual_format_id,
            strategy=data.strategy,
            annotator=annotator,
            doubtful=data.doubtful,
        )
        return AnnotationOut(**{**row, "ig_media_id": str(row["ig_media_id"])})

    async def create_bulk(
        self, data: BulkAnnotationCreate, annotator: str
    ) -> BulkAnnotationResult:
        items = [
            {
                "ig_media_id": int(a.ig_media_id),
                "category_id": a.category_id,
                "visual_format_id": a.visual_format_id,
                "strategy": a.strategy,
                "doubtful": a.doubtful,
            }
            for a in data.annotations
        ]
        rows = await self.repository.bulk_upsert(items, annotator)
        created = [
            AnnotationOut(**{**row, "ig_media_id": str(row["ig_media_id"])})
            for row in rows
        ]
        return BulkAnnotationResult(created=created, count=len(created))
