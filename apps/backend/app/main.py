from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.exceptions import register_exception_handlers
from app.routers import posts, annotations

app = FastAPI(title="HILPO", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(posts.router)
app.include_router(annotations.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
