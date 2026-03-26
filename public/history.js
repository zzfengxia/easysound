const PAGE_SIZE = 10;

const historySummary = document.querySelector("#history-summary");
const historyPageIndicator = document.querySelector("#history-page-indicator");
const historyPaginationText = document.querySelector("#history-pagination-text");
const historyError = document.querySelector("#history-error");
const historyEmpty = document.querySelector("#history-empty");
const historyTableBody = document.querySelector("#history-table-body");
const historyPrev = document.querySelector("#history-prev");
const historyNext = document.querySelector("#history-next");
const historySearchInput = document.querySelector("#history-search-input");
const historyRowTemplate = document.querySelector("#history-row-template");

let presetsById = {};
let allTasks = [];
let currentPage = 1;
let searchKeyword = "";

async function init() {
  const [configResponse, tasksResponse] = await Promise.all([
    fetch("/api/config"),
    fetch("/api/tasks")
  ]);

  const configPayload = await configResponse.json();
  const tasksPayload = await tasksResponse.json();

  if (!configResponse.ok) {
    throw new Error(configPayload.detail || configPayload.error || "加载配置失败。");
  }
  if (!tasksResponse.ok) {
    throw new Error(tasksPayload.detail || tasksPayload.error || "加载历史任务失败。");
  }

  presetsById = Object.fromEntries((configPayload.presets || []).map((preset) => [preset.id, preset]));
  allTasks = tasksPayload.tasks || [];
  bindEvents();
  renderPage();
}

function bindEvents() {
  historyPrev.addEventListener("click", () => {
    if (currentPage > 1) {
      currentPage -= 1;
      renderPage();
    }
  });

  historyNext.addEventListener("click", () => {
    if (currentPage < getTotalPages()) {
      currentPage += 1;
      renderPage();
    }
  });

  historySearchInput.addEventListener("input", () => {
    searchKeyword = historySearchInput.value.trim().toLowerCase();
    currentPage = 1;
    renderPage();
  });
}

function renderPage() {
  historyTableBody.innerHTML = "";
  historyError.hidden = true;

  const filteredTasks = getFilteredTasks();

  if (!filteredTasks.length) {
    historySummary.textContent = searchKeyword ? `搜索结果 0 条 / 总计 ${allTasks.length} 条` : "共 0 条任务";
    historyPageIndicator.textContent = "";
    historyPaginationText.textContent = "";
    historyEmpty.hidden = false;
    historyEmpty.textContent = searchKeyword ? "没有匹配的任务名。" : "还没有任务记录。";
    historyPrev.disabled = true;
    historyNext.disabled = true;
    return;
  }

  historyEmpty.hidden = true;
  const totalPages = getTotalPages(filteredTasks.length);
  if (currentPage > totalPages) {
    currentPage = totalPages;
  }

  const startIndex = (currentPage - 1) * PAGE_SIZE;
  const pageTasks = filteredTasks.slice(startIndex, startIndex + PAGE_SIZE);

  pageTasks.forEach((task) => {
    const fragment = historyRowTemplate.content.cloneNode(true);
    const preset = presetsById[task.scenePreset];
    const detailLink = fragment.querySelector(".history-table-detail-link");

    fragment.querySelector(".history-table-name").textContent = task.originalName;
    fragment.querySelector(".history-table-status").textContent = formatStatus(task.status);
    fragment.querySelector(".history-table-scene").textContent = preset?.name || task.scenePreset;
    fragment.querySelector(".history-table-stage").textContent = stageCopy(task);
    fragment.querySelector(".history-table-mode").textContent = formatMode(task.inputMode);
    fragment.querySelector(".history-table-created").textContent = formatDateTime(task.createdAt);
    fragment.querySelector(".history-table-result").textContent = task.resultPath ? getFileName(task.resultPath) : "尚未生成结果文件";
    detailLink.href = `/history/task/${encodeURIComponent(task.id)}`;
    detailLink.textContent = "查看详情";

    historyTableBody.appendChild(fragment);
  });

  historySummary.textContent = searchKeyword
    ? `搜索结果 ${filteredTasks.length} 条 / 总计 ${allTasks.length} 条`
    : `共 ${allTasks.length} 条任务`;
  historyPageIndicator.textContent = `第 ${currentPage} / ${totalPages} 页`;
  historyPaginationText.textContent = `${startIndex + 1}-${Math.min(startIndex + PAGE_SIZE, filteredTasks.length)} / ${filteredTasks.length}`;
  historyPrev.disabled = currentPage <= 1;
  historyNext.disabled = currentPage >= totalPages;
}

function getFilteredTasks() {
  if (!searchKeyword) {
    return allTasks;
  }
  return allTasks.filter((task) => (task.originalName || "").toLowerCase().includes(searchKeyword));
}

function getTotalPages(totalCount = allTasks.length) {
  return Math.max(1, Math.ceil(totalCount / PAGE_SIZE));
}

function getFileName(filePath) {
  return (filePath || "").split(/[\\/]/).pop();
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
  historyError.hidden = false;
  historyError.textContent = error.message || "加载历史任务失败。";
  historySummary.textContent = "加载失败";
  historyPageIndicator.textContent = "";
  historyPaginationText.textContent = "";
});
