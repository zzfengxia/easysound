const form = document.querySelector("#upload-form");
const presetGrid = document.querySelector("#preset-grid");
const presetTemplate = document.querySelector("#preset-template");
const taskTemplate = document.querySelector("#task-template");
const taskList = document.querySelector("#task-list");
const submitMessage = document.querySelector("#submit-message");
const clearTasksButton = document.querySelector("#clear-tasks-button");
const midiUploadBlock = document.querySelector("#midi-upload-block");
const referenceUploadBlock = document.querySelector("#reference-upload-block");
const pitchStrength = document.querySelector("#pitchStrength");
const pitchStrengthValue = document.querySelector("#pitchStrengthValue");

let selectedPreset = "concert";
let presetsById = {};

async function init() {
  const response = await fetch("/api/config");
  const config = await response.json();
  presetsById = Object.fromEntries(config.presets.map((preset) => [preset.id, preset]));
  renderPresets(config.presets);
  initializePitchControls(config.defaultPitch);
  initializeTaskActions();
  await refreshTasks();
  setInterval(refreshTasks, 2000);
}

function initializePitchControls(defaultPitch) {
  pitchStrength.value = defaultPitch.pitchStrength;
  pitchStrengthValue.textContent = defaultPitch.pitchStrength;
  form.pitchStyle.value = defaultPitch.pitchStyle;
  pitchStrength.addEventListener("input", () => {
    pitchStrengthValue.textContent = pitchStrength.value;
  });
  form.querySelectorAll('input[name="pitchMode"]').forEach((input) => {
    input.addEventListener("change", syncPitchModeUI);
  });
  syncPitchModeUI();
}

function initializeTaskActions() {
  clearTasksButton.addEventListener("click", async () => {
    const confirmed = window.confirm("确定要清空所有历史任务吗？已完成和失败任务的记录会被删除。");
    if (!confirmed) {
      return;
    }

    clearTasksButton.disabled = true;
    submitMessage.textContent = "正在清空历史任务…";
    try {
      const response = await fetch("/api/tasks", { method: "DELETE" });
      const payload = await response.json();
      if (!response.ok) {
        submitMessage.textContent = payload.detail || payload.error || "清空失败，请稍后再试。";
        return;
      }
      submitMessage.textContent = `已清空 ${payload.cleared || 0} 条历史任务。`;
      await refreshTasks();
    } catch (error) {
      submitMessage.textContent = error.message || "清空失败，请稍后再试。";
    } finally {
      clearTasksButton.disabled = false;
    }
  });
}

function setUploadBlockVisible(element, visible) {
  element.hidden = !visible;
  element.style.display = visible ? "block" : "none";
}

function syncPitchModeUI() {
  const mode = form.querySelector('input[name="pitchMode"]:checked')?.value;
  const showMidi = mode === "midi_reference";
  const showReference = mode === "reference_vocal";
  setUploadBlockVisible(midiUploadBlock, showMidi);
  setUploadBlockVisible(referenceUploadBlock, showReference);
  if (!showMidi && form.midiFile) {
    form.midiFile.value = "";
  }
  if (!showReference && form.referenceVocalFile) {
    form.referenceVocalFile.value = "";
  }
}

function renderPresets(presets) {
  presetGrid.innerHTML = "";
  presets.forEach((preset, index) => {
    const fragment = presetTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".preset-card");
    const input = fragment.querySelector("input");
    const name = fragment.querySelector(".preset-name");
    const description = fragment.querySelector(".preset-description");

    card.style.setProperty("--accent", preset.accent);
    input.value = preset.id;
    input.checked = preset.id === selectedPreset || (!selectedPreset && index === 0);
    if (input.checked) {
      selectedPreset = preset.id;
    }
    input.addEventListener("change", () => {
      selectedPreset = preset.id;
    });
    name.textContent = preset.name;
    description.textContent = preset.description;
    presetGrid.appendChild(fragment);
  });
}

async function refreshTasks() {
  const response = await fetch("/api/tasks");
  const payload = await response.json();
  renderTasks(payload.tasks);
}

