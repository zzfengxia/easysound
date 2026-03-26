from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from pathlib import Path
from time import monotonic

from app.core.config import INPUT_MODES, MAX_DURATION_SECONDS, MIN_SAMPLE_RATE, RESULT_DIR, TEMP_DIR
from app.core.scene_presets import get_scene_preset
from app.schemas import PitchSettings
from app.services.audio_metadata import probe_audio

logger = logging.getLogger(__name__)

STAGE_PROGRESS = {
    "preflight": 10,
    "cleanup": 22,
    "separation": 36,
    "pitch_correction": 52,
    "soften": 64,
    "polish": 76,
    "scene": 86,
    "mixdown": 91,
    "loudness": 96,
    "export": 99,
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
        logger.info("任务进入处理流水线，任务ID=%s，临时目录=%s", task.id, temp_dir)

        async def mark_stage(stage: str, note: str) -> None:
            stage_started_at[stage] = monotonic()
            logger.info("任务阶段开始，任务ID=%s，阶段=%s，说明=%s", task.id, stage, note)
            await self.task_store.update(task.id, status="processing", currentStage=stage, progress=STAGE_PROGRESS.get(stage, task.progress))
            await self.task_store.push_timeline(task.id, stage=stage, note=note)

        async def complete_stage(stage: str) -> None:
            current = self.task_store.get(task.id)
            durations = dict(current.stageDurationsMs)
            durations[stage] = int((monotonic() - stage_started_at.get(stage, monotonic())) * 1000)
            await self.task_store.update(task.id, stageDurationsMs=durations)
            logger.info("任务阶段完成，任务ID=%s，阶段=%s，耗时=%sms", task.id, stage, durations[stage])

        await mark_stage("preflight", "正在校验音频格式、采样率和时长。")
        metadata = await probe_audio(Path(task.sourcePath))
        logger.info("音频预检结果，任务ID=%s，时长=%.2fs，采样率=%sHz，声道=%s", task.id, metadata["durationSeconds"], metadata["sampleRate"], metadata["channels"])
        self._validate_metadata(metadata)
        await self.task_store.update(task.id, metadata=metadata)
        await complete_stage("preflight")

        normalized_path = temp_dir / "01-normalized.wav"
        await self.providers["audio"].normalize_input(Path(task.sourcePath), normalized_path)
        current_path = normalized_path
        backing_path = None

        if task.steps.noiseReduction:
            await mark_stage("cleanup", "正在做降噪、去齿音和基础清理，并增强首尾无人声区的抑噪。")
            cleaned_path = temp_dir / "02-cleanup.wav"
            await self.providers["audio"].cleanup_noise(current_path, cleaned_path)
            current_path = cleaned_path
            await complete_stage("cleanup")

        if task.inputMode == INPUT_MODES["MIX"]:
            await mark_stage("separation", "正在分离人声和伴奏。")
            separated = await self.providers["audio"].approximate_separate(current_path, temp_dir / "03-vocals.wav", temp_dir / "03-backing.wav")
            current_path = separated["vocalPath"]
            backing_path = separated["instrumentalPath"]
            await self.task_store.add_warning(task.id, separated["note"])
            logger.info("人声分离完成，任务ID=%s，提示=%s，分离输出采用中性电平。", task.id, separated["note"])
            await complete_stage("separation")

        if task.steps.pitchCorrection:
            await mark_stage("pitch_correction", "正在跟踪音高并渲染修音结果。")
            corrected_path = temp_dir / "04-pitch.wav"
            corrected = await self.providers["pitch"].correct_pitch(
                current_path,
                corrected_path,
                input_mode=task.inputMode,
                settings=task.pitch,
                temp_dir=temp_dir,
            )
            current_path = Path(corrected["outputPath"])
            pitch_payload = task.pitch.model_dump()
            pitch_payload.update({
                "effectivePitchMode": corrected.get("effectiveMode"),
                "fallbackReason": corrected.get("fallbackReason"),
                "fallbackCategory": corrected.get("fallbackCategory"),
            })
            updated_pitch = PitchSettings.model_validate(pitch_payload)
            await self.task_store.update(task.id, pitch=updated_pitch)
            task = self.task_store.get(task.id) or task
            if corrected.get("note"):
                await self.task_store.add_processing_note(task.id, corrected["note"])
                logger.info("修音说明，任务ID=%s，内容=%s", task.id, corrected["note"])
            if corrected.get("fallbackReason"):
                await self.task_store.add_warning(task.id, corrected["fallbackReason"])
                logger.warning(
                    "修音模式发生回退，任务ID=%s，请求模式=%s，实际模式=%s，原因=%s",
                    task.id,
                    corrected.get("requestedMode"),
                    corrected.get("effectiveMode"),
                    corrected.get("fallbackReason"),
                )
            for warning in corrected.get("warnings", []):
                if warning != corrected.get("fallbackReason"):
                    await self.task_store.add_warning(task.id, warning)
                logger.warning("修音警告，任务ID=%s，内容=%s", task.id, warning)
            if not corrected.get("applied") and corrected.get("note"):
                await self.task_store.add_warning(task.id, corrected["note"])
            await complete_stage("pitch_correction")

        if task.steps.softenVoice:
            await mark_stage("soften", f"正在柔化刺耳感，让人声更顺更柔和。当前柔和程度 {task.polishSettings.softenAmount}。")
            softened_path = temp_dir / "05-soften.wav"
            await self.providers["audio"].soften_voice(current_path, softened_path, amount=task.polishSettings.softenAmount)
            current_path = softened_path
            await complete_stage("soften")

        if task.steps.polish:
            await mark_stage("polish", f"正在做人声润色和增强基础轻混响。当前轻混响程度 {task.polishSettings.lightReverbAmount}。")
            polished_path = temp_dir / "06-polish.wav"
            await self.providers["audio"].polish_voice(current_path, polished_path, light_reverb_amount=task.polishSettings.lightReverbAmount)
            current_path = polished_path
            await complete_stage("polish")

        if task.steps.sceneEnhancement:
            preset = get_scene_preset(task.scenePreset)
            await mark_stage("scene", f"正在应用场景预设：{preset['name']}。")
            scene_result = await self.providers["audio"].apply_scene_preset(current_path, task.scenePreset, temp_dir / "07-scene.wav")
            current_path = scene_result["outputPath"]
            await self.task_store.add_processing_note(task.id, f"Scene preset: {scene_result['preset']['name']}")
            logger.info("场景效果应用完成，任务ID=%s，场景=%s", task.id, scene_result["preset"]["name"])
            await complete_stage("scene")

        if task.inputMode == INPUT_MODES["MIX"] and backing_path is not None:
            await mark_stage("mixdown", "正在将处理后的人声回混到伴奏中。")
            remixed_path = temp_dir / "08-mix.wav"
            logger.info(
                "开始回混，任务ID=%s，输入模式=%s，人声参数=%s，伴奏参数=%s",
                task.id,
                task.inputMode,
                task.mixSettings.vocalMixAmount,
                task.mixSettings.backingMixAmount,
            )
            remixed = await self.providers["audio"].remix(
                current_path,
                backing_path,
                remixed_path,
                vocal_mix_amount=task.mixSettings.vocalMixAmount,
                backing_mix_amount=task.mixSettings.backingMixAmount,
            )
            current_path = Path(remixed["outputPath"])
            logger.info(
                "回混完成，任务ID=%s，人声倍率=%.3f，伴奏倍率=%.3f",
                task.id,
                remixed["vocalGain"],
                remixed["backingGain"],
            )
            await self.task_store.add_processing_note(
                task.id,
                f"Mix balance: vocal {task.mixSettings.vocalMixAmount} ({remixed['vocalGain']:.3f}x), backing {task.mixSettings.backingMixAmount} ({remixed['backingGain']:.3f}x)",
            )
            await complete_stage("mixdown")

        await mark_stage("loudness", "正在统一整首音量，并再做一层首尾无人声区的收口抑噪。")
        loudness_path = temp_dir / "09-loudness.wav"
        await self.providers["audio"].normalize_loudness(current_path, loudness_path)
        current_path = loudness_path
        logger.info("响度统一完成，任务ID=%s，策略=稳妥自然（轻压缩 + 动态平滑 + loudnorm + 首尾收口抑噪 + limiter）", task.id)
        await complete_stage("loudness")

        await mark_stage("export", "正在导出最终成品音频。")
        result_path = RESULT_DIR / self._build_result_filename(task.originalName)
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
            "polishSettings": refreshed.polishSettings.model_dump() if refreshed else task.polishSettings.model_dump(),
            "mixSettings": refreshed.mixSettings.model_dump() if refreshed else task.mixSettings.model_dump(),
            "warnings": refreshed.warnings if refreshed else [],
            "processingNotes": refreshed.processingNotes if refreshed else [],
            "preset": get_scene_preset(task.scenePreset),
        }
        (temp_dir / "processing-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("任务处理摘要已写入，任务ID=%s，总耗时=%sms", task.id, summary["totalDurationMs"])

        return {
            "resultPath": str(result_path),
            "resultUrl": f"/media/results/{result_path.name}",
            "progress": 100,
        }

    def _validate_metadata(self, metadata: dict) -> None:
        if not metadata["durationSeconds"]:
            raise RuntimeError("上传的文件中没有可读取的音频流。")
        if metadata["durationSeconds"] > MAX_DURATION_SECONDS:
            raise RuntimeError(f"音频时长过长，当前最多支持 {MAX_DURATION_SECONDS // 60} 分钟。")
        if metadata["sampleRate"] < MIN_SAMPLE_RATE:
            raise RuntimeError(f"采样率过低，当前最低支持 {MIN_SAMPLE_RATE} Hz。")

    @staticmethod
    def _build_result_filename(original_name: str) -> str:
        source_name = original_name or "audio"
        stem = Path(source_name).stem.strip() or "audio"
        safe_stem = re.sub(r'[\\/:*?"<>|]+', "_", stem).strip(" .") or "audio"
        timestamp = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")
        return f"{safe_stem}-处理-{timestamp}.mp3"

