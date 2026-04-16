const DATA_CANDIDATES = ["../data/top1000.json", "./data/top1000.json"];

let allRecords = [];

async function loadTopDataset() {
  let lastError = null;
  for (const path of DATA_CANDIDATES) {
    try {
      const resp = await fetch(path, { cache: "no-store" });
      if (!resp.ok) {
        lastError = new Error(`HTTP ${resp.status} for ${path}`);
        continue;
      }
      return await resp.json();
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError || new Error("无法加载数据文件");
}

function formatNumber(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Number(value).toLocaleString("en-US");
}

function formatCompact(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "-";
  return Intl.NumberFormat("en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(Number(value));
}

function median(values) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  if (sorted.length % 2 === 0) return (sorted[mid - 1] + sorted[mid]) / 2;
  return sorted[mid];
}

function getStopReasonText(reason) {
  switch (reason) {
    case "limit_reached":
      return "已达到目标条数";
    case "no_more_data":
      return "接口无更多数据";
    case "api_quota_or_payment_required":
      return "接口额度或计费限制";
    default:
      return reason || "-";
  }
}

function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function renderMeta(meta) {
  setText("metaGeneratedAt", `生成时间 ${meta.generated_at || "-"}`);
  setText("metaStopReason", `状态 ${getStopReasonText(meta.stop_reason)}`);
  setText("metaCount", `记录数 ${formatNumber(meta.record_count)}`);
}

function renderStats(records) {
  const followers = records.map((r) => Number(r.followers) || 0);
  const likes = records.map((r) => Number(r.likes) || 0);
  const totalFollowers = followers.reduce((sum, v) => sum + v, 0);
  const avgLikes = likes.length ? likes.reduce((sum, v) => sum + v, 0) / likes.length : 0;

  setText("statCreators", formatNumber(records.length));
  setText("statFollowersTotal", formatCompact(totalFollowers));
  setText("statFollowersMedian", formatCompact(median(followers)));
  setText("statLikesAvg", formatCompact(avgLikes));
}

function renderBarChart(containerId, data, valueKey) {
  const root = document.getElementById(containerId);
  if (!root) return;
  root.innerHTML = "";
  if (!data.length) {
    root.innerHTML = `<div class="empty">暂无数据</div>`;
    return;
  }

  const maxValue = Math.max(...data.map((item) => Number(item[valueKey]) || 0), 1);
  data.forEach((item) => {
    const value = Number(item[valueKey]) || 0;
    const width = Math.max(2, (value / maxValue) * 100);
    const name = item.display_name || item.username || item.uid;
    const row = document.createElement("div");
    row.className = "bar-item";
    row.innerHTML = `
      <div class="bar-head">
        <span class="bar-name">${name}</span>
        <span class="bar-value">${formatCompact(value)}</span>
      </div>
      <div class="bar-track"><div class="bar-fill" style="width:${width}%"></div></div>
    `;
    root.appendChild(row);
  });
}

function getFilteredRecords() {
  const keyword = (document.getElementById("searchInput")?.value || "").toLowerCase().trim();
  const minFollowers = Number(document.getElementById("minFollowers")?.value || 0);
  const sortBy = document.getElementById("sortBy")?.value || "rank_followers_asc";

  const filtered = allRecords.filter((row) => {
    const username = (row.username || "").toLowerCase();
    const displayName = (row.display_name || "").toLowerCase();
    const followers = Number(row.followers) || 0;
    const matchesKeyword = !keyword || username.includes(keyword) || displayName.includes(keyword);
    const matchesFollowers = followers >= minFollowers;
    return matchesKeyword && matchesFollowers;
  });

  filtered.sort((a, b) => {
    if (sortBy === "followers_desc") return (Number(b.followers) || 0) - (Number(a.followers) || 0);
    if (sortBy === "likes_desc") return (Number(b.likes) || 0) - (Number(a.likes) || 0);
    if (sortBy === "uploads_desc") return (Number(b.uploads) || 0) - (Number(a.uploads) || 0);
    const ra = Number(a.rank_followers) || Number.MAX_SAFE_INTEGER;
    const rb = Number(b.rank_followers) || Number.MAX_SAFE_INTEGER;
    return ra - rb;
  });

  return filtered;
}

function renderTable(records) {
  const tbody = document.getElementById("tableBody");
  if (!tbody) return;
  tbody.innerHTML = "";

  if (!records.length) {
    tbody.innerHTML = `<tr><td colspan="7" class="empty">筛选后无结果</td></tr>`;
    return;
  }

  records.forEach((row) => {
    const tr = document.createElement("tr");
    const avatar = row.avatar_url
      ? `<img class="avatar" src="${row.avatar_url}" alt="${row.username || "avatar"}" loading="lazy" referrerpolicy="no-referrer" />`
      : "";
    tr.innerHTML = `
      <td>${row.rank_followers ?? "-"}</td>
      <td>
        <div class="user-cell">
          ${avatar}
          <span>@${row.username || "-"}</span>
        </div>
      </td>
      <td>${row.display_name || "-"}</td>
      <td>${formatNumber(row.followers)}</td>
      <td>${formatNumber(row.likes)}</td>
      <td>${formatNumber(row.uploads)}</td>
      <td>${formatNumber(row.following)}</td>
    `;
    tbody.appendChild(tr);
  });
}

function render(filteredRecords) {
  setText("resultCount", `筛选结果 ${formatNumber(filteredRecords.length)} 条（表格全量展示）`);
  renderTable(filteredRecords);

  const followersTop10 = [...filteredRecords]
    .sort((a, b) => (Number(b.followers) || 0) - (Number(a.followers) || 0))
    .slice(0, 10);
  const likesTop10 = [...filteredRecords]
    .sort((a, b) => (Number(b.likes) || 0) - (Number(a.likes) || 0))
    .slice(0, 10);

  renderBarChart("followersChart", followersTop10, "followers");
  renderBarChart("likesChart", likesTop10, "likes");
}

function bindEvents() {
  ["searchInput", "minFollowers", "sortBy"].forEach((id) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("input", () => render(getFilteredRecords()));
    el.addEventListener("change", () => render(getFilteredRecords()));
  });
}

async function bootstrap() {
  try {
    const payload = await loadTopDataset();
    const meta = payload.meta || {};
    const records = Array.isArray(payload.records) ? payload.records : [];
    allRecords = records;

    renderMeta(meta);
    renderStats(records);
    bindEvents();
    render(getFilteredRecords());
  } catch (err) {
    const tableBody = document.getElementById("tableBody");
    if (tableBody) {
      tableBody.innerHTML = `<tr><td colspan="7" class="empty">加载失败：${String(err)}</td></tr>`;
    }
    setText("resultCount", "加载失败");
  }
}

bootstrap();
