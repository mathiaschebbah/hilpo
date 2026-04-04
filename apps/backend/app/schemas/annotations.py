from datetime import datetime
from typing import Literal
from pydantic import BaseModel, field_validator


def normalize_media_id(value: str | int) -> str:
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str) and value.isdigit():
        return value
    raise ValueError("ig_media_id must be a numeric string")


class AnnotationCreate(BaseModel):
    ig_media_id: str
    category_id: int
    visual_format_id: int
    strategy: Literal["Organic", "Brand Content"]
    doubtful: bool = False

    _normalize_media_id = field_validator("ig_media_id", mode="before")(normalize_media_id)


class AnnotationOut(BaseModel):
    id: int
    ig_media_id: str
    category_id: int
    visual_format_id: int
    strategy: str
    doubtful: bool
    annotator: str
    created_at: datetime

    _normalize_media_id = field_validator("ig_media_id", mode="before")(normalize_media_id)
