"use strict";
// Minimal, dependency-free UI over the REST API. Every call sends the identity headers.
const $ = (s, el = document) => el.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const state = { tenant: null, offset: 0, limit: 25, event: null, assessment: null, tenants: [] };

function headers(scopeOverride) {
  return { "Content-Type": "application/json", "X-Actor": $("#actor").value.trim() || "demo-reviewer",
           "X-Tenant-Scope": scopeOverride || $("#tenant").value, "X-Roles": $("#roles").value };
}
async function api(path, opts = {}, scopeOverride) {
  const res = await fetch(path, { ...opts, headers: { ...headers(scopeOverride), ...(opts.headers || {}) } });
  const type = res.headers.get("content-type") || "";
  const body = type.includes("json") ? await res.json() : await res.text();
  if (!res.ok) { const err = new Error((body && body.title) ? `${res.status} ${body.title}: ${body.detail}` : `${res.status}`);
                 err.status = res.status; err.body = body; throw err; }
  return { status: res.status, body };
}
function toast(msg, isErr) {
  const d = document.createElement("div"); d.textContent = msg; if (isErr) d.className = "err";
  $("#toast").appendChild(d); setTimeout(() => d.remove(), 6000);
}
function pillFor(status) {
  if (!status) return '<span class="pill">not assessed</span>';
  const cls = status === "READY_FOR_QA_REVIEW" ? "ok" : status.startsWith("ABSTAIN") ? "warn" : "bad";
  return `<span class="pill ${cls}">${esc(status)}</span>`;
}

// ---------------- tabs ----------------
document.querySelectorAll(".tabs button").forEach((b) => b.addEventListener("click", () => {
  document.querySelectorAll(".tabs button").forEach((x) => x.classList.toggle("active", x === b));
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.id === `tab-${b.dataset.tab}`));
  if (b.dataset.tab === "audit") loadAudit();
  if (b.dataset.tab === "system") loadSystem();
}));

// ---------------- boot ----------------
async function boot() {
  try {
    const info = (await fetch("/api/v1/system/info").then((r) => r.json()));
    state.tenants = info.tenants || [];
    $("#tenant").innerHTML = state.tenants.map((t) => `<option ${t === "T-KAVERI" ? "selected" : ""}>${esc(t)}</option>`).join("");
    const ready = await fetch("/health/ready").then((r) => r.json());
    $("#ready").className = `pill ${ready.ready ? "ok" : "bad"}`;
    $("#ready").textContent = ready.ready ? "ready" : "not ready (load workbook)";
    await loadEvents();
  } catch (e) { toast(`Startup failed: ${e.message}`, true); }
}
$("#tenant").addEventListener("change", () => { state.offset = 0; loadEvents(); $("#detail").innerHTML = ""; });
$("#search").addEventListener("click", () => { state.offset = 0; loadEvents(); });
$("#q").addEventListener("keydown", (e) => { if (e.key === "Enter") { state.offset = 0; loadEvents(); } });
$("#prev").addEventListener("click", () => { state.offset = Math.max(0, state.offset - state.limit); loadEvents(); });
$("#next").addEventListener("click", () => { state.offset += state.limit; loadEvents(); });
$("#pick-brief")?.addEventListener("click", (e) => { e.preventDefault(); pickBrief(); });

async function pickBrief() {
  $("#tenant").value = "T-KAVERI"; $("#q").value = "EXC-107133"; state.offset = 0;
  await loadEvents(); openEvent("EXC-107133");
}

