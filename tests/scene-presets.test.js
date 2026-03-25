import { test } from "node:test";
import assert from "node:assert/strict";
import { SCENE_PRESETS, getScenePreset, listScenePresets } from "../src/config/scene-presets.js";

test("scene presets expose the four launch presets", () => {
  const presets = listScenePresets();
  assert.equal(presets.length, 4);
  assert.deepEqual(
    presets.map((preset) => preset.id).sort(),
    ["bar", "concert", "studio", "theater"]
  );
});

test("unknown scene preset falls back to default concert preset", () => {
  assert.equal(getScenePreset("does-not-exist").id, "concert");
  assert.ok(Array.isArray(SCENE_PRESETS.concert.chain));
});
