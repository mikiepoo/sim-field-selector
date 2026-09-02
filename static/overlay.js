const query = new URLSearchParams(window.location.search);
const settings = {
  field_size: boundedFieldSize("field_size", 40),
};
let previousDrivers = new Map();
let hasRenderedField = false;

function boundedFieldSize(key, fallback) {
  const value = Number(query.get(key));
  return Number.isInteger(value) && value >= 40 && value <= 43 ? value : fallback;
}

document.querySelector("#rules-summary").textContent =
  `${settings.field_size}-car field · ${settings.field_size - 30} Open-Charter guarantees · 5 base open spots`;

async function poll() {
  const params = new URLSearchParams(settings);
  try {
    const response = await fetch(`/api/live/field?${params}`, {cache: "no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to calculate live field");
    renderState(data.live || {});
    if (data.live?.connected) renderField(data);
  } catch (error) {
    renderError(error.message);
  } finally {
    window.setTimeout(poll, 1000);
  }
}

function renderState(live) {
  const state = document.querySelector("#session-state");
  if (!live.connected) {
    state.className = "session-state waiting";
    state.querySelector("strong").textContent = "WAITING FOR IRACING";
    state.querySelector("small").textContent = live.message || "Start or join the simulator session";
    document.querySelector("#updated-at").textContent = "Not connected";
    document.querySelector("#track-name").textContent = "Waiting for track information";
    document.querySelector("#time-remaining").textContent = "--:--";
    return;
  }

  state.className = `session-state ${live.provisional ? "provisional" : "final"}`;
  state.querySelector("strong").textContent = live.provisional ? "QUALIFYING · PROVISIONAL" : "QUALIFYING · FINAL";
  state.querySelector("small").textContent =
    `Session ${live.subsession_id || "unknown"} · ${live.session_name} · ${live.session_state}`;
  document.querySelector("#track-name").textContent =
    [live.track_name, live.track_config].filter(Boolean).join(" · ") || "iRacing live session";
  document.querySelector("#time-remaining").textContent = live.provisional
    ? formatRemaining(live.session_time_remaining)
    : "FINAL";
  document.querySelector("#updated-at").textContent = `Updated ${formatClock(live.captured_at)}`;
}

function renderField(result) {
  const drivers = result.drivers || [];
  const timed = drivers.filter((driver) => Number(driver.best_lap_time) > 0);
  const poleTime = timed.length ? Math.min(...timed.map((driver) => Number(driver.best_lap_time))) : null;
  const openTransfers = drivers.filter((driver) => driver.result === "IN" && driver.reason === "Open position");
  const protectedTransfers = drivers.filter((driver) => driver.result === "IN" && driver.reason !== "Charter locked");
  const lastTransfer = openTransfers.at(-1) || protectedTransfers.at(-1) || null;
  const firstOut = drivers.find((driver) => driver.result === "DNQ") || null;

  document.querySelector("#entered-count").textContent = `${timed.length} / ${result.summary.entered}`;
  document.querySelector("#field-count").textContent = `${result.summary.in_field} / ${result.summary.field_size}`;
  document.querySelector("#dnq-count").textContent = result.summary.dnq;
  document.querySelector("#missing-count").textContent = result.summary.missing_charters;
  document.querySelector("#oc-count").textContent = `${result.summary.open_charter_in} / ${result.summary.open_charter_configured}`;
  document.querySelector("#bubble-matchup").innerHTML = renderBubble(lastTransfer, firstOut);

  const bubbleInKey = driverKey(lastTransfer);
  const bubbleOutKey = driverKey(firstOut);
  const midpoint = Math.ceil(drivers.length / 2);
  const groups = [drivers.slice(0, midpoint), drivers.slice(midpoint)].filter((group) => group.length);
  document.querySelector("#standings-columns").innerHTML = groups.map((group) => `
    <div class="standings-column">
      <div class="column-head"><span>Q</span><span>Car / driver</span><span>Class</span><span>Best lap</span><span>Gap</span><span>Status</span></div>
      ${group.map((driver) => renderDriver(driver, poleTime, bubbleInKey, bubbleOutKey)).join("")}
    </div>
  `).join("");

  previousDrivers = new Map(drivers.map((driver) => [identityKey(driver), {
    rank: driver.qualifying_rank,
    result: driver.result,
  }]));
  hasRenderedField = true;

  const notices = [];
  if (result.unmatched?.length) notices.push(`${result.unmatched.length} unmatched ${result.unmatched.length === 1 ? "entry" : "entries"}`);
  if (result.live?.provisional) notices.push("Projection changes as new times are posted");
  document.querySelector("#notice").textContent = notices.join(" · ") || "Field calculation is final.";
}

function renderDriver(driver, poleTime, bubbleInKey, bubbleOutKey) {
  const key = driverKey(driver);
  const previous = previousDrivers.get(identityKey(driver));
  const movement = hasRenderedField && previous ? Number(previous.rank) - Number(driver.qualifying_rank) : 0;
  const statusChange = hasRenderedField && previous && previous.result !== driver.result
    ? driver.result === "IN" ? " just-in" : " just-out"
    : "";
  const bubbleClass = key && key === bubbleInKey ? " bubble-in" : key && key === bubbleOutKey ? " bubble-out" : "";
  const noTimeClass = Number(driver.best_lap_time) > 0 ? "" : " no-time";
  const level = {"charter": "CHTR", "open-charter": "O-CHTR", "open": "OPEN"}[driver.charter_level] || driver.charter_level;
  const status = driver.result === "DNQ" ? "OUT" : driver.reason === "Charter locked" ? "LOCK" : "IN";
  return `
    <div class="driver-row status-${driver.result.toLowerCase()} level-${escapeHtml(driver.charter_level)}${bubbleClass}${noTimeClass}${statusChange}">
      <div class="rank"><strong>${driver.qualifying_rank ?? "—"}</strong>${renderMovement(movement)}</div>
      <div class="identity" title="${escapeHtml(driver.reason)}"><strong><span class="car-number">#${escapeHtml(driver.car_number)}</span>${escapeHtml(driver.name)}</strong></div>
      <span class="level-pill">${escapeHtml(level)}</span>
      <span class="lap">${formatLap(driver.best_lap_time)}</span>
      <span class="gap">${formatGap(driver.best_lap_time, poleTime)}</span>
      <span class="result-pill">${status}</span>
    </div>`;
}

function renderBubble(lastTransfer, firstOut) {
  if (!lastTransfer) return "<strong>Waiting for transfer positions</strong>";
  const inDriver = `<div class="bubble-driver in"><span>LAST IN</span><strong>#${escapeHtml(lastTransfer.car_number)} ${escapeHtml(lastTransfer.name)}</strong><small>Q${lastTransfer.qualifying_rank} · ${formatLap(lastTransfer.best_lap_time)}</small></div>`;
  if (!firstOut) return `${inDriver}<div class="bubble-gap">FIELD OPEN</div>`;
  const difference = Number(firstOut.best_lap_time) - Number(lastTransfer.best_lap_time);
  const gap = Number.isFinite(difference) && Number(lastTransfer.best_lap_time) > 0 && Number(firstOut.best_lap_time) > 0
    ? `${difference >= 0 ? "+" : ""}${difference.toFixed(3)}`
    : "NO GAP";
  const outDriver = `<div class="bubble-driver out"><span>FIRST OUT</span><strong>#${escapeHtml(firstOut.car_number)} ${escapeHtml(firstOut.name)}</strong><small>Q${firstOut.qualifying_rank} · ${formatLap(firstOut.best_lap_time)}</small></div>`;
  return `${inDriver}<div class="bubble-gap"><span>GAP</span><strong>${gap}</strong></div>${outDriver}`;
}

function identityKey(driver) {
  return `${driver.car_number}|${driver.name}`;
}

function driverKey(driver) {
  return driver ? `${driver.qualifying_rank}|${driver.car_number}|${driver.name}` : "";
}

function renderMovement(movement) {
  if (!Number.isFinite(movement) || movement === 0) return "<small class=\"movement steady\">—</small>";
  return movement > 0
    ? `<small class="movement up">▲${movement}</small>`
    : `<small class="movement down">▼${Math.abs(movement)}</small>`;
}

function formatLap(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value <= 0) return "NO TIME";
  const minutes = Math.floor(value / 60);
  return `${minutes}:${(value - minutes * 60).toFixed(3).padStart(6, "0")}`;
}

function formatGap(seconds, poleTime) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value <= 0 || !poleTime) return "—";
  const gap = value - poleTime;
  return gap < 0.0005 ? "POLE" : `+${gap.toFixed(3)}`;
}

function formatClock(timestamp) {
  const date = new Date(timestamp);
  return Number.isNaN(date.valueOf()) ? "just now" : date.toLocaleTimeString([], {hour: "numeric", minute: "2-digit", second: "2-digit"});
}

function formatRemaining(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value < 0 || value > 86400) return "--:--";
  const rounded = Math.ceil(value);
  const minutes = Math.floor(rounded / 60);
  return `${String(minutes).padStart(2, "0")}:${String(rounded % 60).padStart(2, "0")}`;
}

function renderError(message) {
  const state = document.querySelector("#session-state");
  state.className = "session-state error";
  state.querySelector("strong").textContent = "OVERLAY ERROR";
  state.querySelector("small").textContent = message;
}

function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = String(value ?? "");
  return element.innerHTML;
}

poll();