// ---------------- events ----------------
async function loadEvents() {
  const t = $("#tenant").value; if (!t) return;
  const q = encodeURIComponent($("#q").value.trim());
  try {
    const { body } = await api(`/api/v1/tenants/${t}/events?limit=${state.limit}&offset=${state.offset}${q ? `&q=${q}` : ""}`);
    $("#event-count").textContent = `${body.total} events for ${t} · showing ${body.offset + 1}–${Math.min(body.offset + body.limit, body.total)}`;
    $("#events tbody").innerHTML = body.items.map((e) => `<tr data-id="${esc(e.event_id)}">
      <td><b>${esc(e.event_id)}</b></td><td>${esc(e.alert_ts_utc)}</td><td>${esc(e.product_ref_as_received)}</td>
      <td>${esc(e.max_temp_c)}</td><td>${esc(e.min_temp_c)}</td><td>${pillFor(e.latest_assessment?.status)}</td></tr>`).join("");
    document.querySelectorAll("#events tbody tr").forEach((tr) => tr.addEventListener("click", () => openEvent(tr.dataset.id)));
  } catch (e) { toast(e.message, true); }
}

async function openEvent(id) {
  state.event = id;
  document.querySelectorAll("#events tbody tr").forEach((tr) => tr.classList.toggle("sel", tr.dataset.id === id));
  const t = $("#tenant").value;
  try {
    const { body } = await api(`/api/v1/tenants/${t}/events/${id}`);
    const f = body.fields;
    $("#detail").innerHTML = `
      <h2>${esc(id)} <span class="muted">· ${esc(t)} · ${esc(body.source_ref)}</span></h2>
      <div class="cards">
        <div class="card"><h3>Alert as received</h3><table>
          ${["alert_ts_utc","excursion_start_utc","excursion_end_utc","duration_min","min_temp_c","max_temp_c","spec_text_as_received",
             "product_ref_as_received","origin_ref_as_received","dest_ref_as_received","carrier_ref_as_received","logger_vendor","logger_fw","shipment_ref"]
             .map((k) => `<tr><th>${esc(k)}</th><td>${esc(f[k])}</td></tr>`).join("")}</table>
          <p class="muted">Outcome columns (final disposition, reviewer, etc.) are never served or used.</p></div>
        <div class="card"><h3>Assess</h3>
          <div class="row"><button class="primary" data-cut="alert">As known at alert time</button>
            <button data-cut="extract">As known at pack extract (2026-09-14)</button></div>
          <div class="row"><input id="cut" type="text" placeholder="or ISO cutoff e.g. 2026-08-01T00:00:00Z">
            <select id="mode"><option>RECONSTRUCTED</option><option>STRICT</option></select><button data-cut="custom">Assess</button></div>
          <div class="row"><button id="history">Assessment history</button>
            <button id="cross" class="danger">Try reading this as another tenant</button></div>
          <div id="side"></div></div>
      </div>
      <div id="result"></div>`;
    document.querySelectorAll("[data-cut]").forEach((b) => b.addEventListener("click", () => {
      const cut = b.dataset.cut === "custom" ? $("#cut").value.trim() : b.dataset.cut; assess(cut || "alert", $("#mode").value);
    }));
    $("#history").addEventListener("click", showHistory);
    $("#cross").addEventListener("click", crossTenant);
  } catch (e) { $("#detail").innerHTML = `<pre>${esc(JSON.stringify(e.body, null, 2))}</pre>`; }
}

async function assess(cutoff, mode) {
  const t = $("#tenant").value;
  try {
    const { status, body } = await api(`/api/v1/tenants/${t}/events/${state.event}/assessments`,
      { method: "POST", body: JSON.stringify({ knowledge_cutoff: cutoff, mode }) });
    toast(`${status === 201 ? "Stored new" : "Already stored (idempotent)"} ${body.assessment_id}`);
    state.assessment = body.assessment; renderAssessment(body.assessment); loadEvents();
  } catch (e) { toast(e.message, true); }
}

