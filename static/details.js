const query = new URLSearchParams(window.location.search);
const requestedSize = Number(query.get("field_size"));
const fieldSize = Number.isInteger(requestedSize) && requestedSize >= 40 && requestedSize <= 43 ? requestedSize : 40;

async function poll() {
  try {
    const response = await fetch(`/api/live/field?field_size=${fieldSize}`, {cache: "no-store"});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || "Unable to calculate live field");
    renderState(result.live || {});
    if (result.live?.connected) renderDetails(result);
  } catch (error) {
    const state = document.querySelector("#session-state");
    state.className = "session-state error";
    state.querySelector("strong").textContent = error.message;
  } finally {
    window.setTimeout(poll, 1000);
  }
}

function renderState(live) {
  const state = document.querySelector("#session-state");
  if (!live.connected) {
    state.className = "session-state waiting";
    state.querySelector("strong").textContent = live.message || "WAITING FOR IRACING";
    document.querySelector("#track-name").textContent = "Start or join the simulator session";
    document.querySelector("#time-remaining").textContent = "--:--";
    document.querySelector("#total-drivers").textContent = "0";
    return;
  }
  state.className = `session-state ${live.provisional ? "provisional" : "final"}`;
  state.querySelector("strong").textContent = live.provisional ? "PROVISIONAL" : "FINAL";
  document.querySelector("#track-name").textContent = [live.track_name, live.track_config].filter(Boolean).join(" · ") || `Session ${live.subsession_id}`;
  document.querySelector("#time-remaining").textContent = live.provisional ? formatRemaining(live.session_time_remaining) : "FINAL";
  document.querySelector("#total-drivers").textContent = String(live.driver_count || 0);
}

function renderDetails(result) {
  const summary = result.summary;
  const rules = result.rules;
  const drivers = result.drivers || [];
  const guaranteed = drivers.filter((driver) => driver.reason === "Open-Charter position");
  const charters = drivers.filter((driver) => driver.reason === "Charter locked");
  const transfers = drivers.filter((driver) => driver.reason === "Open position");
  const out = drivers.filter((driver) => driver.result === "DNQ");
  const lastIn = transfers.at(-1) || guaranteed.at(-1) || null;
  const firstOut = out[0] || null;

  setText("#oc-projection", `${summary.open_charter_in} / ${summary.open_charter_configured}`);
  setText("#oc-entered", `${summary.open_charter_entered} entered · ${summary.open_charter_dnq} currently out`);
  setText("#oc-guaranteed", `${summary.open_charter_selected} / ${rules.open_charter_spots}`);
  setText("#oc-final-pool", summary.open_charter_via_final_pool);
  setText("#open-final-pool", summary.open_via_final_pool);
  setText("#oc-out", summary.open_charter_dnq);
  setText("#charter-allocation", `${summary.charter_locked} locked · ${summary.missing_charters} missing`);
  setText("#guarantee-allocation", `${summary.open_charter_selected} of ${rules.open_charter_spots} filled`);
  setText("#pool-allocation", `${summary.open_selected} of ${rules.actual_open_spots} filled · ${summary.open_charter_via_final_pool} OC + ${summary.open_via_final_pool} Open`);
  setText("#field-allocation", `${summary.in_field} of ${summary.field_size}`);
  setText("#last-in", driverSummary(lastIn));
  setText("#first-out", driverSummary(firstOut));
  setText("#bubble-gap", bubbleGap(lastIn, firstOut));
  setText("#guaranteed-count", guaranteed.length);
  setText("#charter-count", charters.length);
  setText("#transfer-count", transfers.length);
  setText("#out-count", out.length);
  setText("#vacancy-note", `${summary.missing_charters} missing Charter ${summary.missing_charters === 1 ? "entry adds" : "entries add"} ${summary.added_vacancy_spots} position${summary.added_vacancy_spots === 1 ? "" : "s"} beyond the five-position base pool.`);

  renderList("#charter-list", charters, "No Charter drivers are currently in the session");
  renderList("#guaranteed-list", guaranteed, "No Open-Charter guarantees filled yet");
  renderList("#transfer-list", transfers, "No final-pool transfers yet");
  renderList("#out-list", out, "No drivers are currently out");
}

function renderList(selector, drivers, emptyMessage) {
  document.querySelector(selector).innerHTML = drivers.length ? drivers.map((driver) => `
    <div class="driver-row level-${escapeHtml(driver.charter_level)}">
      <span class="rank">Q${driver.qualifying_rank}</span>
      <span class="number">#${escapeHtml(driver.car_number)}</span>
      <strong>${escapeHtml(driver.name)}</strong>
      <span class="level">${driver.charter_level === "open-charter" ? "O-CHTR" : driver.charter_level.toUpperCase()}</span>
      <span class="lap">${formatLap(driver.best_lap_time)}</span>
    </div>`).join("") : `<p class="empty">${emptyMessage}</p>`;
}

function driverSummary(driver) {
  return driver ? `Q${driver.qualifying_rank} · #${driver.car_number} ${driver.name} · ${formatLap(driver.best_lap_time)}` : "None";
}

function bubbleGap(lastIn, firstOut) {
  if (!lastIn || !firstOut || !(Number(lastIn.best_lap_time) > 0) || !(Number(firstOut.best_lap_time) > 0)) return "--";
  const difference = Number(firstOut.best_lap_time) - Number(lastIn.best_lap_time);
  return `${difference >= 0 ? "+" : ""}${difference.toFixed(3)}`;
}

function formatLap(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value <= 0) return "NO TIME";
  const minutes = Math.floor(value / 60);
  return `${minutes}:${(value - minutes * 60).toFixed(3).padStart(6, "0")}`;
}

function formatRemaining(seconds) {
  const value = Number(seconds);
  if (!Number.isFinite(value) || value < 0 || value > 86400) return "--:--";
  const rounded = Math.ceil(value);
  return `${String(Math.floor(rounded / 60)).padStart(2, "0")}:${String(rounded % 60).padStart(2, "0")}`;
}

function setText(selector, value) {
  document.querySelector(selector).textContent = String(value);
}

function escapeHtml(value) {
  const element = document.createElement("div");
  element.textContent = String(value ?? "");
  return element.innerHTML;
}

poll();
