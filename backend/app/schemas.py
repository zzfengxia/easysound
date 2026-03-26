from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


TaskStatus = Literal["queued", "processing", "completed", "failed"]
InputMode = Literal["vocals_only", "with_backing_track"]
PitchMode = Literal["auto_scale", "midi_reference", "reference_vocal"]
PitchStyle = Literal["natural", "autotune"]
PitchFallbackCategory = Literal["duration_ratio", "low_coverage", "unstable_reference", "octave_jump", "missing_reference", "midi_parse"]


class ProcessingSteps(BaseModel):
    noiseReduction: bool = True
    pitchCorrection: bool = True
    softenVoice: bool = True
    polish: bool = True
    sceneEnhancement: bool = True


class PitchSettings(BaseModel):
    pitchMode: PitchMode = "auto_scale"
    pitchStyle: PitchStyle = "natural"
    pitchStrength: int = 55
    referenceDurationRatioMin: float = 0.6
    referenceDurationRatioMax: float = 1.67
    effectivePitchMode: PitchMode | None = None
    fallbackReason: str | None = None
    fallbackCategory: PitchFallbackCategory | None = None
    midiOriginalName: str | None = None
    midiStoredName: str | None = None
    midiPath: str | None = None
    referenceOriginalName: str | None = None
    referenceStoredName: str | None = None
    referencePath: str | None = None


class PolishSettings(BaseModel):
    softenAmount: int = 55
    lightReverbAmount: int = 45


class TimelineEntry(BaseModel):
    stage: str
    at: str
    note: str


class AudioMetadata(BaseModel):
    durationSeconds: float
    sampleRate: int
    channels: int
    codec: str
    formatName: str
    bitRate: int


class TaskRecord(BaseModel):
    id: str
    originalName: str
    storedName: str
    sourcePath: str
    size: int
    inputMode: InputMode
    scenePreset: str
    steps: ProcessingSteps
    pitch: PitchSettings = Field(default_factory=PitchSettings)
    polishSettings: PolishSettings = Field(default_factory=PolishSettings)
    status: TaskStatus
    progress: int = 0
    currentStage: str = "queued"
    resultPath: str | None = None
    resultUrl: str | None = None
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)
    timeline: list[TimelineEntry] = Field(default_factory=list)
    stageDurationsMs: dict[str, int] = Field(default_factory=dict)
    metadata: AudioMetadata | None = None
    processingNotes: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str


class ConfigResponse(BaseModel):
    appName: str
    limits: dict[str, int]
    inputModes: dict[str, str]
    defaultSteps: ProcessingSteps
    defaultPolish: PolishSettings
    pitchModes: dict[str, str]
    pitchStyles: dict[str, str]
    defaultPitch: PitchSettings
    presets: list[dict]


class TaskEnvelope(BaseModel):
    task: TaskRecord


class TaskListEnvelope(BaseModel):
    tasks: list[TaskRecord]

