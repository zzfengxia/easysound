const detailTitle = document.querySelector("#detail-title");
const detailSubtitle = document.querySelector("#detail-subtitle");
const detailStatus = document.querySelector("#detail-status");
const detailError = document.querySelector("#detail-error");
const detailEmpty = document.querySelector("#detail-empty");
const detailLayout = document.querySelector("#detail-layout");
const detailMeta = document.querySelector("#detail-meta");
const detailParams = document.querySelector("#detail-params");
const detailTimeline = document.querySelector("#detail-timeline");
const detailInputFiles = document.querySelector("#detail-input-files");
const detailOutputFiles = document.querySelector("#detail-output-files");
const detailAudio = document.querySelector("#detail-audio");
const detailWarningCard = document.querySelector("#detail-warning-card");
const detailWarnings = document.querySelector("#detail-warnings");

let presetsById = {};

async function init() {
  const taskId = getTaskIdFromPath();
  if (!taskId) {
    showEmpty();
    return;
  }

  const [configResponse, taskResponse] = await Promise.all([
    fetch("/api/config"),
    fetch(`/api/tasks/${encodeURIComponent(taskId)}`)
  ]);

  const configPayload = await configResponse.json();
  const taskPayload = await taskResponse.json();

  if (!configResponse.ok) {
    throw new Error(configPayload.detail || configPayload.error || "加载配置失败。");
  }

  presetsById = Object.fromEntries((configPayload.presets || []).map((preset) => [preset.id, preset]));

  if (taskResponse.status === 404) {
    showEmpty();
    return;
  }
  if (!taskResponse.ok) {
    throw new Error(taskPayload.detail || taskPayload.error || "加载任务详情失败。");
  }

  renderTask(taskPayload.task);
}

function renderTask(task) {
  const preset = presetsById[task.scenePreset];
  const warnings = buildWarnings(task);

  detailError.hidden = true;
  detailEmpty.hidden = true;
  detailLayout.hidden = false;
  detailStatus.hidden = false;

  detailTitle.textContent = task.originalName;
  detailSubtitle.textContent = `${formatMode(task.inputMode)} · ${preset?.name || task.scenePreset} · 创建于 ${formatDateTime(task.createdAt)}`;
  detailStatus.textContent = formatStatus(task.status);

  fillKv(detailMeta, [
    ["任务 ID", task.id],
    ["任务状态", formatStatus(task.status)],
    ["当前阶段", stageCopy(task)],
    ["创建时间", formatDateTime(task.createdAt)],
    ["更新时间", formatDateTime(task.updatedAt)],
    ["结果文件", task.resultPath ? getFileName(task.resultPath) : "尚未生成"],
  ]);

  fillKv(detailParams, buildParameterRows(task, preset));
  fillTimeline(detailTimeline, task.timeline || []);
  fillFiles(detailInputFiles, buildInputFiles(task));
  fillFiles(detailOutputFiles, buildOutputFiles(task));

  if (task.status === "completed" && task.resultUrl) {
    detailAudio.hidden = false;
    detailAudio.src = task.resultUrl;
  } else {
    detailAudio.hidden = true;
    detailAudio.removeAttribute("src");
  }

  if (warnings.length) {
    detailWarningCard.hidden = false;
    detailWarnings.innerHTML = "";
    warnings.forEach((warning) => {
      const item = document.createElement("li");
      item.className = "warning-item";
      item.textContent = warning;
      detailWarnings.appendChild(item);
    });
  } else {
    detailWarningCard.hidden = true;
  }
}

function buildInputFiles(task) {
  const files = [
    {
      label: "原始音频",
      name: task.originalName,
      href: toUploadUrl(task.storedName),
      previewable: true,
    }
  ];

  if (task.pitch?.midiStoredName || task.pitch?.midiOriginalName) {
    files.push({
      label: "MIDI 参考",
      name: task.pitch?.midiOriginalName || task.pitch?.midiStoredName,
      href: toUploadUrl(task.pitch?.midiStoredName),
      previewable: false,
    });
  }

  if (task.pitch?.referenceStoredName || task.pitch?.referenceOriginalName) {
    files.push({
      label: "参考干声",
      name: task.pitch?.referenceOriginalName || task.pitch?.referenceStoredName,
      href: toUploadUrl(task.pitch?.referenceStoredName),
      previewable: true,
    });
  }

  return files;
}

function buildOutputFiles(task) {
  if (!task.resultUrl) {
    return [];
  }
  return [
    {
      label: "处理结果",
      name: getFileName(task.resultPath) || "处理结果.mp3",
      href: task.resultUrl,
      previewable: false,
    }
  ];
}

