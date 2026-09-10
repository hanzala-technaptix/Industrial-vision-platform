"""FastAPI application."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import events, routes, showcase, video
from app.events.repository import init_db
from app.pipeline.session import LiveSession, initial_source, initial_use_case


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    session = LiveSession()
    app.state.session = session
    app.state.camera_manager = session.camera_manager
    app.state.event_engine = session.event_engine

    use_case = initial_use_case()
    try:
        session.start(use_case, source=initial_source(use_case))
    except FileNotFoundError as exc:
        print(f"[api] no video for {use_case}: {exc}")
    app.state.pipeline = session.pipeline

    try:
        yield
    finally:
        session.stop()


app = FastAPI(title="Industrial Vision AI", version="0.3.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(routes.router)
app.include_router(events.router)
app.include_router(video.router)
app.include_router(showcase.router)