function renderTasks(tasks) {
  taskList.innerHTML = "";
  const hasActiveTasks = tasks.some((task) => task.status === "queued" || task.status === "processing");
  clearTasksButton.disabled = hasActiveTasks;
  clearTasksButton.title = hasActiveTasks ? "还有排队中或处理中的任务，暂时不能清空。" : "清空所有历史任务";

  if (!tasks.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "还没有任务，先上传一段音频试试。";
    taskList.appendChild(empty);
    return;
  }

  tasks.forEach((task) => {
    const fragment = taskTemplate.content.cloneNode(true);
    const preset = presetsById[task.scenePreset];
    const progressValue = Math.max(0, Math.min(100, Math.round(task.progress || 0)));
    fragment.querySelector(".task-title").textContent = task.originalName;
    fragment.querySelector(".task-subtitle").textContent = buildTaskSubtitle(task, preset);
    fragment.querySelector(".task-status").textContent = formatStatus(task.status);
    fragment.querySelector(".progress-bar").style.width = `${progressValue}%`;
    fragment.querySelector(".task-progress-value").textContent = `${progressValue}%`;
    fragment.querySelector(".task-stage").textContent = stageCopy(task);

    const error = fragment.querySelector(".task-error");
    const failureReason = buildFailureReason(task);
    if (failureReason) {
      error.textContent = `失败原因：${failureReason}`;
      error.style.display = "block";
    } else {
      error.style.display = "none";
    }

    const warningList = fragment.querySelector(".task-warnings");
    if (task.warnings?.length) {
      task.warnings.forEach((warning) => {
        const item = document.createElement("li");
        item.textContent = warning;
        warningList.appendChild(item);
      });
    } else {
      warningList.remove();
    }

    const result = fragment.querySelector(".task-result");
    const resultName = fragment.querySelector(".task-result-name");
    const audio = fragment.querySelector(".task-audio");
    const download = fragment.querySelector(".task-download");
    if (task.status === "completed" && task.resultUrl) {
      result.hidden = false;
      result.style.display = "block";
      resultName.textContent = buildResultName(task);
      audio.src = task.resultUrl;
      download.href = task.resultUrl;
      download.textContent = "下载成品";
    } else {
      result.hidden = true;
      result.style.display = "none";
      audio.removeAttribute("src");
      audio.load();
      download.removeAttribute("href");
    }

    taskList.appendChild(fragment);
  });
}

function buildFailureReason(task) {
  if (task.error && task.error.trim()) {
    return task.error.trim();
  }
  const failedEntry = [...(task.timeline || [])].reverse().find((entry) => entry.stage === "failed" && entry.note?.trim());
  if (failedEntry) {
    return failedEntry.note.trim();
  }
  if (task.status === "failed") {
    return "后端没有返回详细原因，请查看服务端日志。";
  }
  return "";
}

function buildResultName(task) {
  const resultPath = task.resultPath || "";
  const fileName = resultPath.split(/[\\/]/).pop();
  if (fileName) {
    return `成品文件：${fileName}`;
  }
  return "成品文件已生成，可以试听和下载。";
}

function buildTaskSubtitle(task, preset) {
  const mode = formatMode(task.inputMode);
  const scene = preset?.name || task.scenePreset;
  const pitchMode = formatPitchMode(task.pitch?.pitchMode);
  const pitchStyle = task.pitch?.pitchStyle === "autotune" ? "Auto-Tune" : "自然修音";
  return `${mode} · ${scene} · ${pitchMode} · ${pitchStyle}`;
}

function formatPitchMode(mode) {
  switch (mode) {
    case "midi_reference":
      return "MIDI 参考";
    case "reference_vocal":
      return "参考干声";
    default:
      return "自动推断";
  }
}

function formatMode(inputMode) {
  return inputMode === "with_backing_track" ? "带伴奏模式" : "干声模式";
}

function formatStatus(status) {
  switch (status) {
    case "queued":
      return "排队中";
    case "processing":
      return "处理中";
    case "completed":
      return "已完成";
    case "failed":
      return "失败";
    default:
      return status;
  }
}

function stageCopy(task) {
  if (task.status === "failed") {
    const failedStage = task.currentStage || "未知阶段";
    return `处理失败 · ${failedStage}`;
  }

  if (task.status === "completed") {
    return "处理完成，可以试听和下载。";
  }

  const lastNote = task.timeline?.[task.timeline.length - 1]?.note;
  return lastNote || "等待处理";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitMessage.textContent = "正在提交任务…";

  const data = new FormData(form);
  data.set("scenePreset", selectedPreset);
  data.set("noiseReduction", String(form.noiseReduction.checked));
  data.set("pitchCorrection", String(form.pitchCorrection.checked));
  data.set("polish", String(form.polish.checked));
  data.set("sceneEnhancement", String(form.sceneEnhancement.checked));
  data.set("pitchStyle", form.pitchStyle.value);
  data.set("pitchStrength", String(form.pitchStrength.value));
  data.set("pitchMode", form.querySelector('input[name="pitchMode"]:checked')?.value || "auto_scale");

  const response = await fetch("/api/tasks", {
    method: "POST",
    body: data
  });

  const payload = await response.json();
  if (!response.ok) {
    submitMessage.textContent = payload.detail || payload.error || "提交失败，请稍后再试。";
    return;
  }

  form.reset();
  selectedPreset = "concert";
  pitchStrength.value = 55;
  pitchStrengthValue.textContent = 55;
  form.pitchStyle.value = "natural";
  form.querySelector('input[name="pitchMode"][value="auto_scale"]').checked = true;
  syncPitchModeUI();
  renderPresets(Object.values(presetsById));
  submitMessage.textContent = "任务已进入队列，页面会自动刷新状态。";
  await refreshTasks();
});

init().catch((error) => {
  submitMessage.textContent = error.message;
});
