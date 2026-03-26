const form = document.querySelector("#upload-form");
const presetGrid = document.querySelector("#preset-grid");
const presetTemplate = document.querySelector("#preset-template");
const taskTemplate = document.querySelector("#task-template");
const taskList = document.querySelector("#task-list");
const submitMessage = document.querySelector("#submit-message");
const clearTasksButton = document.querySelector("#clear-tasks-button");
const midiUploadBlock = document.querySelector("#midi-upload-block");
const referenceUploadBlock = document.querySelector("#reference-upload-block");
const referenceThresholdBlock = document.querySelector("#reference-threshold-block");
const mixControls = document.querySelector("#mix-controls");
const softenControls = document.querySelector("#soften-controls");
const lightReverbControls = document.querySelector("#light-reverb-controls");
const pitchStrength = document.querySelector("#pitchStrength");
const pitchStrengthValue = document.querySelector("#pitchStrengthValue");
const softenAmount = document.querySelector("#softenAmount");
const softenAmountValue = document.querySelector("#softenAmountValue");
const lightReverbAmount = document.querySelector("#lightReverbAmount");
const lightReverbAmountValue = document.querySelector("#lightReverbAmountValue");
const vocalMixAmount = document.querySelector("#vocalMixAmount");
const vocalMixAmountValue = document.querySelector("#vocalMixAmountValue");
const backingMixAmount = document.querySelector("#backingMixAmount");
const backingMixAmountValue = document.querySelector("#backingMixAmountValue");
const referenceDurationRatioMin = document.querySelector("#referenceDurationRatioMin");
const referenceDurationRatioMax = document.querySelector("#referenceDurationRatioMax");
const HIDDEN_TASKS_STORAGE_KEY = "easysound.hiddenTaskIds";

let selectedPreset = "concert";
let presetsById = {};
let defaultPitchConfig = null;
let defaultStepConfig = null;
let defaultPolishConfig = null;
let defaultMixConfig = null;
let hiddenTaskIds = loadHiddenTaskIds();

async function init() {
  const response = await fetch("/api/config");
  const config = await response.json();
  defaultPitchConfig = config.defaultPitch;
  defaultStepConfig = config.defaultSteps;
  defaultPolishConfig = config.defaultPolish;
  defaultMixConfig = config.defaultMix;
  presetsById = Object.fromEntries(config.presets.map((preset) => [preset.id, preset]));
  renderPresets(config.presets);
  initializePitchControls(config.defaultPitch);
  initializeProcessingControls(config.defaultPolish);
  initializeMixControls(config.defaultMix);
  initializeTaskActions();
  await refreshTasks();
  setInterval(refreshTasks, 2000);
}

function initializePitchControls(defaultPitch) {
  pitchStrength.value = defaultPitch.pitchStrength;
  pitchStrengthValue.textContent = defaultPitch.pitchStrength;
  form.pitchStyle.value = defaultPitch.pitchStyle;
  referenceDurationRatioMin.value = Number(defaultPitch.referenceDurationRatioMin || 0.6).toFixed(2);
  referenceDurationRatioMax.value = Number(defaultPitch.referenceDurationRatioMax || 1.67).toFixed(2);
  pitchStrength.addEventListener("input", () => {
    pitchStrengthValue.textContent = pitchStrength.value;
  });
  form.querySelectorAll('input[name="pitchMode"]').forEach((input) => {
    input.addEventListener("change", syncPitchModeUI);
  });
  syncPitchModeUI();
}

function initializeProcessingControls(defaultPolish) {
  softenAmount.value = defaultPolish?.softenAmount ?? 55;
  softenAmountValue.textContent = softenAmount.value;
  lightReverbAmount.value = defaultPolish?.lightReverbAmount ?? 45;
  lightReverbAmountValue.textContent = lightReverbAmount.value;
  softenAmount.addEventListener("input", () => {
    softenAmountValue.textContent = softenAmount.value;
  });
  lightReverbAmount.addEventListener("input", () => {
    lightReverbAmountValue.textContent = lightReverbAmount.value;
  });
  form.softenVoice.addEventListener("change", syncProcessingControls);
  form.polish.addEventListener("change", syncProcessingControls);
  syncProcessingControls();
}

