from __future__ import annotations

import argparse
import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as api_router
from app.core.config import DATA_DIR, PUBLIC_DIR, RESULT_DIR, STORAGE_DIR, TASK_DIR, TEMP_DIR, UPLOAD_DIR
from app.providers.provider_factory import create_providers
from app.services.audio_pipeline import AudioPipeline
from app.services.job_queue import JobQueue
from app.services.task_store import TaskStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("EasySound 服务启动中，正在准备目录和任务队列。")
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
    logger.info("EasySound 服务已就绪，等待接收任务。")
    try:
        yield
    finally:
        logger.info("EasySound 服务正在关闭。")


app = FastAPI(title="EasySound", lifespan=lifespan)
app.include_router(api_router, prefix="/api")
app.mount("/media/results", StaticFiles(directory=RESULT_DIR), name="results")
app.mount("/media/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")


@app.get("/")
async def index():
    return FileResponse(PUBLIC_DIR / "index.html")


@app.get("/history")
async def history_page():
    return FileResponse(PUBLIC_DIR / "history.html")


@app.get("/history/task/{task_id}")
async def history_detail_page(task_id: str):
    return FileResponse(PUBLIC_DIR / "history-detail.html")


@app.get("/{file_path:path}")
async def public_files(file_path: str):
    target = PUBLIC_DIR / file_path
    if target.is_file():
        return FileResponse(target)
    return FileResponse(PUBLIC_DIR / "index.html")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description="easysound RESTful API server"
    )
    parser.add_argument("--host", type=str, default="0.0.0.0", help="host name")
    parser.add_argument("--port", type=int, default=3001, help="port number")
    parser.add_argument("--workers", type=int, default=1, help="workers")
    parser.add_argument("--backlog", type=int, default=2048, help="backlog")

    args = parser.parse_args()

    uvicorn.run(app='app.main:app', host=args.host, port=args.port, log_level="info", workers=args.workers,
                backlog=args.backlog)
