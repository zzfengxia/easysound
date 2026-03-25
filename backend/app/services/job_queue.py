from __future__ import annotations

import asyncio


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

    async def start(self) -> None:
        if self.worker_task is None:
            self.worker_task = asyncio.create_task(self._worker())

    async def enqueue(self, task_id: str) -> None:
        await self.queue.put(task_id)

    async def _worker(self) -> None:
        while True:
            task_id = await self.queue.get()
            task = self.task_store.get(task_id)
            if task is None or task.status != "queued":
                self.queue.task_done()
                continue
            try:
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
            except Exception as exc:
                await self.task_store.update(task_id, status="failed", currentStage="failed", error=str(exc))
                await self.task_store.push_timeline(task_id, stage="failed", note=str(exc))
            finally:
                self.queue.task_done()
