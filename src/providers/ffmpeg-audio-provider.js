import fs from "node:fs/promises";
import path from "node:path";
import { getScenePreset } from "../config/scene-presets.js";
import { runFfmpeg } from "../lib/process-utils.js";

export class FfmpegAudioProvider {
  async normalizeInput(sourcePath, outputPath) {
    await runFfmpeg([
      "-i",
      sourcePath,
      "-vn",
      "-ac",
      "2",
      "-ar",
      "48000",
      "-c:a",
      "pcm_s16le",
      outputPath
    ]);
    return outputPath;
  }

  async cleanupNoise(sourcePath, outputPath) {
    const cleanupChain = [
      "highpass=f=70",
      "lowpass=f=14500",
      "afftdn=nf=-25",
      "adeclick",
      "deesser=i=0.4:m=0.5:f=0.5:s=o",
      "dynaudnorm=f=150:g=7"
    ].join(",");

    await runFfmpeg(["-i", sourcePath, "-af", cleanupChain, outputPath]);
    return outputPath;
  }

  async approximateSeparate(sourcePath, vocalPath, instrumentalPath) {
    await runFfmpeg([
      "-i",
      sourcePath,
      "-filter_complex",
      [
        "[0:a]pan=mono|c0=0.5*c0+0.5*c1,volume=1.2[a_vocal]",
        "[0:a]pan=stereo|c0=c0-c1|c1=c1-c0,volume=0.75[a_backing]"
      ].join(";"),
      "-map",
      "[a_vocal]",
      "-c:a",
      "pcm_s16le",
      vocalPath,
      "-map",
      "[a_backing]",
      "-c:a",
      "pcm_s16le",
      instrumentalPath
    ]);

    return {
      vocalPath,
      instrumentalPath,
      note: "Used a local mid/side heuristic separation. Swap this provider for an ML/API stem splitter in production."
    };
  }

  async polishVoice(sourcePath, outputPath) {
    const polishChain = [
      "acompressor=threshold=-18dB:ratio=2.2:attack=15:release=120:makeup=2",
      "equalizer=f=180:t=q:w=1.0:g=-1.5",
      "equalizer=f=3500:t=q:w=1.0:g=2.2",
      "aexciter=amount=1.1:drive=6.5:blend=0.18",
      "aecho=0.82:0.55:35|70:0.10|0.06"
    ].join(",");

    await runFfmpeg(["-i", sourcePath, "-af", polishChain, outputPath]);
    return outputPath;
  }

  async applyScenePreset(sourcePath, presetId, outputPath) {
    const preset = getScenePreset(presetId);
    const filterChain = [...preset.chain, "alimiter=limit=0.93"].join(",");
    await runFfmpeg(["-i", sourcePath, "-af", filterChain, outputPath]);
    return { outputPath, preset };
  }

  async remix(processedVocalPath, backingPath, outputPath) {
    await runFfmpeg([
      "-i",
      processedVocalPath,
      "-i",
      backingPath,
      "-filter_complex",
      "[0:a]volume=1.15[v];[1:a]volume=0.78[b];[v][b]amix=inputs=2:weights=1 1:normalize=0,alimiter=limit=0.95[out]",
      "-map",
      "[out]",
      outputPath
    ]);
    return outputPath;
  }

  async exportFinal(sourcePath, outputPath) {
    await runFfmpeg([
      "-i",
      sourcePath,
      "-c:a",
      "libmp3lame",
      "-b:a",
      "192k",
      outputPath
    ]);
    return outputPath;
  }

  async writeSummaryFile(taskTempDir, summary) {
    const summaryPath = path.join(taskTempDir, "processing-summary.json");
    await fs.writeFile(summaryPath, JSON.stringify(summary, null, 2));
    return summaryPath;
  }
}
