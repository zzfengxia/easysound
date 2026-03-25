import fs from "node:fs/promises";
import path from "node:path";
import { getScenePreset } from "../config/scene-presets.js";
import { INPUT_MODES, MAX_DURATION_SECONDS, MIN_SAMPLE_RATE, RESULT_DIR, TASK_STATUS, TEMP_DIR } from "./constants.js";
import { probeAudio } from "./audio-metadata.js";
import { ensureParentDir } from "./fs-utils.js";

const STAGE_PROGRESS = {
  preflight: 10,
  cleanup: 28,
  separation: 45,
  pitch_correction: 60,
  polish: 74,
  scene: 86,
  mixdown: 93,
  export: 98
};

export class AudioPipeline {
  constructor({ providers, taskStore }) {
    this.providers = providers;
    this.taskStore = taskStore;
  }

  async run(task) {
    const tempDir = path.join(TEMP_DIR, task.id);
    await fs.mkdir(tempDir, { recursive: true });

    const startedAt = Date.now();
    const stageStartedAt = new Map();

    const markStage = async (stage, note) => {
      stageStartedAt.set(stage, Date.now());
      await this.taskStore.update(task.id, {
        status: TASK_STATUS.PROCESSING,
        currentStage: stage,
        progress: STAGE_PROGRESS[stage] ?? task.progress
      });
      await this.taskStore.pushTimeline(task.id, { stage, note });
    };

    const completeStage = async (stage) => {
      const current = this.taskStore.get(task.id);
      const duration = Date.now() - (stageStartedAt.get(stage) ?? Date.now());
      await this.taskStore.update(task.id, {
        stageDurationsMs: {
          ...current.stageDurationsMs,
          [stage]: duration
        }
      });
    };

    await markStage("preflight", "Validating format, sample rate, and duration.");
    const metadata = await probeAudio(task.sourcePath);
    this.#validateMetadata(metadata);
    await this.taskStore.update(task.id, { metadata });
    await completeStage("preflight");

    const normalizedPath = path.join(tempDir, "01-normalized.wav");
    await this.providers.audio.normalizeInput(task.sourcePath, normalizedPath);
    let currentPath = normalizedPath;

    if (task.steps.noiseReduction) {
      await markStage("cleanup", "Reducing broadband noise and harsh artifacts.");
      const cleanedPath = path.join(tempDir, "02-cleanup.wav");
      await this.providers.audio.cleanupNoise(currentPath, cleanedPath);
      currentPath = cleanedPath;
      await completeStage("cleanup");
    }

    let backingPath = null;

    if (task.inputMode === INPUT_MODES.MIX) {
      await markStage("separation", "Separating vocal focus from backing track.");
      const separated = await this.providers.audio.approximateSeparate(
        currentPath,
        path.join(tempDir, "03-vocals.wav"),
        path.join(tempDir, "03-backing.wav")
      );
      currentPath = separated.vocalPath;
      backingPath = separated.instrumentalPath;
      await this.taskStore.addWarning(task.id, separated.note);
      await completeStage("separation");
    }

    if (task.steps.pitchCorrection) {
      await markStage("pitch_correction", "Applying natural pitch-correction provider.");
      const corrected = await this.providers.pitch.correctPitch(currentPath, path.join(tempDir, "04-pitch.wav"), {
        inputMode: task.inputMode
      });
      currentPath = corrected.outputPath;
      if (!corrected.applied && corrected.note) {
        await this.taskStore.addWarning(task.id, corrected.note);
      }
      await completeStage("pitch_correction");
    }

    if (task.steps.polish) {
      await markStage("polish", "Adding compression, EQ, and a gentle sheen.");
      const polishedPath = path.join(tempDir, "05-polish.wav");
      await this.providers.audio.polishVoice(currentPath, polishedPath);
      currentPath = polishedPath;
      await completeStage("polish");
    }

    if (task.steps.sceneEnhancement) {
      await markStage("scene", `Applying ${getScenePreset(task.scenePreset).name} preset.`);
      const sceneResult = await this.providers.audio.applyScenePreset(
        currentPath,
        task.scenePreset,
        path.join(tempDir, "06-scene.wav")
      );
      currentPath = sceneResult.outputPath;
      await this.taskStore.addProcessingNote(task.id, `Scene preset: ${sceneResult.preset.name}`);
      await completeStage("scene");
    }

    if (task.inputMode === INPUT_MODES.MIX && backingPath) {
      await markStage("mixdown", "Mixing processed vocal back with backing track.");
      const remixedPath = path.join(tempDir, "07-mix.wav");
      await this.providers.audio.remix(currentPath, backingPath, remixedPath);
      currentPath = remixedPath;
      await completeStage("mixdown");
    }

    await markStage("export", "Encoding final deliverable.");
    const resultPath = path.join(RESULT_DIR, `${task.id}.mp3`);
    await ensureParentDir(resultPath);
    await this.providers.audio.exportFinal(currentPath, resultPath);
    await completeStage("export");

    const summary = {
      taskId: task.id,
      totalDurationMs: Date.now() - startedAt,
      metadata,
      inputMode: task.inputMode,
      steps: task.steps,
      preset: getScenePreset(task.scenePreset)
    };
    await this.providers.audio.writeSummaryFile(tempDir, summary);

    return {
      resultPath,
      resultUrl: `/media/results/${path.basename(resultPath)}`,
      progress: 100
    };
  }

  #validateMetadata(metadata) {
    if (!metadata.durationSeconds || Number.isNaN(metadata.durationSeconds)) {
      throw new Error("Uploaded file does not contain a readable audio stream.");
    }

    if (metadata.durationSeconds > MAX_DURATION_SECONDS) {
      throw new Error(`Audio is too long. Maximum supported length is ${MAX_DURATION_SECONDS / 60} minutes.`);
    }

    if (metadata.sampleRate < MIN_SAMPLE_RATE) {
      throw new Error(`Sample rate too low. Minimum supported sample rate is ${MIN_SAMPLE_RATE} Hz.`);
    }
  }
}
