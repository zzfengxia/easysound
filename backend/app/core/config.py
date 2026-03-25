from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = ROOT_DIR / "data"
TASK_DIR = DATA_DIR / "tasks"
STORAGE_DIR = ROOT_DIR / "storage"
UPLOAD_DIR = STORAGE_DIR / "uploads"
RESULT_DIR = STORAGE_DIR / "results"
TEMP_DIR = STORAGE_DIR / "tmp"
PUBLIC_DIR = ROOT_DIR / "public"

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg"}
ALLOWED_MIDI_EXTENSIONS = {".mid", ".midi"}
MAX_FILE_SIZE_BYTES = 40 * 1024 * 1024
MAX_REFERENCE_FILE_SIZE_BYTES = 40 * 1024 * 1024
MAX_MIDI_FILE_SIZE_BYTES = 2 * 1024 * 1024
MAX_DURATION_SECONDS = 8 * 60
MIN_SAMPLE_RATE = 22_050

INPUT_MODES = {
    "VOCALS": "vocals_only",
    "MIX": "with_backing_track",
}

DEFAULT_PROCESSING_STEPS = {
    "noiseReduction": True,
    "pitchCorrection": True,
    "polish": True,
    "sceneEnhancement": True,
}

PITCH_MODES = {
    "AUTO_SCALE": "auto_scale",
    "MIDI_REFERENCE": "midi_reference",
    "REFERENCE_VOCAL": "reference_vocal",
}

PITCH_STYLES = {
    "NATURAL": "natural",
    "AUTOTUNE": "autotune",
}

DEFAULT_PITCH_MODE = PITCH_MODES["AUTO_SCALE"]
DEFAULT_PITCH_STYLE = PITCH_STYLES["NATURAL"]
DEFAULT_PITCH_STRENGTH = 55

FFMPEG_PATH = Path(r"D:\soft202502\ffmpeg-2025-04-23\bin\ffmpeg.exe")
FFPROBE_PATH = Path(r"D:\soft202502\ffmpeg-2025-04-23\bin\ffprobe.exe")