function renderAssessment(a) {
  const ent = a.entities, ev = a.evidence, st = ev.stability, nt = a.notification_track;
  const sopRows = (ev.sop_origin || []).map((s) => `<tr><td>${esc(s.doc_id)}</td><td>${pillFor(s.status === "SELECTED" ? "READY_FOR_QA_REVIEW" : s.status)}</td><td>${esc((s.in_force || []).join(", "))}</td></tr>`).join("");
  const ref = st.referenced;
  $("#result").innerHTML = `
    <div class="card" style="margin-top:10px">
      <div class="row"><span class="pill status ${a.disposition_evidence_status === "READY_FOR_QA_REVIEW" ? "ok" : "warn"}">${esc(a.disposition_evidence_status)}</span>
        <span class="pill info">is_disposition: ${esc(a.is_disposition)}</span>
        <code>${esc(a.assessment_id)}</code> <span class="muted">knowledge cutoff ${esc(a.time_semantics.knowledge_cutoff)}</span></div>
      <div class="chips">${(a.blocking_reasons || []).map((b) => `<span class="pill bad">${esc(b)}</span>`).join("") || '<span class="muted">no blocking reasons</span>'}</div>
      <div class="row"><button class="primary" id="export">Export evidence package</button><button id="verify">Verify package</button>
        <button id="tamper" class="danger">Tamper with a copy</button><a id="zip" href="#">Download zip</a></div>
      <div id="pkg"></div>
    </div>
    <div class="cards">
      <div class="card wide"><h3>Which product / site / carrier?</h3><table><tr><th>Role</th><th>As received</th><th>Status</th><th>Resolved</th><th>Basis</th></tr>
        ${Object.entries(ent).map(([k, v]) => `<tr><td>${esc(k)}</td><td>${esc(v.input_value)}</td><td>${esc(v.status)}</td><td>${esc(v.resolved_id)}</td><td>${esc(v.basis)}</td></tr>`).join("")}</table></div>
      <div class="card"><h3>Which SOP revision was in force (origin)?</h3><table><tr><th>Doc</th><th>Status</th><th>In force</th></tr>${sopRows || "<tr><td colspan=3 class=muted>none found</td></tr>"}</table></div>
      <div class="card"><h3>Which stability study applies?</h3><p>Status: <b>${esc(st.status)}</b></p>
        ${ref ? `<p>Referenced <b>${esc(ref.study_ref)}</b>: admissible <b>${esc(ref.admissible)}</b><br><span class="muted">${esc((ref.rejection_reasons || []).join("; "))}</span></p>` : ""}
        ${(st.unreferenced_candidates || []).map((c) => `<p>Candidate <b>${esc(c.study_ref)}</b>: admissible ${esc(c.admissible)} <span class="muted">${esc((c.rejection_reasons || []).join("; "))}</span></p>`).join("")}</div>
      <div class="card"><h3>Regulatory clock (independent)</h3><p>${esc(nt.status)}<br>Clock start <b>${esc(nt.clock_start_utc)}</b><br>Due if notifiable <b>${esc(nt.due_at_utc ?? "not computable: escalate")}</b><br>
        <span class="muted">${esc(nt.clock_basis)}; paused by evidence waits: ${esc(nt.paused_by_evidence_waits)}</span></p></div>
      <div class="card"><h3>Required human actions</h3><ol>${a.required_human_actions.map((h) => `<li><span class="sev-${esc(h.severity)}">${esc(h.action)}</span> <span class="muted">(${esc(h.because)})</span></li>`).join("")}</ol></div>
      <div class="card"><h3>Manifest (what produced this)</h3><table>
        <tr><th>kernel</th><td>${esc(a.manifest.kernel_version)} · ${esc(a.manifest.ruleset_version)}</td></tr>
        <tr><th>code sha256</th><td><code>${esc(a.manifest.code_sha256.slice(0, 16))}…</code></td></tr>
        <tr><th>model</th><td>${esc(a.manifest.model.route)}: ${esc(a.manifest.model.reason)}</td></tr>
        <tr><th>cited versions</th><td>${a.manifest.cited_source_versions.length}</td></tr></table></div>
    </div>
    <div class="card" style="margin-top:10px"><h3>All findings (${a.findings.length})</h3><table><tr><th>Severity</th><th>Code</th><th>Dimension</th><th>Message</th></tr>
      ${a.findings.map((f) => `<tr><td class="sev-${esc(f.severity)}">${esc(f.severity)}</td><td><code>${esc(f.code)}</code></td><td>${esc(f.dimension)}</td><td>${esc(f.message)}</td></tr>`).join("")}</table></div>
    <details class="card"><summary>Raw assessment JSON</summary><pre>${esc(JSON.stringify(a, null, 2))}</pre></details>`;
  const id = a.assessment_id;
  $("#export").addEventListener("click", async () => {
    try { const { body } = await api(`/api/v1/assessments/${id}/package`, { method: "POST" });
      $("#pkg").innerHTML = `<p>${pillFor(body.verification.ok ? "READY_FOR_QA_REVIEW" : "FAILED")} digest <code>${esc(body.manifest.package_digest)}</code></p>
        <pre>${esc(JSON.stringify(body.manifest.files_sha256, null, 2))}</pre>`; } catch (e) { toast(e.message, true); } });
  $("#verify").addEventListener("click", async () => {
    try { const { body } = await api(`/api/v1/assessments/${id}/package/verify`);
      $("#pkg").innerHTML = `<p>Verification: <b>${body.ok ? "OK" : "FAILED"}</b> ${esc(body.problems.join(", "))}</p>`; } catch (e) { toast(e.message, true); } });
  $("#tamper").addEventListener("click", async () => {
    try { const { body } = await api(`/api/v1/assessments/${id}/package/tamper-demo`, { method: "POST" });
      $("#pkg").innerHTML = `<p>Original: <b>${body.original.ok ? "OK" : "FAILED"}</b> · Tampered copy: <b class="sev-BLOCKING">${body.tampered_copy.ok ? "OK" : "FAILED"}</b>
        (${esc(body.tampered_copy.problems.join(", "))})<br><span class="muted">${esc(body.edit)}</span></p>`; } catch (e) { toast(e.message, true); } });
  $("#zip").addEventListener("click", async (e) => {
    e.preventDefault();
    const res = await fetch(`/api/v1/assessments/${id}/package.zip`, { headers: headers() });
    if (!res.ok) { toast(`download failed ${res.status}`, true); return; }
    const url = URL.createObjectURL(await res.blob()); const a2 = document.createElement("a");
    a2.href = url; a2.download = `${id}.zip`; a2.click(); URL.revokeObjectURL(url);
  });
}

