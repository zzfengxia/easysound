import fs from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import { listScenePresets } from "./config/scene-presets.js";
import { AudioPipeline } from "./lib/audio-pipeline.js";
import {
  DEFAULT_PROCESSING_STEPS,
  INPUT_MODES,
  MAX_DURATION_SECONDS,
  MAX_FILE_SIZE_BYTES,
  RESULT_DIR,
  ROOT_DIR
} from "./lib/constants.js";
import { ensureDirectories } from "./lib/fs-utils.js";
import { methodNotAllowed, notFound, parseMultipartForm, sendFile, sendJson } from "./lib/http.js";
import { JobQueue } from "./lib/job-queue.js";
import { TaskStore } from "./lib/task-store.js";
import { normalizeTaskInput } from "./lib/task-payload.js";
import { createProviders } from "./providers/index.js";

const PUBLIC_DIR = path.join(ROOT_DIR, "public");
const PORT = Number(process.env.PORT || 3000);

const taskStore = new TaskStore();
const providers = createProviders();
const pipeline = new AudioPipeline({ providers, taskStore });
const queue = new JobQueue({ taskStore, pipeline });

async function bootstrap() {
  await ensureDirectories();
  await taskStore.init();
  await queue.init();
  queue.start();

  const server = http.createServer(async (req, res) => {
    try {
      await handleRequest(req, res);
    } catch (error) {
      sendJson(res, 500, {
        error: error instanceof Error ? error.message : String(error)
      });
    }
  });

  server.listen(PORT, () => {
    console.log(`EasySound running at http://localhost:${PORT}`);
  });
}

async function handleRequest(req, res) {
  const url = new URL(req.url || "/", `http://${req.headers.host || `localhost:${PORT}`}`);

  if (req.method === "GET" && url.pathname === "/api/config") {
    return sendJson(res, 200, {
      appName: "EasySound",
      limits: {
        maxFileSizeBytes: MAX_FILE_SIZE_BYTES,
        maxDurationSeconds: MAX_DURATION_SECONDS
      },
      inputModes: INPUT_MODES,
      defaultSteps: DEFAULT_PROCESSING_STEPS,
      presets: listScenePresets()
    });
  }

  if (req.method === "GET" && url.pathname === "/api/tasks") {
    return sendJson(res, 200, {
      tasks: taskStore.list()
    });
  }

  if (url.pathname.startsWith("/api/tasks/")) {
    if (req.method !== "GET") {
      return methodNotAllowed(res);
    }

    const taskId = url.pathname.split("/").pop();
    const task = taskStore.get(taskId);
    if (!task) {
      return notFound(res);
    }

    return sendJson(res, 200, { task });
  }

  if (url.pathname === "/api/tasks") {
    if (req.method !== "POST") {
      return methodNotAllowed(res);
    }

    const formData = await parseMultipartForm(req);
    const payload = normalizeTaskInput(formData);
    const buffer = Buffer.from(await payload.file.arrayBuffer());
    const storedName = `${Date.now()}-${sanitizeFilename(payload.file.name)}`;
    const sourcePath = path.join(ROOT_DIR, "storage", "uploads", storedName);
    await fs.writeFile(sourcePath, buffer);

    const task = await taskStore.create({
      originalName: payload.file.name,
      storedName,
      sourcePath,
      size: payload.file.size,
      inputMode: payload.inputMode,
      scenePreset: payload.scenePreset,
      steps: payload.steps
    });

    queue.enqueue(task.id);

    return sendJson(res, 202, { task });
  }

  if (req.method === "GET" && url.pathname.startsWith("/media/results/")) {
    const fileName = path.basename(url.pathname);
    const filePath = path.join(RESULT_DIR, fileName);
    return sendFile(res, filePath);
  }

  if (req.method === "GET") {
    const publicPath = url.pathname === "/" ? "index.html" : url.pathname.slice(1);
    const filePath = path.join(PUBLIC_DIR, publicPath);
    try {
      return await sendFile(res, filePath);
    } catch {
      return notFound(res);
    }
  }

  return notFound(res);
}

function sanitizeFilename(name) {
  return name.replace(/[^a-zA-Z0-9._-]/g, "_");
}

await bootstrap();
