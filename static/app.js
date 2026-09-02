let latestResult = null;
let latestLive = {};
let rosterRows = [];
let sessionDrivers = [];
let sessionConnected = false;
let trackRows = [];
let appClosing = false;

function updateFieldSettings() {
  const fieldSize = Number(document.querySelector("#field-size").value);
  document.querySelector("#derived-oc-spots").textContent = Number.isFinite(fieldSize) ? fieldSize - 30 : "—";
  const params = new URLSearchParams({field_size: document.querySelector("#field-size").value});
  document.querySelector("#overlay-link").href = `/overlay?${params}`;
  document.querySelector("#overlay-details-link").href = `/overlay/details?${params}`;
  pollLive();
}

async function pollLive() {
  if (appClosing) return;
  const params = new URLSearchParams({field_size: document.querySelector("#field-size").value});
  const state = document.querySelector("#live-state");
  try {
    const response = await fetch(`/api/live/field?${params}`, {cache: "no-store"});
    const data = await response.json();
    latestLive = data.live || {};
    state.className = `live-state ${latestLive.connected ? (latestLive.provisional ? "connected" : "final") : "waiting"}`;
    state.querySelector("strong").textContent = latestLive.connected
      ? `QUALIFYING — ${latestLive.provisional ? "PROVISIONAL" : "FINAL"}`
      : latestLive.message || "Waiting for the iRacing simulator";
    state.querySelector("small").textContent = latestLive.connected
      ? liveDescription(latestLive)
      : latestLive.detail || "Run iRacing on this computer and join the session.";
    document.querySelector("#pit-stall-count").textContent = latestLive.connected && latestLive.pit_stalls
      ? latestLive.pit_stalls
      : "Not stored";
    if (!response.ok) throw new Error(data.error || "Unable to calculate live field");
    document.querySelector("#error").textContent = "";
    if (latestLive.connected) {
      renderResults(data);
    } else {
      document.querySelector("#results").hidden = true;
    }
  } catch (error) {
    document.querySelector("#error").textContent = error.message;
  }
}

async function closeApplication() {
  if (!window.confirm("Close Sim Field Selector? Live qualifying updates and overlays will stop.")) return;
  const button = document.querySelector("#close-app");
  button.disabled = true;
  button.textContent = "Closing…";
  try {
    const response = await fetch("/api/app/exit", {
      method: "POST",
      headers: {"X-Sim-Field-Selector": "close"},
    });
    const data = await response.json();
    if (!response.ok || !data.closing) throw new Error(data.error || "Unable to close the app");
    appClosing = true;
    const state = document.querySelector("#live-state");
    state.className = "live-state waiting";
    state.querySelector("strong").textContent = "Sim Field Selector is closed";
    state.querySelector("small").textContent = "You can close this browser tab. Launch the app again when needed.";
    document.querySelector("#results").hidden = true;
  } catch (error) {
    button.disabled = false;
    button.textContent = "Close App";
    document.querySelector("#error").textContent = error.message;
  }
}

function liveDescription(live) {
  const track = [live.track_name, live.track_config].filter(Boolean).join(" · ");
  const pitStalls = live.pit_stalls ? ` · ${live.pit_stalls} pit stalls` : " · pit stalls not stored";
  return `${track || `Session ${live.subsession_id || "unknown"}`} · ${live.driver_count || 0} drivers${pitStalls}`;
}

function renderResults(result) {
  latestResult = result;
  document.querySelector("#summary").innerHTML = [
    [result.live?.driver_count ?? result.drivers.length, "Total drivers"],
    [result.summary.field_size ?? "—", "Field size"],
    [result.summary.in_field, "In field"],
    [result.summary.dnq, "DNQ"],
    [result.summary.charter_locked, "Charters"],
    [result.summary.missing_charters, "Missing Charter"],
    [result.summary.open_charter_selected, "Open-Charter"],
    [result.summary.open_selected, "Final pool"],
  ].map(([value, label]) => `<div><strong>${value}</strong><span>${label}</span></div>`).join("");

  document.querySelector("#result-rows").innerHTML = result.drivers.map((driver) => `
    <tr class="${driver.result.toLowerCase()} level-${escapeHtml(driver.charter_level)}">
      <td>${driver.qualifying_rank ?? "—"}</td><td>#${escapeHtml(driver.car_number)}</td><td>${escapeHtml(driver.name)}</td><td>${formatLap(driver.best_lap_time)}</td>
      <td><span class="level-badge">${escapeHtml(driver.charter_level)}</span></td><td><span class="badge">${driver.result}</span></td><td>${escapeHtml(driver.reason)}</td>
    </tr>`).join("");

  const unmatched = result.unmatched || [];
  document.querySelector("#unmatched-wrap").hidden = unmatched.length === 0;
  document.querySelector("#unmatched").innerHTML = unmatched.map((row) => `<li>Q${row.qualifying_rank}: ${escapeHtml(row.input || "(blank)")} — ${escapeHtml(row.error)}</li>`).join("");
  const missing = result.missing_charters || [];
  document.querySelector("#missing-charters-wrap").hidden = missing.length === 0;
  document.querySelector("#missing-charters").innerHTML = missing.map((driver) => `<li>#${escapeHtml(driver.car_number)} ${escapeHtml(driver.name)}</li>`).join("");
  document.querySelector("#results").hidden = false;
}