async function showHistory() {
  const t = $("#tenant").value;
  try { const { body } = await api(`/api/v1/tenants/${t}/events/${state.event}/assessments`);
    $("#side").innerHTML = `<table><tr><th>Assessment</th><th>Cutoff</th><th>Supersedes</th><th>Status</th></tr>${body.map((h) =>
      `<tr><td><code>${esc(h.assessment_id)}</code></td><td>${esc(h.knowledge_cutoff)}</td><td><code>${esc(h.supersedes ?? "")}</code></td><td>${pillFor(h.status)}</td></tr>`).join("")}</table>`;
  } catch (e) { toast(e.message, true); }
}

async function crossTenant() {
  const mine = $("#tenant").value; const other = state.tenants.find((x) => x !== mine);
  try { await api(`/api/v1/tenants/${mine}/events/${state.event}`, {}, other); toast("UNEXPECTED: read allowed", true); }
  catch (e) { $("#side").innerHTML = `<p><b>Caller scoped to ${esc(other)} asked for ${esc(mine)} data →</b></p><pre>${esc(JSON.stringify(e.body, null, 2))}</pre>
      <p class="muted">The refusal is written to the audit trail (tab 3).</p>`; }
}

// ---------------- obligations ----------------
const NEXT = { OPEN_UNDETERMINED: ["NOTIFIABLE_CONFIRMED", "CLOSED_NOT_NOTIFIABLE", "SUBMISSION_QUEUED"], NOTIFIABLE_CONFIRMED: ["SUBMISSION_QUEUED"],
  SUBMISSION_QUEUED: ["SUBMITTED_AWAITING_ACK", "DELIVERY_FAILED"], DELIVERY_FAILED: ["SUBMISSION_QUEUED"], SUBMITTED_AWAITING_ACK: ["ACKNOWLEDGED", "DELIVERY_FAILED"] };
