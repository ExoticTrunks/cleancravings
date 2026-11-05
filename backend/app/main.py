import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .controllers.hawker_centre_controller import HawkerCentreController
from .controllers.recommendation_controller import RecommendationController
from .db import SessionLocal, engine, init_db
from .geo import today_sg
from .routers import me, public


def _warm_centre_cache() -> None:
    # Builds the centre and recommendation caches in the background so the first Finder or
    # Home visit isn't the slow one (NFR-1). If it fails, the first request builds them instead.
    db = SessionLocal()
    try:
        HawkerCentreController.list_centres(db, today_sg())
        RecommendationController.recommend(db, today_sg())
    except Exception:  # noqa: BLE001
        pass
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # For the prototype we create tables on boot. Move to Alembic migrations once the schema settles.
    init_db()
    # Only worth it against the hosted database; local SQLite builds the cache in milliseconds
    if engine.dialect.name == "postgresql":
        threading.Thread(target=_warm_centre_cache, daemon=True).start()
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
