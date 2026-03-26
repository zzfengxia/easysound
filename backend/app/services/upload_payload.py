from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile

from app.core.config import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIDI_EXTENSIONS,
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
    MAX_FILE_SIZE_BYTES,
    MAX_MIDI_FILE_SIZE_BYTES,
    MAX_REFERENCE_FILE_SIZE_BYTES,
    PITCH_MODES,
    PITCH_STYLES,
)
from app.core.scene_presets import DEFAULT_SCENE_PRESET, SCENE_PRESETS
from app.schemas import MixSettings, PitchSettings, PolishSettings, ProcessingSteps


async def normalize_upload_payload(
    audio: UploadFile,
    input_mode: str = INPUT_MODES["VOCALS"],
    scene_preset: str = DEFAULT_SCENE_PRESET,
    noise_reduction: bool = DEFAULT_PROCESSING_STEPS["noiseReduction"],
    pitch_correction: bool = DEFAULT_PROCESSING_STEPS["pitchCorrection"],
    soften_voice: bool = DEFAULT_PROCESSING_STEPS["softenVoice"],
    polish: bool = DEFAULT_PROCESSING_STEPS["polish"],
    scene_enhancement: bool = DEFAULT_PROCESSING_STEPS["sceneEnhancement"],
    pitch_mode: str = DEFAULT_PITCH_MODE,
    pitch_style: str = DEFAULT_PITCH_STYLE,
    pitch_strength: int = DEFAULT_PITCH_STRENGTH,
    soften_amount: int = DEFAULT_SOFTEN_AMOUNT,
    light_reverb_amount: int = DEFAULT_LIGHT_REVERB_AMOUNT,
    vocal_mix_amount: int = DEFAULT_VOCAL_MIX_AMOUNT,
    backing_mix_amount: int = DEFAULT_BACKING_MIX_AMOUNT,
    reference_duration_ratio_min: float = DEFAULT_REFERENCE_DURATION_RATIO_MIN,
    reference_duration_ratio_max: float = DEFAULT_REFERENCE_DURATION_RATIO_MAX,
    midi_file: UploadFile | None = None,
    reference_vocal_file: UploadFile | None = None,
) -> tuple[dict, bytes, bytes | None, bytes | None]:
    if input_mode not in INPUT_MODES.values():
        raise HTTPException(status_code=400, detail="Invalid input mode.")
    if scene_preset not in SCENE_PRESETS:
        raise HTTPException(status_code=400, detail="Invalid scene preset.")
    if pitch_mode not in PITCH_MODES.values():
        raise HTTPException(status_code=400, detail="Invalid pitch mode.")
    if pitch_style not in PITCH_STYLES.values():
        raise HTTPException(status_code=400, detail="Invalid pitch style.")
    if not 0 <= int(pitch_strength) <= 100:
        raise HTTPException(status_code=400, detail="Pitch strength must be between 0 and 100.")
    if not 0 <= int(soften_amount) <= 100:
        raise HTTPException(status_code=400, detail="Soften amount must be between 0 and 100.")
    if not 0 <= int(light_reverb_amount) <= 100:
        raise HTTPException(status_code=400, detail="Light reverb amount must be between 0 and 100.")
    if not 0 <= int(vocal_mix_amount) <= 100:
        raise HTTPException(status_code=400, detail="Vocal mix amount must be between 0 and 100.")
    if not 0 <= int(backing_mix_amount) <= 100:
        raise HTTPException(status_code=400, detail="Backing mix amount must be between 0 and 100.")

    reference_duration_ratio_min = float(reference_duration_ratio_min)
    reference_duration_ratio_max = float(reference_duration_ratio_max)
    if reference_duration_ratio_min <= 0 or reference_duration_ratio_max <= 0:
        raise HTTPException(status_code=400, detail="Reference duration ratio must be greater than 0.")
    if reference_duration_ratio_min >= reference_duration_ratio_max:
        raise HTTPException(status_code=400, detail="Reference duration ratio minimum must be smaller than maximum.")

    suffix = Path(audio.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {suffix or 'unknown' }.")

    content = await audio.read()
    if not content:
        raise HTTPException(status_code=400, detail="Audio file is required.")
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum supported size is {MAX_FILE_SIZE_BYTES // 1024 // 1024} MB.")

    midi_content = None
    midi_settings = {
        "midiOriginalName": None,
        "midiStoredName": None,
        "midiPath": None,
    }
    if midi_file and midi_file.filename:
        midi_suffix = Path(midi_file.filename).suffix.lower()
        if midi_suffix not in ALLOWED_MIDI_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Unsupported MIDI file type.")
        midi_content = await midi_file.read()
        if len(midi_content) > MAX_MIDI_FILE_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="MIDI file too large.")
        midi_settings["midiOriginalName"] = midi_file.filename

    reference_content = None
    reference_settings = {
        "referenceOriginalName": None,
        "referenceStoredName": None,
        "referencePath": None,
    }
    if reference_vocal_file and reference_vocal_file.filename:
        reference_suffix = Path(reference_vocal_file.filename).suffix.lower()
        if reference_suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Unsupported reference vocal file type.")
        reference_content = await reference_vocal_file.read()
        if len(reference_content) > MAX_REFERENCE_FILE_SIZE_BYTES:
            raise HTTPException(status_code=400, detail="Reference vocal file too large.")
        reference_settings["referenceOriginalName"] = reference_vocal_file.filename

    if pitch_mode == PITCH_MODES["MIDI_REFERENCE"] and not midi_settings["midiOriginalName"]:
        raise HTTPException(status_code=400, detail="MIDI reference mode requires a MIDI file.")
    if pitch_mode == PITCH_MODES["REFERENCE_VOCAL"] and not reference_settings["referenceOriginalName"]:
        raise HTTPException(status_code=400, detail="Reference vocal mode requires a reference vocal file.")

    payload = {
        "inputMode": input_mode,
        "scenePreset": scene_preset,
        "steps": ProcessingSteps(
            noiseReduction=noise_reduction,
            pitchCorrection=pitch_correction,
            softenVoice=soften_voice,
            polish=polish,
            sceneEnhancement=scene_enhancement,
        ),
        "pitch": PitchSettings(
            pitchMode=pitch_mode,
            pitchStyle=pitch_style,
            pitchStrength=int(pitch_strength),
            referenceDurationRatioMin=reference_duration_ratio_min,
            referenceDurationRatioMax=reference_duration_ratio_max,
            **midi_settings,
            **reference_settings,
        ),
        "polishSettings": PolishSettings(
            softenAmount=int(soften_amount),
            lightReverbAmount=int(light_reverb_amount),
        ),
        "mixSettings": MixSettings(
            vocalMixAmount=int(vocal_mix_amount),
            backingMixAmount=int(backing_mix_amount),
        ),
    }
    return payload, content, midi_content, reference_content
