"use strict";

const TARGET = ["USA", "Canada"];
const DEFAULTS = { q: "", country: "target", degree: "", funding: "", area: "", university: "",
  deadline: "", status: "active", sort: "match", min: 40, newOnly: false };

const store = {
  get(key, fallback) {
    try { const v = localStorage.getItem(key); return v === null ? fallback : JSON.parse(v); }
    catch { return fallback; }
  },
  set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch { /* private mode */ } },
};

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "");
const DAY = 86400000;

let data = [];
let runs = [];
let filters = { ...DEFAULTS, ...store.get("filters", {}) };
let statuses = store.get("statuses", {});
let seenCutoff = store.get("seenCutoff", null);

function todayStart() { const d = new Date(); d.setHours(0, 0, 0, 0); return d; }
function daysLeft(iso) { return iso ? Math.round((new Date(iso + "T23:59:59") - todayStart()) / DAY) : null; }
function fmtDate(iso) {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? iso + "T12:00:00" : iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: d.getFullYear() === new Date().getFullYear() ? undefined : "numeric" });
}
function ago(iso) {
  const mins = Math.round((Date.now() - new Date(iso)) / 60000);
  if (mins < 60) return `${mins} min ago`;
  if (mins < 1440) return `${Math.round(mins / 60)} h ago`;
  return `${Math.round(mins / 1440)} days ago`;
}
function isNew(r) { return r.first_seen > seenCutoff; }

function fillSelect(id, values, firstLabel, extra = []) {
  const el = $(id);
  el.innerHTML = [`<option value="">${esc(firstLabel)}</option>`, ...extra, ...values.map((v) => `<option>${esc(v)}</option>`)].join("");
}

function buildOptions() {
  const uniq = (arr) => [...new Set(arr.filter(Boolean))].sort((a, b) => a.localeCompare(b));
  fillSelect("f-country", uniq(data.map((r) => r.country)), "All countries", [`<option value="target">USA &amp; Canada</option>`]);
  fillSelect("f-area", uniq(data.flatMap((r) => r.research_areas)), "Any area");
  fillSelect("f-university", uniq(data.map((r) => r.university)), "Any university");
}

function syncControls() {
  $("f-q").value = filters.q;
  for (const k of ["country", "degree", "funding", "area", "university", "deadline", "status", "sort"]) {
    const el = $("f-" + k);
    el.value = filters[k];
    if (el.value !== filters[k]) { filters[k] = DEFAULTS[k]; el.value = filters[k]; }
  }
  $("f-min").value = filters.min;
  $("f-min-out").textContent = filters.min;
  $("f-new").checked = filters.newOnly;
}

function matches(r) {
  const f = filters;
  const st = statuses[r.id] || "";
  if (f.status === "active" && st === "hidden") return false;
  if (["interested", "applied", "hidden"].includes(f.status) && st !== f.status) return false;
  if (f.country === "target" && r.country && !TARGET.includes(r.country)) return false;
  if (f.country && f.country !== "target" && r.country !== f.country) return false;
  if (f.degree && !r.degrees.includes(f.degree)) return false;
  if (f.funding === "any-funded" && !["Fully funded", "Funded", "Partially funded"].includes(r.funding)) return false;
  if (f.funding && f.funding !== "any-funded" && r.funding !== f.funding) return false;
  if (f.area && !r.research_areas.includes(f.area)) return false;
  if (f.university && r.university !== f.university) return false;
  const left = daysLeft(r.deadline);
  if (f.deadline === "has" && left === null) return false;
  if (f.deadline === "open" && left !== null && left < 0) return false;
  if (f.deadline === "30" && (left === null || left < 0 || left > 30)) return false;
  if (r.relevance < f.min) return false;
  if (f.newOnly && !isNew(r)) return false;
  if (f.q) {
    const hay = [r.poster_name, r.role, r.university, r.lab, r.country, r.summary, r.title, r.snippet, ...r.research_areas].join(" ").toLowerCase();
    if (!f.q.toLowerCase().split(/\s+/).every((w) => hay.includes(w))) return false;
  }
  return true;
}