function buildParameterRows(task, preset) {
  const pitch = task.pitch || {};
  const steps = task.steps || {};
  const polish = task.polishSettings || {};
  const mix = task.mixSettings || {};

  return [
    ["场景预设", preset?.name || task.scenePreset],
    ["输入模式", formatMode(task.inputMode)],
    ["降噪去杂", formatBoolean(steps.noiseReduction)],
    ["自动修音", formatBoolean(steps.pitchCorrection)],
    ["修音模式", formatPitchMode(pitch.pitchMode)],
    ["实际修音模式", formatPitchMode(pitch.effectivePitchMode || pitch.pitchMode)],
    ["修音风格", pitch.pitchStyle === "autotune" ? "Auto-Tune" : "自然修音"],
    ["修音强度", String(pitch.pitchStrength ?? 55)],
    ["声音柔和", steps.softenVoice ? `开启 · ${polish.softenAmount ?? 55}` : "关闭"],
    ["轻混响", steps.polish ? `开启 · ${polish.lightReverbAmount ?? 45}` : "关闭"],
    ["场景效果", formatBoolean(steps.sceneEnhancement)],
    ["参考时长阈值", `${formatRatio(pitch.referenceDurationRatioMin)} - ${formatRatio(pitch.referenceDurationRatioMax)}`],
    ["人声回混", task.inputMode === "with_backing_track" ? String(mix.vocalMixAmount ?? 60) : "不适用"],
    ["伴奏回混", task.inputMode === "with_backing_track" ? String(mix.backingMixAmount ?? 45) : "不适用"],
  ];
}

function buildWarnings(task) {
  const rows = [];
  const failureReason = buildFailureReason(task);
  if (failureReason) {
    rows.push(`失败原因：${failureReason}`);
  }
  if (task.pitch?.fallbackReason) {
    rows.push(`回退说明：${task.pitch.fallbackReason}`);
  }
  (task.warnings || []).forEach((warning) => rows.push(`警告：${warning}`));
  return rows;
}

function fillKv(element, rows) {
  element.innerHTML = "";
  rows.forEach(([label, value]) => {
    const row = document.createElement("div");
    row.className = "history-detail-kv-row";

    const dt = document.createElement("dt");
    dt.className = "history-detail-kv-label";
    dt.textContent = label;

    const dd = document.createElement("dd");
    dd.className = "history-detail-kv-value";
    dd.textContent = value ?? "未记录";

    row.appendChild(dt);
    row.appendChild(dd);
    element.appendChild(row);
  });
}

function fillTimeline(element, timeline) {
  element.innerHTML = "";
  if (!timeline.length) {
    const item = document.createElement("li");
    item.className = "timeline-item";
    item.textContent = "暂无处理流程记录";
    element.appendChild(item);
    return;
  }

  timeline.forEach((entry) => {
    const item = document.createElement("li");
    item.className = "timeline-item";
    item.textContent = `${formatDateTime(entry.at)} · ${entry.stage} · ${entry.note}`;
    element.appendChild(item);
  });
}

function fillFiles(element, files) {
  element.innerHTML = "";
  if (!files.length) {
    const empty = document.createElement("p");
    empty.className = "history-detail-muted";
    empty.textContent = "暂无可下载文件";
    element.appendChild(empty);
    return;
  }

  files.forEach((file) => {
    const row = document.createElement("div");
    row.className = "history-detail-file-row";

    const meta = document.createElement("div");
    meta.className = "history-detail-file-meta";

    const label = document.createElement("strong");
    label.textContent = file.label;
    const name = document.createElement("span");
    name.textContent = file.name || "未命名文件";

    meta.appendChild(label);
    meta.appendChild(name);
    row.appendChild(meta);

    const actions = document.createElement("div");
    actions.className = "history-detail-file-actions";

    if (file.href) {
      const link = document.createElement("a");
      link.className = "subtle-link-button";
      link.href = file.href;
      link.download = file.name || "download";
      link.textContent = "下载";
      actions.appendChild(link);
    }

    row.appendChild(actions);

    if (file.previewable && file.href) {
      const audio = document.createElement("audio");
      audio.className = "history-audio history-detail-inline-audio";
      audio.controls = true;
      audio.preload = "none";
      audio.src = file.href;
      row.appendChild(audio);
    }

    element.appendChild(row);
  });
}

function showEmpty() {
  detailError.hidden = true;
  detailLayout.hidden = true;
  detailStatus.hidden = true;
  detailEmpty.hidden = false;
  detailSubtitle.textContent = "当前地址没有对应的任务记录。";
}

function getTaskIdFromPath() {
  const match = window.location.pathname.match(/\/history\/task\/([^/]+)$/);
  return match ? decodeURIComponent(match[1]) : "";
}

function toUploadUrl(storedName) {
  return storedName ? `/media/uploads/${encodeURIComponent(storedName)}` : "";
}

function getFileName(filePath) {
  return (filePath || "").split(/[\\/]/).pop();
}

function formatBoolean(value) {
  return value ? "开启" : "关闭";
}

function formatRatio(value) {
  return Number.isFinite(Number(value)) ? Number(value).toFixed(2) : "未设置";
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
    return `处理失败 · ${task.currentStage || "未知阶段"}`;
  }
  if (task.status === "completed") {
    return "处理完成";
  }
  return task.timeline?.[task.timeline.length - 1]?.note || "等待处理";
}

function buildFailureReason(task) {
  if (task.error && task.error.trim()) {
    return task.error.trim();
  }
  const failedEntry = [...(task.timeline || [])].reverse().find((entry) => entry.stage === "failed" && entry.note?.trim());
  if (failedEntry) {
    return failedEntry.note.trim();
  }
  return "";
}

function formatDateTime(value) {
  if (!value) {
    return "未记录";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

init().catch((error) => {
  detailError.hidden = false;
  detailError.textContent = error.message || "加载任务详情失败。";
  detailStatus.hidden = true;
  detailLayout.hidden = true;
  detailEmpty.hidden = true;
});
