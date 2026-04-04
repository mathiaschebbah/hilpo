from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class NotFoundError(Exception):
    def __init__(self, resource: str, identifier: str | int):
        self.resource = resource
        self.identifier = identifier
        self.message = f"{resource} non trouvé(e) avec id: {identifier}"
        super().__init__(self.message)


class AlreadyExistsError(Exception):
    def __init__(self, resource: str, detail: str):
        self.resource = resource
        self.detail = detail
        self.message = f"{resource} existe déjà: {detail}"
        super().__init__(self.message)


class ValidationError(Exception):
    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class AllAnnotatedError(Exception):
    def __init__(self, annotator: str):
        self.annotator = annotator
        self.message = f"Tous les posts sont annotés par {annotator}"
        super().__init__(self.message)


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(NotFoundError)
    async def not_found_handler(request: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"error": exc.message})

    @app.exception_handler(AlreadyExistsError)
    async def already_exists_handler(request: Request, exc: AlreadyExistsError):
        return JSONResponse(status_code=409, content={"error": exc.message})

    @app.exception_handler(ValidationError)
    async def validation_handler(request: Request, exc: ValidationError):
        return JSONResponse(status_code=400, content={"error": exc.message})

    @app.exception_handler(AllAnnotatedError)
    async def all_annotated_handler(request: Request, exc: AllAnnotatedError):
        return JSONResponse(status_code=200, content={"done": True, "message": exc.message})
