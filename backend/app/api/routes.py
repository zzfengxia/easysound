from __future__ import annotations

import logging
import re
import time

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from app.core.config import (
    DEFAULT_BACKING_MIX_AMOUNT,
    DEFAULT_LIGHT_REVERB_AMOUNT,
    DEFAULT_PITCH_MODE,
    DEFAULT_PITCH_STRENGTH,
    DEFAULT_PITCH_STYLE,
    DEFAULT_PROCESSING_STEPS,
    DEFAULT_REFERENCE_DURATION_RATIO_MAX,
    DEFAULT_REFERENCE_DURATION_RATIO_MIN,
    DEFAULT_SOFTEN_AMOUNT,
    DEFAULT_VOCAL_MIX_AMOUNT,
    INPUT_MODES,
    MAX_DURATION_SECONDS,
    MAX_FILE_SIZE_BYTES,
    PITCH_MODES,
    PITCH_STYLES,
    UPLOAD_DIR,
)
from app.core.scene_presets import list_scene_presets
from app.schemas import ConfigResponse, MixSettings, PitchSettings, PolishSettings, TaskEnvelope, TaskListEnvelope
from app.services.upload_payload import normalize_upload_payload

router = APIRouter()
logger = logging.getLogger(__name__)


def _sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name)


@router.get("/config", response_model=ConfigResponse)
async def get_config() -> ConfigResponse:
    return ConfigResponse(
        appName="EasySound",
        limits={"maxFileSizeBytes": MAX_FILE_SIZE_BYTES, "maxDurationSeconds": MAX_DURATION_SECONDS},
        inputModes=INPUT_MODES,
        defaultSteps=DEFAULT_PROCESSING_STEPS,
        defaultPolish=PolishSettings(
            softenAmount=DEFAULT_SOFTEN_AMOUNT,
            lightReverbAmount=DEFAULT_LIGHT_REVERB_AMOUNT,
        ),
        defaultMix=MixSettings(
            vocalMixAmount=DEFAULT_VOCAL_MIX_AMOUNT,
            backingMixAmount=DEFAULT_BACKING_MIX_AMOUNT,
        ),
        pitchModes=PITCH_MODES,
        pitchStyles=PITCH_STYLES,
        defaultPitch=PitchSettings(
            pitchMode=DEFAULT_PITCH_MODE,
            pitchStyle=DEFAULT_PITCH_STYLE,
            pitchStrength=DEFAULT_PITCH_STRENGTH,
            referenceDurationRatioMin=DEFAULT_REFERENCE_DURATION_RATIO_MIN,
            referenceDurationRatioMax=DEFAULT_REFERENCE_DURATION_RATIO_MAX,
        ),
        presets=list_scene_presets(),
    )


@router.get("/tasks", response_model=TaskListEnvelope)
async def list_tasks(request: Request) -> TaskListEnvelope:
    return TaskListEnvelope(tasks=request.app.state.task_store.list())


@router.delete("/tasks")
async def clear_tasks(request: Request) -> dict:
    task_store = request.app.state.task_store
    if task_store.has_active_tasks():
        raise HTTPException(status_code=409, detail="还有排队中或处理中的任务，暂时不能清空历史记录。")
    cleared = await task_store.clear_all()
    logger.info("历史任务已清空，共删除 %s 条任务记录。", cleared)
    return {"cleared": cleared}


@router.get("/tasks/{task_id}", response_model=TaskEnvelope)
async def get_task(task_id: str, request: Request) -> TaskEnvelope:
    task = request.app.state.task_store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskEnvelope(task=task)


