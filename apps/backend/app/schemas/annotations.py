from datetime import datetime
from typing import Literal
from pydantic import BaseModel


class AnnotationCreate(BaseModel):
    ig_media_id: int
    category_id: int
    visual_format_id: int
    strategy: Literal["Organic", "Brand Content"]


class AnnotationOut(BaseModel):
    id: int
    ig_media_id: int
    category_id: int
    visual_format_id: int
    strategy: str
    annotator: str
    created_at: datetime
