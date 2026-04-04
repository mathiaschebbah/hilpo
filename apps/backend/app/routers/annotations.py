from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.repositories.annotations import AnnotationRepository
from app.schemas.annotations import AnnotationCreate, AnnotationOut
from app.services.annotations import AnnotationService

router = APIRouter(prefix="/v1/annotations", tags=["annotations"])


def get_service(db: AsyncSession = Depends(get_db)) -> AnnotationService:
    return AnnotationService(AnnotationRepository(db))


@router.post("/", response_model=AnnotationOut, status_code=201)
async def create_annotation(
    data: AnnotationCreate,
    annotator: str = "mathias",
    service: AnnotationService = Depends(get_service),
):
    annotation = await service.create(data, annotator)
    return JSONResponse(
        status_code=201,
        content=annotation.model_dump(mode="json"),
        headers={"Location": f"/v1/annotations/{annotation.id}"},
    )
