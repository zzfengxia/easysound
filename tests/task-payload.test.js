import { test } from "node:test";
import assert from "node:assert/strict";
import { normalizeTaskInput } from "../src/lib/task-payload.js";

test("normalizeTaskInput parses booleans and validates supported audio files", () => {
  const formData = new FormData();
  formData.set("inputMode", "vocals_only");
  formData.set("scenePreset", "concert");
  formData.set("noiseReduction", "true");
  formData.set("pitchCorrection", "false");
  formData.set("polish", "true");
  formData.set("sceneEnhancement", "false");
  formData.set("audio", new File([new Uint8Array([1, 2, 3])], "demo.wav", { type: "audio/wav" }));

  const payload = normalizeTaskInput(formData);

  assert.equal(payload.inputMode, "vocals_only");
  assert.equal(payload.scenePreset, "concert");
  assert.deepEqual(payload.steps, {
    noiseReduction: true,
    pitchCorrection: false,
    polish: true,
    sceneEnhancement: false
  });
});

test("normalizeTaskInput rejects unsupported file types", () => {
  const formData = new FormData();
  formData.set("inputMode", "vocals_only");
  formData.set("scenePreset", "concert");
  formData.set("audio", new File([new Uint8Array([1, 2, 3])], "demo.txt", { type: "text/plain" }));

  assert.throws(() => normalizeTaskInput(formData), /Unsupported file type/);
});
