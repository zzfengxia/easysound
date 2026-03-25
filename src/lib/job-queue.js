import { TASK_STATUS } from "./constants.js";

export class JobQueue {
  constructor({ taskStore, pipeline }) {
    this.taskStore = taskStore;
    this.pipeline = pipeline;
    this.queue = [];
    this.activeTaskId = null;
    this.timer = null;
  }

  async init() {
    const queuedTasks = this.taskStore
      .list()
      .filter((task) => task.status === TASK_STATUS.QUEUED)
      .map((task) => task.id);

    this.queue.push(...queuedTasks);
  }

  start() {
    if (this.timer) {
      return;
    }

    this.timer = setInterval(() => {
      void this.#tick();
    }, 750);
  }

  enqueue(taskId) {
    if (!this.queue.includes(taskId) && this.activeTaskId !== taskId) {
      this.queue.push(taskId);
    }
  }

  async #tick() {
    if (this.activeTaskId || this.queue.length === 0) {
      return;
    }

    const taskId = this.queue.shift();
    const task = this.taskStore.get(taskId);
    if (!task || task.status !== TASK_STATUS.QUEUED) {
      return;
    }

    this.activeTaskId = taskId;

    try {
      const result = await this.pipeline.run(task);
      await this.taskStore.update(taskId, {
        status: TASK_STATUS.COMPLETED,
        currentStage: "completed",
        progress: result.progress,
        resultPath: result.resultPath,
        resultUrl: result.resultUrl,
        error: null
      });
      await this.taskStore.pushTimeline(taskId, {
        stage: "completed",
        note: "Processing finished successfully."
      });
    } catch (error) {
      await this.taskStore.update(taskId, {
        status: TASK_STATUS.FAILED,
        currentStage: "failed",
        error: error instanceof Error ? error.message : String(error)
      });
      await this.taskStore.pushTimeline(taskId, {
        stage: "failed",
        note: error instanceof Error ? error.message : String(error)
      });
    } finally {
      this.activeTaskId = null;
    }
  }
}
