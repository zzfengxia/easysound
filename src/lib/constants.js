import path from "node:path";

export const ROOT_DIR = process.cwd();
export const DATA_DIR = path.join(ROOT_DIR, "data");
export const STORAGE_DIR = path.join(ROOT_DIR, "storage");
export const UPLOAD_DIR = path.join(STORAGE_DIR, "uploads");
export const RESULT_DIR = path.join(STORAGE_DIR, "results");
export const TEMP_DIR = path.join(STORAGE_DIR, "tmp");
export const TASK_DIR = path.join(DATA_DIR, "tasks");

export const ALLOWED_EXTENSIONS = new Set([".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg"]);
export const MAX_FILE_SIZE_BYTES = 40 * 1024 * 1024;
export const MAX_DURATION_SECONDS = 8 * 60;
export const MIN_SAMPLE_RATE = 22_050;

export const INPUT_MODES = {
  VOCALS: "vocals_only",
  MIX: "with_backing_track"
};

export const TASK_STATUS = {
  QUEUED: "queued",
  PROCESSING: "processing",
  COMPLETED: "completed",
  FAILED: "failed"
};

export const DEFAULT_PROCESSING_STEPS = {
  noiseReduction: true,
  pitchCorrection: true,
  polish: true,
  sceneEnhancement: true
};
