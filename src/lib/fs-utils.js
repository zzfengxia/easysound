import fs from "node:fs/promises";
import path from "node:path";
import { DATA_DIR, RESULT_DIR, STORAGE_DIR, TASK_DIR, TEMP_DIR, UPLOAD_DIR } from "./constants.js";

export async function ensureDirectories() {
  await Promise.all([
    fs.mkdir(DATA_DIR, { recursive: true }),
    fs.mkdir(STORAGE_DIR, { recursive: true }),
    fs.mkdir(UPLOAD_DIR, { recursive: true }),
    fs.mkdir(RESULT_DIR, { recursive: true }),
    fs.mkdir(TEMP_DIR, { recursive: true }),
    fs.mkdir(TASK_DIR, { recursive: true })
  ]);
}

export async function ensureParentDir(filePath) {
  await fs.mkdir(path.dirname(filePath), { recursive: true });
}

export async function fileExists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

export async function removeIfExists(filePath) {
  try {
    await fs.rm(filePath, { recursive: true, force: true });
  } catch {
    // Best-effort cleanup.
  }
}