async function finalizeField() {
  try {
    const response = await fetch("/api/live/finalize", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({field_size: Number(document.querySelector("#field-size").value)})});
    const data = await response.json();
    if (!response.ok || !data.saved) throw new Error(data.error || data.live?.message || "Unable to save field");
    document.querySelector("#finalize").textContent = `Saved ${data.filename}`;
  } catch (error) {
    document.querySelector("#error").textContent = error.message;
  }
}

async function copyResults() {
  if (!latestResult) return;
  const text = latestResult.drivers.map((driver) => `${driver.qualifying_rank ?? "—"}. #${driver.car_number} ${driver.name} — ${driver.result} (${driver.reason})`).join("\n");
  await navigator.clipboard.writeText(text);
  document.querySelector("#copy").textContent = "Copied";
  window.setTimeout(() => document.querySelector("#copy").textContent = "Copy Results", 1200);
}

function setEditorOpen(editorId) {
  document.querySelectorAll(".editor-panel").forEach((editor) => {
    const open = editor.id === editorId;
    editor.classList.toggle("open", open);
    editor.setAttribute("aria-hidden", String(!open));
  });
  document.querySelector("#editor-scrim").hidden = !editorId;
}

async function openRosterEditor() {
  const message = document.querySelector("#roster-message");
  message.className = "";
  message.textContent = "Loading driver lists...";
  setEditorOpen("roster-editor");
  try {
    const [rosterResponse, sessionResponse] = await Promise.all([
      fetch("/api/roster", {cache: "no-store"}),
      fetch("/api/live/drivers", {cache: "no-store"}),
    ]);
    const data = await rosterResponse.json();
    const live = await sessionResponse.json();
    if (!rosterResponse.ok) throw new Error(data.error || "Unable to load driver lists");
    if (!sessionResponse.ok) throw new Error(live.error || "Unable to load session drivers");
    rosterRows = data.drivers.map((driver) => ({...driver}));
    sessionConnected = Boolean(live.connected);
    sessionDrivers = live.drivers || [];
    renderRosterRows();
    message.textContent = `${rosterRows.length} configured drivers loaded`;
  } catch (error) {
    message.className = "error";
    message.textContent = error.message;
  }
}

function renderRosterRows() {
  document.querySelector("#roster-rows").innerHTML = rosterRows.map((driver, index) => `
    <div class="roster-row" data-index="${index}">
      <input class="car-number" value="${escapeAttribute(driver.car_number)}" aria-label="Car number">
      <input class="driver-name" value="${escapeAttribute(driver.name)}" aria-label="Driver name">
      <input class="cust-id" type="number" min="1" value="${escapeAttribute(driver.cust_id ?? "")}" placeholder="Optional" aria-label="iRacing customer ID">
      <select class="charter-level" aria-label="Driver group">${groupOption("charter", "Charter", driver.charter_level)}${groupOption("open-charter", "Open-Charter", driver.charter_level)}${groupOption("open", "Open", driver.charter_level)}</select>
      <button class="remove-row remove-driver" type="button" aria-label="Remove driver">&times;</button>
    </div>`).join("");
  filterRosterRows();
  renderSessionDrivers();
}

function renderSessionDrivers() {
  const summary = document.querySelector("#session-driver-summary");
  const container = document.querySelector("#session-suggestions");
  if (!sessionConnected) {
    summary.textContent = "No active simulator session";
    container.innerHTML = '<p class="session-empty">Join the iRacing session, then reopen this editor to pull its drivers.</p>';
    return;
  }
  const missing = sessionDrivers.filter((driver) => !findRosterMatch(driver));
  summary.textContent = `${sessionDrivers.length} in session · ${sessionDrivers.length - missing.length} configured · ${missing.length} need a group`;
  container.innerHTML = missing.length ? missing.map((driver) => `
    <div class="session-suggestion" data-session-index="${sessionDrivers.indexOf(driver)}">
      <span class="session-number">#${escapeHtml(driver.car_number || "—")}</span><strong>${escapeHtml(driver.name || "Unknown driver")}</strong>
      <select aria-label="Driver group"><option value="charter">Charter</option><option value="open-charter">Open-Charter</option><option value="open" selected>Open</option></select>
      <button type="button" class="add-session-driver">Add</button>
    </div>`).join("") : '<p class="session-empty">Every driver in this session is already assigned to a group.</p>';
}

