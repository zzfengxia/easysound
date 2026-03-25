from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.core.config import DATA_DIR, PUBLIC_DIR, RESULT_DIR, STORAGE_DIR, TASK_DIR, TEMP_DIR, UPLOAD_DIR
from app.providers.provider_factory import create_providers
from app.services.audio_pipeline import AudioPipeline
from app.services.job_queue import JobQueue
from app.services.task_store import TaskStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    for directory in (DATA_DIR, TASK_DIR, STORAGE_DIR, UPLOAD_DIR, RESULT_DIR, TEMP_DIR):
        directory.mkdir(parents=True, exist_ok=True)

    task_store = TaskStore()
    await task_store.init()
    providers = create_providers()
    pipeline = AudioPipeline(providers=providers, task_store=task_store)
    job_queue = JobQueue(task_store=task_store, pipeline=pipeline)
    await job_queue.init()
    await job_queue.start()

    app.state.task_store = task_store
    app.state.job_queue = job_queue
    app.state.providers = providers
    yield


app = FastAPI(title="EasySound", lifespan=lifespan)
app.include_router(api_router, prefix="/api")
app.mount("/media/results", StaticFiles(directory=RESULT_DIR), name="results")


@app.get("/")
async def index():
    return FileResponse(PUBLIC_DIR / "index.html")


@app.get("/{file_path:path}")
async def public_files(file_path: str):
    target = PUBLIC_DIR / file_path
    if target.is_file():
        return FileResponse(target)
    return FileResponse(PUBLIC_DIR / "index.html")