function sorter(a, b) {
  switch (filters.sort) {
    case "found": return b.first_seen.localeCompare(a.first_seen);
    case "posted": return (b.post_date || b.first_seen).localeCompare(a.post_date || a.first_seen);
    case "deadline": {
      const da = daysLeft(a.deadline), db = daysLeft(b.deadline);
      const ka = da === null || da < 0 ? 1e9 : da, kb = db === null || db < 0 ? 1e9 : db;
      return ka - kb || b.relevance - a.relevance;
    }
    default: return b.relevance - a.relevance || b.first_seen.localeCompare(a.first_seen);
  }
}

function field(r, name, value) {
  if (!value) return "";
  return r.inferred_fields.includes(name)
    ? `<span class="inferred" title="Inferred, not stated in the post. Verify.">${esc(value)}</span>`
    : esc(value);
}

function card(r) {
  const left = daysLeft(r.deadline);
  const expired = left !== null && left < 0;
  const scoreCls = r.relevance >= 75 ? "good" : r.relevance >= 50 ? "mid" : "low";
  const chips = [];
  if (isNew(r)) chips.push(`<span class="chip new">NEW</span>`);
  for (const d of r.degrees) chips.push(`<span class="chip degree">${esc(d)}</span>`);
  if (r.funding !== "Not stated") chips.push(`<span class="chip ${r.funding === "Fully funded" ? "funded" : ""}">${esc(r.funding)}</span>`);
  if (left !== null) {
    const cls = expired ? "passed" : left <= 14 ? "urgent" : "due";
    const label = expired ? `Deadline passed (${fmtDate(r.deadline)})` : `Deadline ${fmtDate(r.deadline)} · ${left} day${left === 1 ? "" : "s"} left`;
    chips.push(`<span class="chip ${cls}">${esc(label)}</span>`);
  } else if (r.deadline_text) {
    chips.push(`<span class="chip">Deadline: ${esc(r.deadline_text)}</span>`);
  }
  if (r.start_term) chips.push(`<span class="chip">Start ${esc(r.start_term)}</span>`);

  const where = [field(r, "university", r.university), field(r, "lab", r.lab), field(r, "country", r.country)].filter(Boolean).join(" · ");
  const post = safeUrl(r.post_url), profile = safeUrl(r.profile_url);
  const extra = r.links.filter((l) => l.url !== r.post_url && safeUrl(l.url))
    .map((l, i) => `<a class="btn secondary" href="${esc(l.url)}" target="_blank" rel="noopener">Source ${i + 2} ↗</a>`).join("");
  const sourceName = { linkedin: "LinkedIn search", x: "X search", web: "Web search", alert: "Google Alert", feed: "Feed" }[r.source] || r.source;
  const st = statuses[r.id] || "";
  const sbtn = (val, label) => `<button type="button" data-id="${esc(r.id)}" data-status="${val}" aria-pressed="${st === val}">${label}</button>`;

  return `<article class="card${isNew(r) ? " is-new" : ""}${expired ? " expired" : ""}">
    <div class="score ${scoreCls}" title="Match with your profile (0-100)">${r.relevance}<small>match</small></div>
    <div class="body">
      <div class="chips">${chips.join("")}</div>
      <h2>${esc(r.poster_name || "Unknown poster")}${r.role ? ` <span class="role">· ${field(r, "role", r.role)}</span>` : ""}</h2>
      ${where ? `<div class="where">${where}</div>` : ""}
      ${r.summary ? `<p class="summary">${esc(r.summary)}</p>` : ""}
      ${r.relevance_reason ? `<p class="why"><b>Why it fits:</b> ${esc(r.relevance_reason)}</p>` : ""}
      ${r.research_areas.length ? `<div class="areas">${r.research_areas.map((a) => `<span class="area">${esc(a)}</span>`).join("")}</div>` : ""}
      <div class="meta">${r.post_date ? `Posted ${fmtDate(r.post_date)} · ` : ""}Found ${fmtDate(r.first_seen)} · via ${esc(sourceName)}</div>
      <div class="actions">
        ${post ? `<a class="btn" href="${esc(post)}" target="_blank" rel="noopener">Open post ↗</a>` : ""}
        ${profile ? `<a class="btn secondary" href="${esc(profile)}" target="_blank" rel="noopener">Profile ↗</a>` : ""}
        ${extra}
        <span class="status-btns">${sbtn("interested", "★ Interested")}${sbtn("applied", "✓ Applied")}${sbtn("hidden", "Hide")}</span>
      </div>
    </div>
  </article>`;
}

