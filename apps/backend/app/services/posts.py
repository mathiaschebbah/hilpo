from app.exceptions import AllAnnotatedError
from app.repositories.posts import PostRepository
from app.schemas.posts import (
    HeuristicLabels,
    LookupOut,
    MediaOut,
    NextPostOut,
    PostOut,
    ProgressOut,
)


class PostService:
    def __init__(self, repository: PostRepository):
        self.repository = repository

    async def get_next_post(self, annotator: str) -> NextPostOut:
        row = await self.repository.find_next_unannotated(annotator)
        if not row:
            raise AllAnnotatedError(annotator)

        media_rows = await self.repository.find_media_by_post(row["ig_media_id"])

        return NextPostOut(
            post=PostOut(
                ig_media_id=row["ig_media_id"],
                shortcode=row["shortcode"],
                caption=row["caption"],
                timestamp=row["timestamp"],
                media_type=row["media_type"],
                media_product_type=row["media_product_type"],
            ),
            heuristic=HeuristicLabels(
                category_id=row["category_id"],
                heuristic_category=row["heuristic_category"],
                visual_format_id=row["visual_format_id"],
                heuristic_visual_format=row["heuristic_visual_format"],
                heuristic_strategy=row["heuristic_strategy"],
                heuristic_subcategory=row["heuristic_subcategory"],
            ),
            media=[MediaOut(**m) for m in media_rows],
        )

    async def get_progress(self, annotator: str) -> ProgressOut:
        row = await self.repository.count_progress(annotator)
        return ProgressOut(**row)

    async def get_categories(self) -> list[LookupOut]:
        rows = await self.repository.find_all_categories()
        return [LookupOut(**r) for r in rows]

    async def get_visual_formats(self) -> list[LookupOut]:
        rows = await self.repository.find_all_visual_formats()
        return [LookupOut(**r) for r in rows]
