"""FastAPI app entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from clue.api import auth, system
from clue.core.config import get_settings
from clue.core.db import SessionLocal
from clue.seed import ensure_reference_data


@asynccontextmanager
async def lifespan(app: FastAPI):
    with SessionLocal() as db:
        ensure_reference_data(db)
    yield


app = FastAPI(title="Clue AI API", version="0.1.0", lifespan=lifespan, docs_url="/docs", openapi_url="/openapi.json")
app.add_middleware(
    CORSMiddleware, allow_origins=[get_settings().site_url], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)
app.include_router(system.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