function renderHeader() {
  const last = runs[runs.length - 1];
  $("updated").textContent = last ? `Updated ${ago(last.at)} · updates every morning (Bangladesh time)` : "Waiting for the first update";
  const open = data.filter((r) => statuses[r.id] !== "hidden");
  const fresh = open.filter(isNew).length;
  const soon = open.filter((r) => { const d = daysLeft(r.deadline); return d !== null && d >= 0 && d <= 30; }).length;
  const strong = open.filter((r) => r.relevance >= 75 && (!r.country || TARGET.includes(r.country))).length;
  $("stats").innerHTML = [
    `<span class="stat new"><b>${fresh}</b>new</span>`,
    `<span class="stat"><b>${strong}</b>strong matches (75+)</span>`,
    `<span class="stat"><b>${soon}</b>deadlines in 30 days</span>`,
    `<span class="stat"><b>${data.length}</b>total tracked</span>`,
  ].join("");
  const warn = last && last.errors && last.errors.find((e) => /claude error|serper error|not set/i.test(e));
  $("runWarning").hidden = !warn;
  if (warn) $("runWarning").textContent = `Last update had a problem: ${warn.slice(0, 220)}`;
}

function render() {
  renderHeader();
  const rows = data.filter(matches).sort(sorter);
  $("resultCount").textContent = `${rows.length} shown`;
  $("list").innerHTML = rows.length
    ? rows.map(card).join("")
    : `<div class="empty">${data.length ? "No opportunities match these filters. Try lowering the minimum match or choosing “All countries”." : "No opportunities yet. The tracker updates once a day; new posts will appear here."}</div>`;
}

function bind() {
  const update = () => { store.set("filters", filters); render(); };
  $("f-q").addEventListener("input", (e) => { filters.q = e.target.value.trim(); update(); });
  for (const k of ["country", "degree", "funding", "area", "university", "deadline", "status", "sort"]) {
    $("f-" + k).addEventListener("change", (e) => { filters[k] = e.target.value; update(); });
  }
  $("f-min").addEventListener("input", (e) => { filters.min = Number(e.target.value); $("f-min-out").textContent = filters.min; update(); });
  $("f-new").addEventListener("change", (e) => { filters.newOnly = e.target.checked; update(); });
  $("reset").addEventListener("click", () => { filters = { ...DEFAULTS }; syncControls(); update(); });
  $("markSeen").addEventListener("click", () => {
    seenCutoff = data.reduce((m, r) => (r.first_seen > m ? r.first_seen : m), seenCutoff);
    store.set("seenCutoff", seenCutoff);
    render();
  });
  $("list").addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-status]");
    if (!btn) return;
    const { id, status } = btn.dataset;
    if (statuses[id] === status) delete statuses[id]; else statuses[id] = status;
    store.set("statuses", statuses);
    render();
  });
  if (window.matchMedia("(max-width: 760px)").matches) $("filtersBox").open = false;
}

async function init() {
  if (!seenCutoff) {
    seenCutoff = new Date(Date.now() - 7 * DAY).toISOString().slice(0, 19);
    store.set("seenCutoff", seenCutoff);
  }
  try {
    const res = await fetch("data/tracker.json", { cache: "no-store" });
    const json = await res.json();
    data = json.opportunities || [];
    runs = json.runs || [];
  } catch (err) {
    $("updated").textContent = "Could not load data.";
  }
  buildOptions();
  syncControls();
  bind();
  render();
}

init();
