from datetime import datetime
from pydantic import BaseModel


class MediaOut(BaseModel):
    media_url: str | None
    thumbnail_url: str | None
    media_type: str
    media_order: int
    width: int | None
    height: int | None


class HeuristicLabels(BaseModel):
    category_id: int | None = None
    heuristic_category: str | None = None
    visual_format_id: int | None = None
    heuristic_visual_format: str | None = None
    heuristic_strategy: str | None = None
    heuristic_subcategory: str | None = None


class PostOut(BaseModel):
    ig_media_id: int
    shortcode: str | None
    caption: str | None
    timestamp: datetime
    media_type: str
    media_product_type: str


class NextPostOut(BaseModel):
    post: PostOut
    heuristic: HeuristicLabels
    media: list[MediaOut]


class ProgressOut(BaseModel):
    total: int
    annotated: int


class LookupOut(BaseModel):
    id: int
    name: str