function initializeMixControls(defaultMix) {
  vocalMixAmount.value = defaultMix?.vocalMixAmount ?? 60;
  vocalMixAmountValue.textContent = vocalMixAmount.value;
  backingMixAmount.value = defaultMix?.backingMixAmount ?? 45;
  backingMixAmountValue.textContent = backingMixAmount.value;
  vocalMixAmount.addEventListener("input", () => {
    vocalMixAmountValue.textContent = vocalMixAmount.value;
  });
  backingMixAmount.addEventListener("input", () => {
    backingMixAmountValue.textContent = backingMixAmount.value;
  });
  form.querySelectorAll('input[name="inputMode"]').forEach((input) => {
    input.addEventListener("change", syncInputModeUI);
  });
  syncInputModeUI();
}

function initializeTaskActions() {
  clearTasksButton.addEventListener("click", async () => {
    const visibleTaskIds = [...taskList.querySelectorAll("[data-task-id]")]
      .map((node) => node.dataset.taskId)
      .filter(Boolean);

    if (!visibleTaskIds.length) {
      submitMessage.textContent = "当前列表已经是空的。";
      return;
    }

    const confirmed = window.confirm("确定只清空当前页面上的任务列表吗？任务记录、上传文件和处理结果都会保留，可在历史页继续查看。");
    if (!confirmed) {
      return;
    }

    visibleTaskIds.forEach((taskId) => hiddenTaskIds.add(taskId));
    saveHiddenTaskIds(hiddenTaskIds);
    submitMessage.textContent = `已从当前页面隐藏 ${visibleTaskIds.length} 条记录，可在历史页查看完整任务。`;
    await refreshTasks();
  });
}

function setBlockVisible(element, visible) {
  element.hidden = !visible;
  element.style.display = visible ? "block" : "none";
}

function syncInputModeUI() {
  const inputMode = form.querySelector('input[name="inputMode"]:checked')?.value;
  const showMix = inputMode === "with_backing_track";
  setBlockVisible(mixControls, showMix);
}

function syncPitchModeUI() {
  const mode = form.querySelector('input[name="pitchMode"]:checked')?.value;
  const showMidi = mode === "midi_reference";
  const showReference = mode === "reference_vocal";
  setBlockVisible(midiUploadBlock, showMidi);
  setBlockVisible(referenceUploadBlock, showReference);
  setBlockVisible(referenceThresholdBlock, showReference);
  if (!showMidi && form.midiFile) {
    form.midiFile.value = "";
  }
  if (!showReference && form.referenceVocalFile) {
    form.referenceVocalFile.value = "";
    if (defaultPitchConfig) {
      referenceDurationRatioMin.value = Number(defaultPitchConfig.referenceDurationRatioMin || 0.6).toFixed(2);
      referenceDurationRatioMax.value = Number(defaultPitchConfig.referenceDurationRatioMax || 1.67).toFixed(2);
    }
  }
}

