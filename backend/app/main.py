from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import init_db
from .routers import me, public

@asynccontextmanager
async def lifespan(_app: FastAPI):
    # For the prototype we create tables on boot. Move to Alembic migrations once the schema settles.
    init_db()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="CleanCravings API",
    version="0.2.0",
    description="SC2006 SCSL Group 4. Serves NEA, SFA and HPB data through our own API (NFR-5).",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(public.router)
app.include_router(me.router)


@app.get("/api/health", tags=["public"])
def health() -> dict[str, bool]:
    return {"ok": True}
