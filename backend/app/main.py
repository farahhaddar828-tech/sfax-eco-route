import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from .api import analytics, assistant, open311, reports, routing
from .config import get_settings
from .db import Base, SessionLocal, engine
from .graph.road_graph import get_graph

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(engine)  # Alembic migrations would replace this in production
    g = get_graph()                    # load + warm the road graph once
    logging.getLogger("ecoroute").info("Road graph ready: %s", g.stats())
    yield


app = FastAPI(title=settings.app_name, version="2.0.0", lifespan=lifespan,
              description="Citizen reporting + road-network intelligence for Grand Sfax.")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","),
                   allow_methods=["*"], allow_headers=["*"])

for r in (reports.router, routing.router, analytics.router, assistant.router, open311.router):
    app.include_router(r, prefix="/api/v1" if r is not open311.router else "")

os.makedirs(reports.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=reports.UPLOAD_DIR), name="uploads")
Instrumentator().instrument(app).expose(app, include_in_schema=False)


@app.get("/healthz", tags=["ops"])
def healthz():
    """Liveness: the process is up."""
    return {"status": "ok"}


@app.get("/readyz", tags=["ops"])
def readyz():
    """Readiness: DB reachable and road graph loaded (used by the k8s readinessProbe)."""
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return {"status": "ready", "graph": get_graph().source}
