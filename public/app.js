const form = document.querySelector("#upload-form");
const presetGrid = document.querySelector("#preset-grid");
const presetTemplate = document.querySelector("#preset-template");
const taskTemplate = document.querySelector("#task-template");
const taskList = document.querySelector("#task-list");
const submitMessage = document.querySelector("#submit-message");
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
  await refreshTasks();
  setInterval(refreshTasks, 2000);
}

function initializePitchControls(defaultPitch) {
  pitchStrength.value = defaultPitch.pitchStrength;
  pitchStrengthValue.textContent = defaultPitch.pitchStrength;
  form.pitchStyle.value = defaultPitch.pitchStyle;
  syncPitchModeUI();
  pitchStrength.addEventListener("input", () => {
    pitchStrengthValue.textContent = pitchStrength.value;
  });
  form.querySelectorAll('input[name="pitchMode"]').forEach((input) => {
    input.addEventListener("change", syncPitchModeUI);
  });
}

function syncPitchModeUI() {
  const mode = form.querySelector('input[name="pitchMode"]:checked')?.value;
  midiUploadBlock.hidden = mode !== "midi_reference";
  referenceUploadBlock.hidden = mode !== "reference_vocal";
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
    fragment.querySelector(".task-title").textContent = task.originalName;
    fragment.querySelector(".task-subtitle").textContent = buildTaskSubtitle(task, preset);
    fragment.querySelector(".task-status").textContent = formatStatus(task.status);
    fragment.querySelector(".progress-bar").style.width = `${task.progress || 0}%`;
    fragment.querySelector(".task-stage").textContent = stageCopy(task);

    const error = fragment.querySelector(".task-error");
    if (task.error) {
      error.textContent = task.error;
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

    const audio = fragment.querySelector(".task-audio");
    const download = fragment.querySelector(".task-download");
    if (task.resultUrl) {
      audio.src = task.resultUrl;
      download.href = task.resultUrl;
      download.textContent = "下载成品";
    } else {
      audio.remove();
      download.remove();
    }

    taskList.appendChild(fragment);
  });
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
    return `处理失败 · ${task.currentStage}`;
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
