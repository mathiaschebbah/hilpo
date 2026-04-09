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
    ig_media_id: str
    shortcode: str | None
    caption: str | None
    timestamp: datetime
    media_type: str
    media_product_type: str
    split: str | None = None


class AnnotationValues(BaseModel):
    category_id: int | None = None
    visual_format_id: int | None = None
    strategy: str | None = None
    doubtful: bool = False


class NextPostOut(BaseModel):
    post: PostOut
    heuristic: HeuristicLabels
    media: list[MediaOut]
    annotation: AnnotationValues | None = None


class ProgressOut(BaseModel):
    total: int
    annotated: int


class LookupOut(BaseModel):
    id: int
    name: str


class PostGridItem(BaseModel):
    ig_media_id: str
    shortcode: str | None = None
    caption: str | None = None
    timestamp: datetime | None = None
    media_type: str
    media_product_type: str
    split: str | None = None
    thumbnail_url: str | None = None
    category: str | None = None
    visual_format: str | None = None
    strategy: str | None = None
    annotation_category: str | None = None
    annotation_visual_format: str | None = None
    annotation_strategy: str | None = None
    annotation_doubtful: bool = False
    is_annotated: bool = False


class PostGridPage(BaseModel):
    items: list[PostGridItem]
    total: int
    offset: int
    limit: int
