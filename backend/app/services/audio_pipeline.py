from __future__ import annotations

import json
from pathlib import Path
from time import monotonic

from app.core.config import INPUT_MODES, MAX_DURATION_SECONDS, MIN_SAMPLE_RATE, RESULT_DIR, TEMP_DIR
from app.core.scene_presets import get_scene_preset
from app.services.audio_metadata import probe_audio

STAGE_PROGRESS = {
    "preflight": 10,
    "cleanup": 28,
    "separation": 45,
    "pitch_correction": 60,
    "polish": 74,
    "scene": 86,
    "mixdown": 93,
    "export": 98,
}


class AudioPipeline:
    def __init__(self, providers: dict, task_store) -> None:
        self.providers = providers
        self.task_store = task_store

    async def run(self, task) -> dict:
        temp_dir = TEMP_DIR / task.id
        temp_dir.mkdir(parents=True, exist_ok=True)
        started_at = monotonic()
        stage_started_at: dict[str, float] = {}

        async def mark_stage(stage: str, note: str) -> None:
            stage_started_at[stage] = monotonic()
            await self.task_store.update(task.id, status="processing", currentStage=stage, progress=STAGE_PROGRESS.get(stage, task.progress))
            await self.task_store.push_timeline(task.id, stage=stage, note=note)

        async def complete_stage(stage: str) -> None:
            current = self.task_store.get(task.id)
            durations = dict(current.stageDurationsMs)
            durations[stage] = int((monotonic() - stage_started_at.get(stage, monotonic())) * 1000)
            await self.task_store.update(task.id, stageDurationsMs=durations)

        await mark_stage("preflight", "Validating format, sample rate, and duration.")
        metadata = await probe_audio(Path(task.sourcePath))
        self._validate_metadata(metadata)
        await self.task_store.update(task.id, metadata=metadata)
        await complete_stage("preflight")

        normalized_path = temp_dir / "01-normalized.wav"
        await self.providers["audio"].normalize_input(Path(task.sourcePath), normalized_path)
        current_path = normalized_path
        backing_path = None

        if task.steps.noiseReduction:
            await mark_stage("cleanup", "Reducing broadband noise and harsh artifacts.")
            cleaned_path = temp_dir / "02-cleanup.wav"
            await self.providers["audio"].cleanup_noise(current_path, cleaned_path)
            current_path = cleaned_path
            await complete_stage("cleanup")

        if task.inputMode == INPUT_MODES["MIX"]:
            await mark_stage("separation", "Separating vocal focus from backing track.")
            separated = await self.providers["audio"].approximate_separate(current_path, temp_dir / "03-vocals.wav", temp_dir / "03-backing.wav")
            current_path = separated["vocalPath"]
            backing_path = separated["instrumentalPath"]
            await self.task_store.add_warning(task.id, separated["note"])
            await complete_stage("separation")

        if task.steps.pitchCorrection:
            await mark_stage("pitch_correction", "Tracking pitch, building targets, and rendering correction.")
            corrected_path = temp_dir / "04-pitch.wav"
            corrected = await self.providers["pitch"].correct_pitch(
                current_path,
                corrected_path,
                input_mode=task.inputMode,
                settings=task.pitch,
                temp_dir=temp_dir,
            )
            current_path = Path(corrected["outputPath"])
            if corrected.get("note"):
                await self.task_store.add_processing_note(task.id, corrected["note"])
            for warning in corrected.get("warnings", []):
                await self.task_store.add_warning(task.id, warning)
            if not corrected.get("applied") and corrected.get("note"):
                await self.task_store.add_warning(task.id, corrected["note"])
            await complete_stage("pitch_correction")

        if task.steps.polish:
            await mark_stage("polish", "Adding compression, EQ, and a gentle sheen.")
            polished_path = temp_dir / "05-polish.wav"
            await self.providers["audio"].polish_voice(current_path, polished_path)
            current_path = polished_path
            await complete_stage("polish")

        if task.steps.sceneEnhancement:
            preset = get_scene_preset(task.scenePreset)
            await mark_stage("scene", f"Applying {preset['name']} preset.")
            scene_result = await self.providers["audio"].apply_scene_preset(current_path, task.scenePreset, temp_dir / "06-scene.wav")
            current_path = scene_result["outputPath"]
            await self.task_store.add_processing_note(task.id, f"Scene preset: {scene_result['preset']['name']}")
            await complete_stage("scene")

        if task.inputMode == INPUT_MODES["MIX"] and backing_path is not None:
            await mark_stage("mixdown", "Mixing processed vocal back with backing track.")
            remixed_path = temp_dir / "07-mix.wav"
            await self.providers["audio"].remix(current_path, backing_path, remixed_path)
            current_path = remixed_path
            await complete_stage("mixdown")

        await mark_stage("export", "Encoding final deliverable.")
        result_path = RESULT_DIR / f"{task.id}.mp3"
        result_path.parent.mkdir(parents=True, exist_ok=True)
        await self.providers["audio"].export_final(current_path, result_path)
        await complete_stage("export")

        refreshed = self.task_store.get(task.id)
        summary = {
            "taskId": task.id,
            "totalDurationMs": int((monotonic() - started_at) * 1000),
            "metadata": metadata,
            "inputMode": task.inputMode,
            "steps": task.steps.model_dump(),
            "pitch": refreshed.pitch.model_dump() if refreshed else task.pitch.model_dump(),
            "warnings": refreshed.warnings if refreshed else [],
            "processingNotes": refreshed.processingNotes if refreshed else [],
            "preset": get_scene_preset(task.scenePreset),
        }
        (temp_dir / "processing-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

        return {
            "resultPath": str(result_path),
            "resultUrl": f"/media/results/{result_path.name}",
            "progress": 100,
        }

    def _validate_metadata(self, metadata: dict) -> None:
        if not metadata["durationSeconds"]:
            raise RuntimeError("Uploaded file does not contain a readable audio stream.")
        if metadata["durationSeconds"] > MAX_DURATION_SECONDS:
            raise RuntimeError(f"Audio is too long. Maximum supported length is {MAX_DURATION_SECONDS // 60} minutes.")
        if metadata["sampleRate"] < MIN_SAMPLE_RATE:
            raise RuntimeError(f"Sample rate too low. Minimum supported sample rate is {MIN_SAMPLE_RATE} Hz.")
