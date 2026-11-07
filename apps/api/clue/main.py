"""FastAPI app entrypoint."""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from clue.api import admin, ai, auth, creative, editor, money, public, render, system, tools, uploads, workspace, youtube
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


class Guard:
    """Pure ASGI middleware (does not buffer streaming responses such as the SSE job feed): refuses oversized
    bodies early and adds defensive headers to every API response."""

    MAX_BODY, MAX_UPLOAD = 4 * 1024 * 1024, 64 * 1024 * 1024
    HEADERS = [(b"x-content-type-options", b"nosniff"), (b"referrer-policy", b"strict-origin-when-cross-origin")]

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        hdrs = dict(scope["headers"])
        cap = self.MAX_UPLOAD if scope["path"].startswith("/api/uploads") else self.MAX_BODY
        try:
            n = int(hdrs.get(b"content-length", b"0") or 0)
        except ValueError:
            n = 0
        if n > cap:
            return await JSONResponse({"detail": "That request is too large."}, status_code=413)(scope, receive, send)

        async def send2(msg):
            if msg["type"] == "http.response.start":
                have = {k.lower() for k, _ in msg["headers"]}
                msg["headers"] = list(msg["headers"]) + [h for h in self.HEADERS if h[0] not in have]
            await send(msg)

        await self.app(scope, receive, send2)


app.add_middleware(Guard)
app.include_router(system.router, prefix="/api")
app.include_router(auth.router, prefix="/api")
app.include_router(public.router, prefix="/api")
app.include_router(render.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(uploads.router, prefix="/api")
app.include_router(tools.router, prefix="/api")
app.include_router(creative.router, prefix="/api")
app.include_router(editor.router, prefix="/api")
app.include_router(money.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(workspace.router, prefix="/api")
app.include_router(youtube.router, prefix="/api")
