// The volunteer's screen. Everything here comes from the API; nothing is invented.
//
//   POST /api/messages     pasted text -> cases
//   GET  /api/cases        the queue, highest score first
//   GET  /api/cases/{id}   one case with reasons, messages and call script
//   PATCH /api/cases/{id}  mark assigned / resolved
//
// The ranking is done in Python (reliefrank/score.py). This file only shows it.

let cases = [];
let filter = "";          // "" = all; otherwise a status from models.STATUSES
let selectedId = null;
let pins = {};            // case_id -> Leaflet marker

const $ = (id) => document.getElementById(id);

// ---- Colour by score: red = most urgent ----
function colourFor(score) {
  if (score >= 80) return "#c8102e";
  if (score >= 50) return "#e87722";
  return "#d4a017";
}

const escapeHtml = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, options) {
  const r = await fetch("/api" + path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail || detail; } catch (e) { /* not JSON */ }
    throw new Error(detail);
  }
  return r.status === 204 ? null : r.json();
}

function setStatus(text, kind) {
  const el = $("status");
  el.textContent = text;
  el.className = "note" + (kind ? " " + kind : "");
}

// ---- The map ----
const map = L.map("map").setView([9.8, 76.45], 9);

// Map tiles need internet. If they fail, the grey background and pins still show.
L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
  attribution: "&copy; OpenStreetMap contributors",
}).addTo(map);

// ---- Which model is answering ----
async function loadHealth() {
  const badge = $("badge");
  const text = $("badge-text");
  const error = $("badge-error");
  try {
    // verify=1 makes the server actually call the model, so "ready" is not a guess.
    const h = await api("/health?verify=1");
    const where = h.offline ? "offline" : "needs internet";
    if (h.ready) {
      badge.className = "badge badge-ok";
      text.textContent = `${h.label} · ${h.model} · ${where}`;
      error.hidden = true;
      $("rank").disabled = false;
    } else {
      badge.className = "badge badge-bad";
      text.textContent = `No model ready (${h.backend})`;
      error.textContent = h.error || "The model did not answer.";
      error.hidden = false;
      // Messages are still stored without a model, they just all need a call.
      $("rank").disabled = false;
      setStatus("Without a model every message goes to the needs-a-call queue.", "warn");
    }
  } catch (e) {
    badge.className = "badge badge-bad";
    text.textContent = "Server not reachable";
    error.textContent = e.message;
    error.hidden = false;
  }
}

// ---- The queue ----
function drawQueue() {
  const queue = $("queue");
  queue.innerHTML = "";
  $("count").textContent = cases.length ? `(${cases.length})` : "";
  $("empty").hidden = cases.length > 0;
  if (!cases.length) {
    $("empty").textContent = filter
      ? "No cases with that status."
      : "No cases yet. Paste messages or press Load demo.";
  }

  cases.forEach((c) => {
    const item = document.createElement("li");
    if (c.id === selectedId) item.classList.add("on");
    const place = c.location_text || c.area || "location unknown";
    const tags = [];
    if (c.needs_call) tags.push('<span class="tag tag-call">needs a call</span>');
    if (!c.mapped) tags.push('<span class="tag">not on map</span>');
    if (c.status === "assigned") tags.push('<span class="tag tag-ok">assigned</span>');
    if (c.status === "resolved") tags.push('<span class="tag tag-ok">done</span>');

    item.innerHTML =
      `<span class="score" style="background:${colourFor(c.score)}">${c.score}</span>` +
      `<span class="who"><strong>${escapeHtml(place)}</strong>` +
      `<small>${escapeHtml(c.gemma_note || "")}</small>` +
      `<span class="tags">${tags.join("")}</span></span>`;
    item.addEventListener("click", () => selectCase(c.id));
    queue.appendChild(item);
  });
}

function drawPins() {
  Object.values(pins).forEach((p) => map.removeLayer(p));
  pins = {};
  cases.forEach((c) => {
    if (c.lat == null || c.lng == null) return;      // nothing to place yet
    const pin = L.circleMarker([c.lat, c.lng], {
      radius: c.id === selectedId ? 13 : 10,
      color: "#ffffff",
      weight: 2,
      fillColor: colourFor(c.score),
      fillOpacity: 1,
    }).addTo(map);
    pin.bindPopup(
      `<strong>Score ${c.score}</strong><br>` +
      `${c.people_count ?? "?"} people, water at ${escapeHtml(c.water_level)}<br>` +
      `${escapeHtml(c.location_text || c.area || "")}<br>` +
      `<em>${escapeHtml((c.reasons || []).join(", "))}</em>`
    );
    pin.on("click", () => selectCase(c.id));
    pins[c.id] = pin;
  });
}

async function loadCases() {
  try {
    const q = filter ? "?status=" + encodeURIComponent(filter) : "";
    cases = await api("/cases" + q);
    drawQueue();
    drawPins();
    const unmapped = cases.filter((c) => !c.mapped).length;
    if (cases.length && unmapped) {
      setStatus(`${cases.length} case(s). ${unmapped} without known coordinates.`);
    } else if (cases.length) {
      setStatus(`${cases.length} case(s).`);
    }
  } catch (e) {
    setStatus("Could not load cases: " + e.message, "warn");
  }
}

