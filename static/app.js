const $ = (sel) => document.querySelector(sel);

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "request failed");
  }
  return res.json();
}

async function refreshMemory() {
  const data = await api("/api/memory");
  const tbody = $("#memTable tbody");
  tbody.innerHTML = "";
  for (const e of data.entries) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${e.phonetic_key}</td><td>${e.context_before ?? "<i>any</i>"}</td>
      <td>${e.canonical_term}</td><td>${e.category ?? ""}</td>
      <td>${e.observation_count}</td><td>${e.confidence.toFixed(2)}</td>`;
    tbody.appendChild(tr);
  }
}

async function refreshLog() {
  const data = await api("/api/observations");
  const tbody = $("#logTable tbody");
  tbody.innerHTML = "";
  for (const o of data.observations) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${o.id}</td><td>${o.heard_word}</td><td>${o.corrected_word}</td>
      <td>${o.context_before ?? ""}</td><td>${o.category ?? ""}</td><td>${o.source}</td>
      <td>${o.created_at.split("T")[0]}</td>`;
    tbody.appendChild(tr);
  }
}

$("#obsForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = Object.fromEntries(fd.entries());
  if (!payload.context_before) delete payload.context_before;
  if (!payload.category) delete payload.category;
  try {
    const result = await api("/api/observations", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    $("#obsResult").textContent = "Learned: " + JSON.stringify(result.entry);
    e.target.reset();
    refreshMemory();
    refreshLog();
  } catch (err) {
    $("#obsResult").textContent = "Error: " + err.message;
  }
});

$("#resolveForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const payload = Object.fromEntries(fd.entries());
  if (!payload.asr_text) delete payload.asr_text;
  const result = await api("/api/resolve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const box = $("#resolveResult");
  box.innerHTML = `
    <div class="output-line">${result.memory_aware_text}</div>
    <div class="token-trace">${result.trace
      .map((t) => `<span class="tok ${t.decision}" title="${t.reason.replace(/"/g, "&quot;")}">${t.output}</span>`)
      .join("")}</div>
    <div class="trace-list">${result.trace
      .map((t) => `<div><b>${t.token}</b> → <i>${t.decision}</i>: ${t.reason}</div>`)
      .join("")}</div>
  `;
});

$("#resetBtn").addEventListener("click", async () => {
  if (!confirm("Wipe all learned memory and observations?")) return;
  await api("/api/reset", { method: "POST" });
  refreshMemory();
  refreshLog();
  $("#resolveResult").innerHTML = "";
  $("#obsResult").textContent = "";
});

$("#refreshMemBtn").addEventListener("click", refreshMemory);
$("#refreshLogBtn").addEventListener("click", refreshLog);

refreshMemory();
refreshLog();
