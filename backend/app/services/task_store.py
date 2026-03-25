from __future__ import annotations

import json
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import TASK_DIR, TEMP_DIR
from app.schemas import PitchSettings, TaskRecord


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class TaskStore:
    def __init__(self) -> None:
        self._tasks: dict[str, TaskRecord] = {}

    async def init(self) -> None:
        TASK_DIR.mkdir(parents=True, exist_ok=True)
        for file_path in TASK_DIR.glob("*.json"):
            data = json.loads(file_path.read_text(encoding="utf-8"))
            if "pitch" not in data:
                data["pitch"] = PitchSettings().model_dump()
            else:
                pitch_data = PitchSettings.model_validate(data["pitch"])
                data["pitch"] = pitch_data.model_dump()
            task = TaskRecord.model_validate(data)
            if task.status == "processing":
                task.status = "queued"
                task.currentStage = "queued"
                task.progress = 0
                task.timeline.append({"stage": "queued", "at": utc_now(), "note": "Server restart detected. Task re-queued automatically."})
                self._save(task)
            self._tasks[task.id] = task

    def list(self) -> list[TaskRecord]:
        return sorted(self._tasks.values(), key=lambda task: task.createdAt, reverse=True)

    def get(self, task_id: str) -> TaskRecord | None:
        return self._tasks.get(task_id)

    def has_active_tasks(self) -> bool:
        return any(task.status in {"queued", "processing"} for task in self._tasks.values())

    async def create(self, **payload) -> TaskRecord:
        now = utc_now()
        task = TaskRecord.model_validate(
            {
                "id": str(uuid.uuid4()),
                **payload,
                "status": "queued",
                "progress": 0,
                "currentStage": "queued",
                "resultPath": None,
                "resultUrl": None,
                "error": None,
                "warnings": [],
                "timeline": [{"stage": "queued", "at": now, "note": "Upload accepted and queued."}],
                "stageDurationsMs": {},
                "metadata": None,
                "processingNotes": [],
                "createdAt": now,
                "updatedAt": now,
            }
        )
        self._tasks[task.id] = task
        self._save(task)
        return task

    async def update(self, task_id: str, **patch) -> TaskRecord:
        current = self.get(task_id)
        if current is None:
            raise KeyError(f"Task {task_id} not found")
        data = current.model_dump()
        data.update(patch)
        data["updatedAt"] = utc_now()
        task = TaskRecord.model_validate(data)
        self._tasks[task.id] = task
        self._save(task)
        return task

    async def push_timeline(self, task_id: str, stage: str, note: str) -> TaskRecord:
        current = self.get(task_id)
        if current is None:
            raise KeyError(f"Task {task_id} not found")
        timeline = [*current.timeline, {"stage": stage, "at": utc_now(), "note": note}]
        return await self.update(task_id, timeline=timeline)

    async def add_warning(self, task_id: str, warning: str) -> TaskRecord:
        current = self.get(task_id)
        if current is None:
            raise KeyError(f"Task {task_id} not found")
        return await self.update(task_id, warnings=[*current.warnings, warning])

    async def add_processing_note(self, task_id: str, note: str) -> TaskRecord:
        current = self.get(task_id)
        if current is None:
            raise KeyError(f"Task {task_id} not found")
        return await self.update(task_id, processingNotes=[*current.processingNotes, note])

    async def clear_all(self) -> int:
        tasks = list(self._tasks.values())
        count = len(tasks)
        for task in tasks:
            self._delete_file(Path(task.sourcePath))
            self._delete_file(Path(task.resultPath) if task.resultPath else None)
            self._delete_file(Path(task.pitch.midiPath) if task.pitch.midiPath else None)
            self._delete_file(Path(task.pitch.referencePath) if task.pitch.referencePath else None)
            self._delete_file(TASK_DIR / f"{task.id}.json")
            temp_dir = TEMP_DIR / task.id
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        self._tasks.clear()
        return count

    def _save(self, task: TaskRecord) -> None:
        path = TASK_DIR / f"{task.id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(task.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _delete_file(path: Path | None) -> None:
        if path is None:
            return
        try:
            if path.exists() and path.is_file():
                path.unlink()
        except OSError:
            pass