$("#load-obl").addEventListener("click", loadObligations);
async function loadObligations() {
  const t = $("#tenant").value, asof = encodeURIComponent($("#asof").value.trim()), m = $("#margin").value, risk = $("#only-risk").checked;
  const recv = $("#recv").value ? `&received_within_hours=${$("#recv").value}` : "";
  const qs = `as_of=${asof}&margin_hours=${m}&only_at_risk=${risk}${recv}`;
  const url = $("#all-scope").checked ? `/api/v1/obligations/queue?${qs}` : `/api/v1/tenants/${t}/obligations?${qs}`;
  const scope = $("#all-scope").checked ? state.tenants.join(",") : undefined;
  try { const { body } = await api(url, {}, scope);
    $("#obl tbody").innerHTML = body.items.map((o) => `<tr><td>${esc(o.event_id)}</td><td>${esc(o.tenant_code)}</td><td>${esc(o.clock_start_utc)}</td>
      <td>${o.due_at_utc ? esc(o.due_at_utc) : '<span class="pill bad">not computable: escalate</span>'}</td>
      <td>${o.hours_remaining === null ? "" : o.breached ? `<span class="pill bad">${esc(o.hours_remaining)}</span>` : esc(o.hours_remaining)}</td>
      <td>${esc(o.state)}</td><td>${esc(o.version)}</td>
      <td>${(NEXT[o.state] || []).map((s) => `<button data-t="${esc(o.tenant_code)}" data-e="${esc(o.event_id)}" data-v="${o.version}" data-s="${s}">${esc(s)}</button>`).join(" ")}</td></tr>`).join("")
      || `<tr><td colspan=8 class=muted>nothing in the window</td></tr>`;
    document.querySelectorAll("#obl button[data-s]").forEach((b) => b.addEventListener("click", () => transition(b.dataset)));
  } catch (e) { toast(e.message, true); }
}
async function transition(d) {
  const note = d.s === "CLOSED_NOT_NOTIFIABLE" ? prompt("Rationale for the not-notifiable determination (required):") : "via UI";
  if (note === null) return;
  try { await api(`/api/v1/tenants/${d.t}/obligations/${d.e}/transitions`, { method: "POST",
      headers: { "Idempotency-Key": `${d.t}:${d.e}:v${d.v}:${d.s}` }, body: JSON.stringify({ to_state: d.s, expected_version: Number(d.v), note }) },
      $("#all-scope").checked ? state.tenants.join(",") : undefined);
    toast(`${d.e} → ${d.s}`); loadObligations();
  } catch (e) { toast(e.message, true); }
}

// ---------------- audit & system ----------------
$("#load-audit").addEventListener("click", loadAudit);
async function loadAudit() {
  try { const { body } = await api(`/api/v1/tenants/${$("#tenant").value}/audit?limit=200`);
    $("#audit tbody").innerHTML = body.slice().reverse().map((a) => `<tr><td>${a.seq}</td><td>${esc(a.at)}</td><td>${esc(a.actor)}</td><td>${esc(a.action)}</td>
      <td><code>${esc(a.target)}</code></td><td>${a.outcome === "DENIED" ? '<span class="pill bad">DENIED</span>' : esc(a.outcome)}</td></tr>`).join("");
  } catch (e) { toast(e.message, true); }
}
$("#load-sys").addEventListener("click", loadSystem);
async function loadSystem() {
  const [ready, info] = await Promise.all([fetch("/health/ready").then((r) => r.json()), fetch("/api/v1/system/info").then((r) => r.json())]);
  $("#sys").textContent = JSON.stringify({ readiness: ready, info }, null, 2);
}
boot();
