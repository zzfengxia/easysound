import fs from "node:fs/promises";

export class OptionalPitchProvider {
  async correctPitch(sourcePath, outputPath, context = {}) {
    await fs.copyFile(sourcePath, outputPath);

    return {
      outputPath,
      applied: false,
      note:
        context.inputMode === "with_backing_track"
          ? "Pitch correction fallback kept the vocal timing intact. Replace this provider with a third-party pitch API for production-grade tuning."
          : "Pitch correction provider is currently a safe bypass. Hook a third-party tuning API here to enable natural auto-tune."
    };
  }
}