@router.post("/tasks", status_code=202, response_model=TaskEnvelope)
async def create_task(
    request: Request,
    audio: UploadFile = File(...),
    midiFile: UploadFile | None = File(None),
    referenceVocalFile: UploadFile | None = File(None),
    inputMode: str = Form(INPUT_MODES["VOCALS"]),
    scenePreset: str = Form("concert"),
    noiseReduction: bool = Form(DEFAULT_PROCESSING_STEPS["noiseReduction"]),
    pitchCorrection: bool = Form(DEFAULT_PROCESSING_STEPS["pitchCorrection"]),
    softenVoice: bool = Form(DEFAULT_PROCESSING_STEPS["softenVoice"]),
    polish: bool = Form(DEFAULT_PROCESSING_STEPS["polish"]),
    sceneEnhancement: bool = Form(DEFAULT_PROCESSING_STEPS["sceneEnhancement"]),
    pitchMode: str = Form(DEFAULT_PITCH_MODE),
    pitchStyle: str = Form(DEFAULT_PITCH_STYLE),
    pitchStrength: int = Form(DEFAULT_PITCH_STRENGTH),
    softenAmount: int = Form(DEFAULT_SOFTEN_AMOUNT),
    lightReverbAmount: int = Form(DEFAULT_LIGHT_REVERB_AMOUNT),
    vocalMixAmount: int = Form(DEFAULT_VOCAL_MIX_AMOUNT),
    backingMixAmount: int = Form(DEFAULT_BACKING_MIX_AMOUNT),
    referenceDurationRatioMin: float = Form(DEFAULT_REFERENCE_DURATION_RATIO_MIN),
    referenceDurationRatioMax: float = Form(DEFAULT_REFERENCE_DURATION_RATIO_MAX),
) -> TaskEnvelope:
    logger.info("收到新任务请求，文件=%s，输入模式=%s，修音模式=%s，场景=%s", audio.filename, inputMode, pitchMode, scenePreset)
    payload, content, midi_content, reference_content = await normalize_upload_payload(
        audio,
        input_mode=inputMode,
        scene_preset=scenePreset,
        noise_reduction=noiseReduction,
        pitch_correction=pitchCorrection,
        soften_voice=softenVoice,
        polish=polish,
        scene_enhancement=sceneEnhancement,
        pitch_mode=pitchMode,
        pitch_style=pitchStyle,
        pitch_strength=pitchStrength,
        soften_amount=softenAmount,
        light_reverb_amount=lightReverbAmount,
        vocal_mix_amount=vocalMixAmount,
        backing_mix_amount=backingMixAmount,
        reference_duration_ratio_min=referenceDurationRatioMin,
        reference_duration_ratio_max=referenceDurationRatioMax,
        midi_file=midiFile,
        reference_vocal_file=referenceVocalFile,
    )

    stored_name = f"{int(time.time() * 1000)}-{_sanitize_filename(audio.filename or 'upload.wav')}"
    source_path = UPLOAD_DIR / stored_name
    source_path.write_bytes(content)

    pitch_settings = payload["pitch"]
    if midi_content and midiFile and midiFile.filename:
        midi_stored_name = f"{int(time.time() * 1000)}-{_sanitize_filename(midiFile.filename)}"
        midi_path = UPLOAD_DIR / midi_stored_name
        midi_path.write_bytes(midi_content)
        pitch_settings.midiStoredName = midi_stored_name
        pitch_settings.midiPath = str(midi_path)
        logger.info("任务附带 MIDI 参考文件，文件=%s", midiFile.filename)

    if reference_content and referenceVocalFile and referenceVocalFile.filename:
        reference_stored_name = f"{int(time.time() * 1000)}-{_sanitize_filename(referenceVocalFile.filename)}"
        reference_path = UPLOAD_DIR / reference_stored_name
        reference_path.write_bytes(reference_content)
        pitch_settings.referenceStoredName = reference_stored_name
        pitch_settings.referencePath = str(reference_path)
        logger.info("任务附带参考干声文件，文件=%s", referenceVocalFile.filename)

    task = await request.app.state.task_store.create(
        originalName=audio.filename or stored_name,
        storedName=stored_name,
        sourcePath=str(source_path),
        size=len(content),
        inputMode=payload["inputMode"],
        scenePreset=payload["scenePreset"],
        steps=payload["steps"],
        pitch=pitch_settings,
        polishSettings=payload["polishSettings"],
        mixSettings=payload["mixSettings"],
    )
    await request.app.state.job_queue.enqueue(task.id)
    logger.info("任务已入队，任务ID=%s，原始文件=%s", task.id, task.originalName)
    return TaskEnvelope(task=task)