function syncProcessingControls() {
  setBlockVisible(softenControls, !!form.softenVoice.checked);
  setBlockVisible(lightReverbControls, !!form.polish.checked);
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
  const visibleTasks = tasks.filter((task) => !hiddenTaskIds.has(task.id));
  clearTasksButton.disabled = visibleTasks.length === 0;
  clearTasksButton.title = visibleTasks.length ? "只隐藏当前页面上的任务列表，不会删除文件或历史记录。" : "当前没有可清空的页面记录。";

  if (!visibleTasks.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = tasks.length ? "当前页面记录已清空，可去历史页查看全部任务。" : "还没有任务，先上传一段音频试试。";
    taskList.appendChild(empty);
    return;
  }

  visibleTasks.forEach((task) => {
    const fragment = taskTemplate.content.cloneNode(true);
    const card = fragment.querySelector(".task-card");
    const preset = presetsById[task.scenePreset];
    const progressValue = Math.max(0, Math.min(100, Math.round(task.progress || 0)));
    card.dataset.taskId = task.id;
    fragment.querySelector(".task-title").textContent = task.originalName;
    fragment.querySelector(".task-subtitle").textContent = buildTaskSubtitle(task, preset);
    fragment.querySelector(".task-status").textContent = formatStatus(task.status);
    fragment.querySelector(".progress-bar").style.width = `${progressValue}%`;
    fragment.querySelector(".task-progress-value").textContent = `${progressValue}%`;
    fragment.querySelector(".task-stage").textContent = stageCopy(task);

    const fallbackAlert = fragment.querySelector(".task-fallback-alert");
    const fallbackMessage = buildFallbackAlert(task);
    if (fallbackMessage) {
      fallbackAlert.hidden = false;
      fallbackAlert.style.display = "block";
      fallbackAlert.textContent = fallbackMessage;
    } else {
      fallbackAlert.hidden = true;
      fallbackAlert.style.display = "none";
    }

    const error = fragment.querySelector(".task-error");
    const failureReason = buildFailureReason(task);
    if (failureReason) {
      error.textContent = `失败原因：${failureReason}`;
      error.style.display = "block";
    } else {
      error.style.display = "none";
    }

    const warningList = fragment.querySelector(".task-warnings");
    const visibleWarnings = (task.warnings || []).filter((warning) => warning !== task.pitch?.fallbackReason);
    if (visibleWarnings.length) {
      visibleWarnings.forEach((warning) => {
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
      const fileName = getTaskResultFileName(task);
      resultName.textContent = fileName ? `成品文件：${fileName}` : "成品文件已生成，可以试听和下载。";
      audio.src = task.resultUrl;
      download.href = task.resultUrl;
      download.download = fileName || "处理结果.mp3";
      download.textContent = "下载成品";
    } else {
      result.hidden = true;
      result.style.display = "none";
      audio.removeAttribute("src");
      audio.load();
      download.removeAttribute("href");
      download.removeAttribute("download");
    }

    taskList.appendChild(fragment);
  });
}

function buildFallbackAlert(task) {
  const pitch = task.pitch || {};
  if (pitch.pitchMode === "reference_vocal" && pitch.effectivePitchMode === "auto_scale" && pitch.fallbackReason) {
    return `参考干声未生效，已回退为自动修音：${pitch.fallbackReason}`;
  }
  return "";
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

function getTaskResultFileName(task) {
  const resultPath = task.resultPath || "";
  return resultPath.split(/[\\/]/).pop();
}

function buildTaskSubtitle(task, preset) {
  const mode = formatMode(task.inputMode);
  const scene = preset?.name || task.scenePreset;
  const pitchMode = formatPitchMode(task.pitch?.pitchMode);
  const pitchStyle = task.pitch?.pitchStyle === "autotune" ? "Auto-Tune" : "自然修音";
  const soften = task.polishSettings?.softenAmount ?? 55;
  const reverb = task.polishSettings?.lightReverbAmount ?? 45;
  const mixPart = task.inputMode === "with_backing_track"
    ? ` · 人声 ${task.mixSettings?.vocalMixAmount ?? 60} · 伴奏 ${task.mixSettings?.backingMixAmount ?? 45}`
    : "";
  return `${mode} · ${scene} · ${pitchMode} · ${pitchStyle}${mixPart} · 柔和 ${soften} · 轻混响 ${reverb}`;
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

function loadHiddenTaskIds() {
  try {
    const raw = window.localStorage.getItem(HIDDEN_TASKS_STORAGE_KEY);
    if (!raw) {
      return new Set();
    }
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) {
      return new Set();
    }
    return new Set(parsed.filter((value) => typeof value === "string" && value));
  } catch {
    return new Set();
  }
}

function saveHiddenTaskIds(taskIds) {
  window.localStorage.setItem(HIDDEN_TASKS_STORAGE_KEY, JSON.stringify([...taskIds]));
}

function validateReferenceThresholds() {
  const minValue = Number.parseFloat(referenceDurationRatioMin.value);
  const maxValue = Number.parseFloat(referenceDurationRatioMax.value);
  if (!Number.isFinite(minValue) || !Number.isFinite(maxValue)) {
    return "参考干声时长比例阈值必须填写数字。";
  }
  if (minValue <= 0 || maxValue <= 0) {
    return "参考干声时长比例阈值必须大于 0。";
  }
  if (minValue >= maxValue) {
    return "参考干声时长比例的最小值必须小于最大值。";
  }
  return "";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  submitMessage.textContent = "正在提交任务…";

  const selectedPitchMode = form.querySelector('input[name="pitchMode"]:checked')?.value || "auto_scale";
  if (selectedPitchMode === "reference_vocal") {
    const validationError = validateReferenceThresholds();
    if (validationError) {
      submitMessage.textContent = validationError;
      return;
    }
  }

  const data = new FormData(form);
  data.set("scenePreset", selectedPreset);
  data.set("noiseReduction", String(form.noiseReduction.checked));
  data.set("pitchCorrection", String(form.pitchCorrection.checked));
  data.set("softenVoice", String(form.softenVoice.checked));
  data.set("polish", String(form.polish.checked));
  data.set("sceneEnhancement", String(form.sceneEnhancement.checked));
  data.set("pitchStyle", form.pitchStyle.value);
  data.set("pitchStrength", String(form.pitchStrength.value));
  data.set("softenAmount", String(form.softenAmount.value));
  data.set("lightReverbAmount", String(form.lightReverbAmount.value));
  data.set("vocalMixAmount", String(form.vocalMixAmount.value));
  data.set("backingMixAmount", String(form.backingMixAmount.value));
  data.set("pitchMode", selectedPitchMode);
  if (selectedPitchMode === "reference_vocal") {
    data.set("referenceDurationRatioMin", Number.parseFloat(referenceDurationRatioMin.value).toFixed(2));
    data.set("referenceDurationRatioMax", Number.parseFloat(referenceDurationRatioMax.value).toFixed(2));
  }

  const response = await fetch("/api/tasks", {
    method: "POST",
    body: data
  });

  const payload = await response.json();
  if (!response.ok) {
    submitMessage.textContent = payload.detail || payload.error || "提交失败，请稍后再试。";
    return;
  }

  hiddenTaskIds.delete(payload.task?.id);
  saveHiddenTaskIds(hiddenTaskIds);

  form.reset();
  selectedPreset = "concert";
  form.querySelector('input[name="inputMode"][value="vocals_only"]').checked = true;
  form.noiseReduction.checked = defaultStepConfig?.noiseReduction ?? true;
  form.pitchCorrection.checked = defaultStepConfig?.pitchCorrection ?? true;
  form.softenVoice.checked = defaultStepConfig?.softenVoice ?? true;
  form.polish.checked = defaultStepConfig?.polish ?? true;
  form.sceneEnhancement.checked = defaultStepConfig?.sceneEnhancement ?? true;
  pitchStrength.value = defaultPitchConfig?.pitchStrength || 55;
  pitchStrengthValue.textContent = defaultPitchConfig?.pitchStrength || 55;
  softenAmount.value = defaultPolishConfig?.softenAmount || 55;
  softenAmountValue.textContent = defaultPolishConfig?.softenAmount || 55;
  lightReverbAmount.value = defaultPolishConfig?.lightReverbAmount || 45;
  lightReverbAmountValue.textContent = defaultPolishConfig?.lightReverbAmount || 45;
  vocalMixAmount.value = defaultMixConfig?.vocalMixAmount || 60;
  vocalMixAmountValue.textContent = defaultMixConfig?.vocalMixAmount || 60;
  backingMixAmount.value = defaultMixConfig?.backingMixAmount || 45;
  backingMixAmountValue.textContent = defaultMixConfig?.backingMixAmount || 45;
  form.pitchStyle.value = defaultPitchConfig?.pitchStyle || "natural";
  referenceDurationRatioMin.value = Number(defaultPitchConfig?.referenceDurationRatioMin || 0.6).toFixed(2);
  referenceDurationRatioMax.value = Number(defaultPitchConfig?.referenceDurationRatioMax || 1.67).toFixed(2);
  form.querySelector('input[name="pitchMode"][value="auto_scale"]').checked = true;
  syncInputModeUI();
  syncPitchModeUI();
  syncProcessingControls();
  renderPresets(Object.values(presetsById));
  submitMessage.textContent = "任务已进入队列，页面会自动刷新状态。";
  await refreshTasks();
});

init().catch((error) => {
  submitMessage.textContent = error.message;
});

