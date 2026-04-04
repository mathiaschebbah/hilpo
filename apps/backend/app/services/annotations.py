from app.repositories.annotations import AnnotationRepository
from app.schemas.annotations import AnnotationCreate, AnnotationOut


class AnnotationService:
    def __init__(self, repository: AnnotationRepository):
        self.repository = repository

    async def create(self, data: AnnotationCreate, annotator: str) -> AnnotationOut:
        row = await self.repository.upsert(
            ig_media_id=data.ig_media_id,
            category_id=data.category_id,
            visual_format_id=data.visual_format_id,
            strategy=data.strategy,
            annotator=annotator,
        )
        return AnnotationOut(**row)
