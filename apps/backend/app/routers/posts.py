from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.repositories.posts import PostRepository
from app.schemas.posts import LookupOut, NextPostOut, ProgressOut
from app.services.posts import PostService

router = APIRouter(prefix="/v1/posts", tags=["posts"])


def get_service(db: AsyncSession = Depends(get_db)) -> PostService:
    return PostService(PostRepository(db))


@router.get("/next", response_model=NextPostOut)
async def get_next_post(
    annotator: str = "mathias",
    service: PostService = Depends(get_service),
):
    return await service.get_next_post(annotator)


@router.get("/progress", response_model=ProgressOut)
async def get_progress(
    annotator: str = "mathias",
    service: PostService = Depends(get_service),
):
    return await service.get_progress(annotator)


@router.get("/categories", response_model=list[LookupOut])
async def get_categories(service: PostService = Depends(get_service)):
    return await service.get_categories()


@router.get("/visual-formats", response_model=list[LookupOut])
async def get_visual_formats(service: PostService = Depends(get_service)):
    return await service.get_visual_formats()