// ---- One case, in full ----
function fieldRows(c) {
  const rows = [
    ["People", c.people_count ?? "not stated"],
    ["Vulnerable", (c.vulnerable || []).join(", ") || "none stated"],
    ["Trapped", c.trapped === null ? "not stated" : c.trapped ? "yes" : "no"],
    ["Medical need", c.medical_need === null ? "not stated" : c.medical_need ? "yes" : "no"],
    ["Water", c.water_level],
    ["Location", c.location_text || "not stated"],
    ["Area", c.area || "not matched"],
    ["Phone", c.phone || "not stated"],
  ];
  return rows
    .map(([k, v]) => `<tr><th>${k}</th><td>${escapeHtml(v)}</td></tr>`)
    .join("");
}

async function selectCase(id) {
  selectedId = id;
  drawQueue();
  drawPins();
  const pin = pins[id];
  if (pin) {
    map.setView(pin.getLatLng(), 13);
    pin.openPopup();
  }
  try {
    const c = await api("/cases/" + encodeURIComponent(id));
    const reasons = (c.reasons || []).map((r) => `<li>${escapeHtml(r)}</li>`).join("");
    const messages = (c.raw_texts || [])
      .map((t) => `<blockquote>${escapeHtml(t)}</blockquote>`)
      .join("");
    $("detail-body").innerHTML =
      `<div class="detail-head">
         <span class="score big" style="background:${colourFor(c.score)}">${c.score}</span>
         <div>
           <strong>${escapeHtml(c.location_text || c.area || "Location unknown")}</strong>
           <small>${escapeHtml(c.gemma_note || "")}</small>
         </div>
       </div>
       <h3>Why this score</h3>
       <ul class="reasons">${reasons || "<li>no points yet</li>"}</ul>
       <h3>What the model read</h3>
       <table class="fields">${fieldRows(c)}</table>
       ${c.missing && c.missing.length
          ? `<p class="warn">Missing: ${escapeHtml(c.missing.join(", "))}</p>` : ""}
       ${c.call_script
          ? `<h3>Call script</h3><pre class="script">${escapeHtml(c.call_script)}</pre>` : ""}
       <h3>Original message${(c.raw_texts || []).length > 1 ? "s" : ""}</h3>
       ${messages}
       <h3>Status</h3>
       <div class="row statuses">
         ${["new", "needs call", "assigned", "resolved"]
           .map((s) => `<button class="secondary${c.status === s ? " on" : ""}"
                         data-set-status="${s}">${s}</button>`).join("")}
       </div>`;
    $("detail").hidden = false;
    $("detail-body").querySelectorAll("[data-set-status]").forEach((b) => {
      b.addEventListener("click", () => setCaseStatus(c.id, b.dataset.setStatus));
    });
  } catch (e) {
    setStatus("Could not open case: " + e.message, "warn");
  }
}

async function setCaseStatus(id, status) {
  try {
    await api("/cases/" + encodeURIComponent(id), {
      method: "PATCH",
      body: JSON.stringify({ status }),
    });
    await loadCases();
    await selectCase(id);
  } catch (e) {
    setStatus("Could not change status: " + e.message, "warn");
  }
}

// ---- Buttons ----
async function rankPasted() {
  const text = $("paste").value.trim();
  if (!text) {
    setStatus("Paste at least one message first.", "warn");
    return;
  }
  const lines = text.split("\n").filter((l) => l.trim()).length;
  const button = $("rank");
  button.disabled = true;
  button.textContent = "Reading…";
  setStatus(`Reading ${lines} message(s) with the model. The first one is slow.`);
  try {
    const out = await api("/messages", { method: "POST", body: JSON.stringify({ text }) });
    $("paste").value = "";
    await loadCases();
    setStatus(`${out.received} message(s) read into ${out.cases.length} case(s).`);
  } catch (e) {
    setStatus("Could not read the messages: " + e.message, "warn");
  } finally {
    button.disabled = false;
    button.textContent = "Rank messages";
  }
}

async function loadDemo() {
  try {
    const d = await api("/demo");
    $("paste").value = d.messages.join("\n");
    setStatus(`${d.messages.length} demo message(s) loaded. Press Rank messages.`);
  } catch (e) {
    setStatus("Could not load demo messages: " + e.message, "warn");
  }
}

async function clearBoard() {
  if (!confirm("Delete every case on the board?")) return;
  try {
    await api("/cases", { method: "DELETE" });
    selectedId = null;
    $("detail").hidden = true;
    await loadCases();
    setStatus("Board cleared.");
  } catch (e) {
    setStatus("Could not clear: " + e.message, "warn");
  }
}

$("rank").addEventListener("click", rankPasted);
$("demo").addEventListener("click", loadDemo);
$("clear").addEventListener("click", clearBoard);
$("detail-close").addEventListener("click", () => {
  $("detail").hidden = true;
  selectedId = null;
  drawQueue();
  drawPins();
});
$("filters").addEventListener("click", (e) => {
  const b = e.target.closest(".filter");
  if (!b) return;
  filter = b.dataset.status;
  document.querySelectorAll(".filter").forEach((f) => f.classList.toggle("on", f === b));
  loadCases();
});

// Ctrl+Enter in the textarea ranks, so the demo needs no mouse.
$("paste").addEventListener("keydown", (e) => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) rankPasted();
});

loadHealth();
loadCases();
// Waiting-time points grow while the board is open, so refresh the order.
setInterval(loadCases, 60000);
