from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


class JobQueue:
    def __init__(self, task_store, pipeline) -> None:
        self.task_store = task_store
        self.pipeline = pipeline
        self.queue: asyncio.Queue[str] = asyncio.Queue()
        self.worker_task: asyncio.Task | None = None

    async def init(self) -> None:
        for task in self.task_store.list():
            if task.status == "queued":
                await self.queue.put(task.id)
                logger.info("检测到历史排队任务，已重新入队，任务ID=%s", task.id)

    async def start(self) -> None:
        if self.worker_task is None:
            self.worker_task = asyncio.create_task(self._worker())
            logger.info("后台任务消费者已启动。")

    async def enqueue(self, task_id: str) -> None:
        await self.queue.put(task_id)
        logger.info("任务已加入处理队列，任务ID=%s", task_id)

    async def _worker(self) -> None:
        while True:
            task_id = await self.queue.get()
            task = self.task_store.get(task_id)
            if task is None or task.status != "queued":
                logger.warning("跳过无效任务或非排队任务，任务ID=%s", task_id)
                self.queue.task_done()
                continue
            try:
                logger.info("开始处理任务，任务ID=%s，文件=%s", task.id, task.originalName)
                result = await self.pipeline.run(task)
                await self.task_store.update(
                    task_id,
                    status="completed",
                    currentStage="completed",
                    progress=result["progress"],
                    resultPath=result["resultPath"],
                    resultUrl=result["resultUrl"],
                    error=None,
                )
                await self.task_store.push_timeline(task_id, stage="completed", note="Processing finished successfully.")
                logger.info("任务处理完成，任务ID=%s，结果文件=%s", task_id, result["resultPath"])
            except Exception as exc:
                current = self.task_store.get(task_id)
                failure_stage = current.currentStage if current else "failed"
                failure_progress = current.progress if current else 0
                message = self._format_error(exc)
                await self.task_store.update(
                    task_id,
                    status="failed",
                    currentStage=failure_stage,
                    progress=failure_progress,
                    error=message,
                )
                await self.task_store.push_timeline(task_id, stage="failed", note=message)
                logger.exception("任务处理失败，任务ID=%s，阶段=%s，原因=%s", task_id, failure_stage, message)
            finally:
                self.queue.task_done()

    @staticmethod
    def _format_error(exc: Exception) -> str:
        message = str(exc).strip()
        if message:
            return message
        return f"{exc.__class__.__name__}: 处理失败，但没有返回更详细的错误信息。"
