import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

import config
from api.db import init_db
from api.routers import jobs, logs, media, settings, system, topics, voices
from logging_setup import configure_logging

configure_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Dashboard API started")
    yield


app = FastAPI(title="auto-yt-shorts dashboard API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router, prefix="/api")
app.include_router(topics.router, prefix="/api")
app.include_router(settings.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(voices.router, prefix="/api")
app.include_router(jobs.router, prefix="/api")
app.include_router(media.router, prefix="/api")

# Serve generated videos/media so the frontend can preview them directly.
if config.OUTPUT_PATH.exists():
    app.mount("/media/output", StaticFiles(directory=str(config.OUTPUT_PATH)), name="output")
if config.BACKGROUND_SONGS_PATH.exists():
    app.mount("/media/music", StaticFiles(directory=str(config.BACKGROUND_SONGS_PATH)), name="music")
if config.SECONDARY_CONTENT_PATH.exists():
    app.mount(
        "/media/secondary-video",
        StaticFiles(directory=str(config.SECONDARY_CONTENT_PATH)),
        name="secondary-video",
    )
