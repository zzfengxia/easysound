import path from "node:path";
import { DEFAULT_SCENE_PRESET, SCENE_PRESETS } from "../config/scene-presets.js";
import {
  ALLOWED_EXTENSIONS,
  DEFAULT_PROCESSING_STEPS,
  INPUT_MODES,
  MAX_FILE_SIZE_BYTES
} from "./constants.js";

export function normalizeTaskInput(formData) {
  const inputMode = formData.get("inputMode") || INPUT_MODES.VOCALS;
  const scenePreset = formData.get("scenePreset") || DEFAULT_SCENE_PRESET;
  const file = formData.get("audio");

  if (!(file instanceof File)) {
    throw new Error("Audio file is required.");
  }

  if (!Object.values(INPUT_MODES).includes(inputMode)) {
    throw new Error("Invalid input mode.");
  }

  if (!SCENE_PRESETS[scenePreset]) {
    throw new Error("Invalid scene preset.");
  }

  const extension = path.extname(file.name || "").toLowerCase();
  if (!ALLOWED_EXTENSIONS.has(extension)) {
    throw new Error(`Unsupported file type: ${extension || "unknown"}.`);
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    throw new Error(`File too large. Maximum supported size is ${Math.round(MAX_FILE_SIZE_BYTES / 1024 / 1024)} MB.`);
  }

  return {
    inputMode,
    scenePreset,
    steps: {
      noiseReduction: readBoolean(formData.get("noiseReduction"), DEFAULT_PROCESSING_STEPS.noiseReduction),
      pitchCorrection: readBoolean(formData.get("pitchCorrection"), DEFAULT_PROCESSING_STEPS.pitchCorrection),
      polish: readBoolean(formData.get("polish"), DEFAULT_PROCESSING_STEPS.polish),
      sceneEnhancement: readBoolean(formData.get("sceneEnhancement"), DEFAULT_PROCESSING_STEPS.sceneEnhancement)
    },
    file
  };
}

function readBoolean(value, fallback) {
  if (value === null) {
    return fallback;
  }

  return value === "true" || value === "on" || value === true;
}