function findRosterMatch(driver) {
  const custId = Number(driver.cust_id);
  if (custId > 0 && rosterRows.filter((row) => Number(row.cust_id) === custId).length === 1) return true;
  const name = normalizeName(driver.name);
  if (name && rosterRows.filter((row) => normalizeName(row.name) === name).length === 1) return true;
  const number = String(driver.car_number ?? "").trim().replace(/^#/, "");
  return Boolean(number && rosterRows.filter((row) => String(row.car_number) === number).length === 1);
}

function readRosterRows() {
  return [...document.querySelectorAll(".roster-row")].map((row) => {
    const custId = row.querySelector(".cust-id").value.trim();
    return {car_number: row.querySelector(".car-number").value.trim().replace(/^#/, ""), name: row.querySelector(".driver-name").value.trim(), cust_id: custId ? Number(custId) : null, charter_level: row.querySelector(".charter-level").value};
  });
}

function filterRosterRows() {
  const search = document.querySelector("#roster-search").value.trim().toLowerCase();
  const group = document.querySelector("#roster-filter").value;
  document.querySelectorAll(".roster-row").forEach((row) => {
    const matchesSearch = !search || `${row.querySelector(".car-number").value} ${row.querySelector(".driver-name").value}`.toLowerCase().includes(search);
    const matchesGroup = group === "all" || row.querySelector(".charter-level").value === group;
    row.hidden = !(matchesSearch && matchesGroup);
  });
}

async function saveRosterEditor() {
  const message = document.querySelector("#roster-message");
  try {
    message.className = ""; message.textContent = "Saving...";
    const response = await fetch("/api/roster", {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify({drivers: readRosterRows()})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to save driver lists");
    rosterRows = data.drivers;
    message.textContent = `${data.count} drivers saved; live field updated`;
    window.setTimeout(() => setEditorOpen(null), 650);
  } catch (error) { message.className = "error"; message.textContent = error.message; }
}

async function openTrackEditor() {
  const message = document.querySelector("#track-message");
  message.className = ""; message.textContent = "Loading track list...";
  setEditorOpen("track-editor");
  try {
    const response = await fetch("/api/tracks", {cache: "no-store"});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to load track list");
    trackRows = data.tracks.map((track) => ({...track}));
    renderTrackRows(); renderActiveTrack();
    message.textContent = `${trackRows.length} track configurations loaded`;
  } catch (error) { message.className = "error"; message.textContent = error.message; }
}

function renderActiveTrack() {
  const summary = document.querySelector("#active-track-summary");
  const action = document.querySelector("#active-track-action");
  if (!latestLive.connected || !latestLive.track_id) {
    summary.textContent = "No active simulator session"; action.textContent = "Join a session to capture its Track ID automatically."; return;
  }
  const label = [latestLive.track_name, latestLive.track_config].filter(Boolean).join(" · ");
  const stored = trackRows.find((track) => Number(track.track_id) === Number(latestLive.track_id));
  summary.textContent = `${label || "Current track"} · ID ${latestLive.track_id}`;
  action.innerHTML = stored ? `${stored.pit_stalls} pit stalls are stored for this configuration.` : '<button id="add-active-track" type="button">Add Active Track</button>';
}

function renderTrackRows() {
  document.querySelector("#track-rows").innerHTML = trackRows.map((track, index) => `
    <div class="track-row" data-index="${index}">
      <input class="track-id" type="number" min="1" value="${escapeAttribute(track.track_id ?? "")}" aria-label="Track ID">
      <input class="track-name" value="${escapeAttribute(track.track_name)}" aria-label="Track name">
      <input class="track-config" value="${escapeAttribute(track.track_config)}" aria-label="Track configuration">
      <input class="pit-stalls" type="number" min="1" max="200" value="${escapeAttribute(track.pit_stalls ?? "")}" aria-label="Pit stalls">
      <button class="remove-row remove-track" type="button" aria-label="Remove track">&times;</button>
    </div>`).join("");
  filterTrackRows();
}

function readTrackRows() {
  return [...document.querySelectorAll(".track-row")].map((row) => ({track_id: Number(row.querySelector(".track-id").value), track_name: row.querySelector(".track-name").value.trim(), track_config: row.querySelector(".track-config").value.trim(), pit_stalls: Number(row.querySelector(".pit-stalls").value)}));
}

function filterTrackRows() {
  const search = document.querySelector("#track-search").value.trim().toLowerCase();
  document.querySelectorAll(".track-row").forEach((row) => { row.hidden = Boolean(search && !row.textContent.toLowerCase().includes(search) && ![...row.querySelectorAll("input")].some((input) => input.value.toLowerCase().includes(search))); });
}

async function saveTrackEditor() {
  const message = document.querySelector("#track-message");
  try {
    message.className = ""; message.textContent = "Saving...";
    const response = await fetch("/api/tracks", {method: "PUT", headers: {"Content-Type": "application/json"}, body: JSON.stringify({tracks: readTrackRows()})});
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "Unable to save track list");
    trackRows = data.tracks; message.textContent = `${data.count} track configurations saved`;
    await pollLive(); window.setTimeout(() => setEditorOpen(null), 650);
  } catch (error) { message.className = "error"; message.textContent = error.message; }
}

function groupOption(value, label, selected) { return `<option value="${value}"${value === selected ? " selected" : ""}>${label}</option>`; }
function normalizeName(value) { return String(value ?? "").trim().toLowerCase().replace(/\s+/g, " "); }
function escapeHtml(value) { const element = document.createElement("div"); element.textContent = String(value ?? ""); return element.innerHTML; }
function escapeAttribute(value) { return String(value ?? "").replaceAll("&", "&amp;").replaceAll('"', "&quot;").replaceAll("<", "&lt;").replaceAll(">", "&gt;"); }
function formatLap(seconds) { const value = Number(seconds); if (!Number.isFinite(value) || value <= 0) return "No time"; const minutes = Math.floor(value / 60); return `${minutes}:${(value - minutes * 60).toFixed(3).padStart(6, "0")}`; }

document.querySelector("#field-size").addEventListener("input", updateFieldSettings);
document.querySelector("#finalize").addEventListener("click", finalizeField);
document.querySelector("#copy").addEventListener("click", copyResults);
document.querySelector("#edit-roster").addEventListener("click", openRosterEditor);
document.querySelector("#edit-tracks").addEventListener("click", openTrackEditor);
document.querySelector("#close-app").addEventListener("click", closeApplication);
document.querySelectorAll(".close-editor,.cancel-editor").forEach((button) => button.addEventListener("click", () => setEditorOpen(null)));
document.querySelector("#editor-scrim").addEventListener("click", () => setEditorOpen(null));
document.querySelector("#roster-search").addEventListener("input", filterRosterRows);
document.querySelector("#roster-filter").addEventListener("change", filterRosterRows);
document.querySelector("#save-roster").addEventListener("click", saveRosterEditor);
document.querySelector("#save-tracks").addEventListener("click", saveTrackEditor);
document.querySelector("#track-search").addEventListener("input", filterTrackRows);
document.querySelector("#add-driver").addEventListener("click", () => { rosterRows = readRosterRows(); rosterRows.push({car_number: "", name: "", cust_id: null, charter_level: "open"}); renderRosterRows(); });
document.querySelector("#add-track").addEventListener("click", () => { trackRows = readTrackRows(); trackRows.push({track_id: "", track_name: "", track_config: "", pit_stalls: ""}); renderTrackRows(); });
document.querySelector("#roster-rows").addEventListener("click", (event) => { const button = event.target.closest(".remove-driver"); if (!button) return; rosterRows = readRosterRows(); rosterRows.splice(Number(button.closest(".roster-row").dataset.index), 1); renderRosterRows(); });
document.querySelector("#track-rows").addEventListener("click", (event) => { const button = event.target.closest(".remove-track"); if (!button) return; trackRows = readTrackRows(); trackRows.splice(Number(button.closest(".track-row").dataset.index), 1); renderTrackRows(); renderActiveTrack(); });
document.querySelector("#session-suggestions").addEventListener("click", (event) => { const button = event.target.closest(".add-session-driver"); if (!button) return; rosterRows = readRosterRows(); const suggestion = button.closest(".session-suggestion"); const driver = sessionDrivers[Number(suggestion.dataset.sessionIndex)]; if (!driver || findRosterMatch(driver)) return; rosterRows.push({car_number: String(driver.car_number ?? "").replace(/^#/, ""), name: driver.name || "", cust_id: Number(driver.cust_id) > 0 ? Number(driver.cust_id) : null, charter_level: suggestion.querySelector("select").value}); renderRosterRows(); });
document.querySelector("#active-track-action").addEventListener("click", (event) => { if (!event.target.closest("#add-active-track")) return; trackRows = readTrackRows(); trackRows.push({track_id: latestLive.track_id, track_name: latestLive.track_name || "", track_config: latestLive.track_config || "", pit_stalls: ""}); renderTrackRows(); renderActiveTrack(); const pitInput = document.querySelector(".track-row:last-child .pit-stalls"); if (pitInput) pitInput.focus(); });
document.addEventListener("keydown", (event) => { if (event.key === "Escape") setEditorOpen(null); });

updateFieldSettings();
window.setInterval(pollLive, 1000);
