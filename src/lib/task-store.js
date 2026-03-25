import crypto from "node:crypto";
import fs from "node:fs/promises";
import path from "node:path";
import { TASK_DIR, TASK_STATUS } from "./constants.js";
import { ensureParentDir } from "./fs-utils.js";

export class TaskStore {
  constructor() {
    this.tasks = new Map();
  }

  async init() {
    const entries = await fs.readdir(TASK_DIR, { withFileTypes: true });

    await Promise.all(
      entries
        .filter((entry) => entry.isFile() && entry.name.endsWith(".json"))
        .map(async (entry) => {
          const filePath = path.join(TASK_DIR, entry.name);
          const raw = await fs.readFile(filePath, "utf8");
          const task = JSON.parse(raw);

          if (task.status === TASK_STATUS.PROCESSING) {
            task.status = TASK_STATUS.QUEUED;
            task.currentStage = "queued";
            task.progress = 0;
            task.timeline.push({
              stage: "queued",
              at: new Date().toISOString(),
              note: "Server restart detected. Task re-queued automatically."
            });
            await this.#save(task);
          }

          this.tasks.set(task.id, task);
        })
    );
  }

  list() {
    return [...this.tasks.values()].sort((a, b) => new Date(b.createdAt) - new Date(a.createdAt));
  }

  get(id) {
    return this.tasks.get(id) ?? null;
  }

  async create({ originalName, storedName, sourcePath, size, inputMode, scenePreset, steps }) {
    const id = crypto.randomUUID();
    const now = new Date().toISOString();
    const task = {
      id,
      originalName,
      storedName,
      sourcePath,
      size,
      inputMode,
      scenePreset,
      steps,
      status: TASK_STATUS.QUEUED,
      progress: 0,
      currentStage: "queued",
      resultPath: null,
      resultUrl: null,
      error: null,
      warnings: [],
      timeline: [
        {
          stage: "queued",
          at: now,
          note: "Upload accepted and queued."
        }
      ],
      stageDurationsMs: {},
      metadata: null,
      processingNotes: [],
      createdAt: now,
      updatedAt: now
    };

    this.tasks.set(id, task);
    await this.#save(task);
    return task;
  }

  async update(id, patch) {
    const current = this.get(id);
    if (!current) {
      throw new Error(`Task ${id} not found`);
    }

    const next = {
      ...current,
      ...patch,
      updatedAt: new Date().toISOString()
    };

    this.tasks.set(id, next);
    await this.#save(next);
    return next;
  }

  async pushTimeline(id, entry) {
    const current = this.get(id);
    if (!current) {
      throw new Error(`Task ${id} not found`);
    }

    return this.update(id, {
      timeline: [
        ...current.timeline,
        {
          at: new Date().toISOString(),
          ...entry
        }
      ]
    });
  }

  async addWarning(id, warning) {
    const current = this.get(id);
    if (!current) {
      throw new Error(`Task ${id} not found`);
    }

    return this.update(id, {
      warnings: [...current.warnings, warning]
    });
  }

  async addProcessingNote(id, note) {
    const current = this.get(id);
    if (!current) {
      throw new Error(`Task ${id} not found`);
    }

    return this.update(id, {
      processingNotes: [...current.processingNotes, note]
    });
  }

  async #save(task) {
    const filePath = path.join(TASK_DIR, `${task.id}.json`);
    await ensureParentDir(filePath);
    await fs.writeFile(filePath, JSON.stringify(task, null, 2));
  }
}
