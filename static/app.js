(() => {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const textEl = $("#text");
  const outEl = $("#out");
  const markedWrap = $("#marked-wrap");
  const markedEl = $("#marked");
  const legendEl = $("#legend");
  const analyzeBtn = $("#analyze");
  let lastResult = null;

  const esc = (s) =>
    String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : s);

  /* ------------------------------------------------------------ views */
  const VIEWS = ["welcome", "home", "analyzer", "live", "compare", "pipeline", "how", "evaluation", "about"];
  let evalLoaded = false;
  let datasetLoaded = false;

  function showView(name) {
    if (!VIEWS.includes(name)) name = "home";
    VIEWS.forEach((v) => {
      $("#view-" + v).hidden = v !== name;
    });
    document.body.classList.toggle("on-welcome", name === "welcome");
    document.querySelectorAll("#nav a").forEach((a) => {
      if (a.dataset.view === name) a.setAttribute("aria-current", "page");
      else a.removeAttribute("aria-current");
    });
    if (name === "evaluation") {
      if (!evalLoaded) loadEvaluation();
      if (!datasetLoaded) loadDataset();
    }
    window.scrollTo(0, 0);
  }
  function routeFromHash() {
    showView(location.hash.replace("#", "") || "home");
  }
  window.addEventListener("hashchange", routeFromHash);

  /* ------------------------------------------------------------ marked-up text */
  const PRIORITY = {
    symptom: 1, negated: 1, uncertain: 1, history: 1, other: 1,
    trigger: 2, duration: 3, severity: 4, location: 5, trend: 6, onset: 6, frequency: 6,
    quality: 7, medication: 8, condition: 8, context: 8,
  };
  const LABEL_NAMES = {
    symptom: "Symptom", negated: "Not present", uncertain: "Unsure", history: "Past episode", other: "Someone else",
    duration: "Duration", severity: "Severity", trend: "Course", onset: "Course", frequency: "Course",
    trigger: "Trigger", location: "Location", quality: "Feels like",
    medication: "Background", condition: "Background", context: "Background",
  };
  const LEGEND_ORDER = ["symptom", "negated", "uncertain", "history", "other", "duration", "severity", "trend", "trigger", "location", "quality", "context"];

  function renderMarked(text, highlights) {
    const cps = Array.from(text); // Python offsets count code points
    const n = cps.length;
    const owner = new Array(n).fill(-1);
    highlights.forEach((h, idx) => {
      for (let i = h.start; i < Math.min(h.end, n); i++) {
        if (owner[i] === -1 || PRIORITY[h.label] < PRIORITY[highlights[owner[i]].label]) owner[i] = idx;
      }
    });
    let html = "";
    let i = 0;
    let k = 0;
    while (i < n) {
      const o = owner[i];
      let j = i;
      while (j < n && owner[j] === o) j++;
      const seg = esc(cps.slice(i, j).join(""));
      if (o === -1) {
        html += seg;
      } else {
        const h = highlights[o];
        const title = LABEL_NAMES[h.label] + (h.symptom && h.label !== "symptom" ? " · " + h.symptom : "");
        html += `<mark class="hl hl-${h.label}" data-sym="${esc(h.symptom || "")}" style="--i:${k++}" title="${esc(title)}">${seg}</mark>`;
      }
      i = j;
    }
    markedEl.innerHTML = html;

    const present = new Set(owner.filter((o) => o >= 0).map((o) => highlights[o].label));
    const seen = new Set();
    legendEl.innerHTML = LEGEND_ORDER.filter((l) => {
      const name = LABEL_NAMES[l];
      const group = l === "trend" ? ["trend", "onset", "frequency"] : l === "context" ? ["context", "medication", "condition"] : [l];
      if (!group.some((g) => present.has(g)) || seen.has(name)) return false;
      seen.add(name);
      return true;
    })
      .map((l) => `<li><span class="swatch hl-${l}"></span>${esc(LABEL_NAMES[l])}</li>`)
      .join("");
    markedWrap.hidden = false;
  }

  /* ------------------------------------------------------------ results */
  const LEVELS = {
    routine: ["Routine review", "No red flags found in the text."],
    attention: ["Needs the doctor's attention", "A symptom is described as severe."],
    urgent: ["See a doctor soon", "Red flags found in the text."],
    emergency: ["Seek urgent care", "Serious warning signs are mentioned."],
  };

  function meter(score) {
    return `<span class="meter" aria-hidden="true">${[1, 2, 3].map((i) => `<i class="${i <= score ? "on" : ""}"></i>`).join("")}</span>`;
  }

  function rowHtml(s, negated) {
    const dur = s.duration
      ? `${esc(s.duration.text)}${s.duration.approx && /\d/.test(s.duration.text) === false ? `<small class="approx">~${esc(s.duration.approx)}</small>` : ""}`
      : '<span class="dash">—</span>';
    const sev = s.severity
      ? `<span class="sev">${meter(s.severity.score)}${esc(cap(s.severity.label))}</span>${
          s.severity.source !== "word" ? `<small class="muted"> (${esc({ scale: "pain scale", temperature: "from temperature", intensifier: "from wording" }[s.severity.source] || s.severity.source)})</small>` : ""
        }`
      : '<span class="dash">—</span>';
    const course = [];
    if (s.trend) course.push(`<span class="pill course">${esc(s.trend.label)}</span>`);
    if (s.onset) course.push(`<span class="pill course">${esc(s.onset.label)} onset</span>`);
    if (s.frequency) course.push(`<span class="pill course">${esc(s.frequency.text)}</span>`);
    const details = [];
    if (s.temperature) details.push(`<span class="pill quality">${esc(s.temperature.value)}°${esc(s.temperature.unit)}</span>`);
    s.quality.forEach((q) => details.push(`<span class="pill quality">${esc(q.label)}</span>`));
    if (s.location && !s.name.includes(s.location.text)) details.push(`<span class="pill location">${esc(s.location.text)}</span>`);
    if (s.radiates_to) details.push(`<span class="pill location">radiates to ${esc(s.radiates_to.text)}</span>`);
    s.triggers.forEach((t) => details.push(`<span class="pill trigger">${esc(t.label)}</span>`));
    const sub = [s.system];
    if (s.method === "fuzzy") sub.push("spelling matched");
    if (s.method === "inferred") sub.push("inferred from temperature");
    if (negated && s.reason) sub.push(s.reason);
    return `<tr class="${negated ? "neg" : ""}" data-sym="${esc(s.name)}" tabindex="0">
      <td class="sym"><span class="name">${esc(cap(s.name))}</span><small>${esc(sub.join(" · "))}</small></td>
      <td>${negated ? '<span class="dash">—</span>' : dur}</td>
      <td>${negated ? '<span class="dash">—</span>' : sev}</td>
      <td>${course.join("") || '<span class="dash">—</span>'}</td>
      <td>${details.join("") || '<span class="dash">—</span>'}</td>
    </tr>`;
  }

  function tableHtml(symptoms) {
    const groups = [
      ["Present", (s) => s.subject === "patient" && s.status === "present", false],
      ["Possible", (s) => s.subject === "patient" && s.status === "uncertain", false],
      ["Past episode", (s) => s.subject === "patient" && s.status === "history", false],
      ["Denied or resolved", (s) => s.subject === "patient" && (s.status === "absent" || s.status === "resolved"), true],
      ["Reported for someone else", (s) => s.subject !== "patient", false],
    ];
    let body = "";
    groups.forEach(([title, test, neg]) => {
      const rows = symptoms.filter(test);
      if (!rows.length) return;
      body += `<tr class="group"><th colspan="5" scope="colgroup">${esc(title)}${
        title === "Reported for someone else" ? ` (${esc([...new Set(rows.map((r) => r.subject))].join(", "))})` : ""
      }</th></tr>`;
      body += rows.map((r) => rowHtml(r, neg)).join("");
    });
    if (!body) return '<p class="muted">No symptoms were found in this text.</p>';
    return `<div class="table-wrap"><table>
      <thead><tr><th scope="col">Symptom</th><th scope="col">Since / for</th><th scope="col">Severity</th><th scope="col">Course</th><th scope="col">Details</th></tr></thead>
      <tbody>${body}</tbody></table></div>`;
  }

  function traceHtml(r) {
    const rows = r.symptoms
      .map(
        (s) =>
          `<tr><td>${esc(cap(s.name))}</td><td>${esc(s.status)}${s.reason ? " — " + esc(s.reason) : ""}</td><td>${esc(s.method)}</td><td>${Math.round(s.confidence * 100)}%</td></tr>`
      )
      .join("");
    const toks = r.tokens
      .slice(0, 120)
      .map((t) => `<span class="tok">${esc(t.text)}<sub>${t.sent + 1}.${t.clause + 1}</sub></span>`)
      .join("");
    const unl = r.unlinked_details.length
      ? `<h3>Details that could not be linked to a symptom</h3><p class="unlinked">${r.unlinked_details.map((u) => `“${esc(u.text)}” (${esc(u.kind)})`).join(", ")}</p>`
      : "";
    return `<details class="trace card trace-card">
      <summary>How the engine read this text</summary>
      <div class="trace-body">
        <h3>Decisions</h3>
        <div class="table-wrap"><table><thead><tr><th>Symptom</th><th>Status and reason</th><th>Matched by</th><th>Confidence</th></tr></thead><tbody>${rows || '<tr><td colspan="4" class="muted">Nothing found.</td></tr>'}</tbody></table></div>
        <h3>Tokens (sentence.clause)</h3>
        <div class="tokens">${toks}</div>
        ${unl}
      </div></details>`;
  }

  function renderTrace(r) {
    const slot = $("#trace-slot");
    if (slot) slot.innerHTML = traceHtml(r);
  }

  function render(r) {
    lastResult = r;
    const [title, fallback] = LEVELS[r.attention_level] || LEVELS.routine;
    const sub = r.red_flags.length ? r.red_flags[0].title : fallback;
    const flags = r.red_flags.length
      ? `<div class="block"><h3>Red flags</h3><ul class="flags">${r.red_flags
          .map(
            (f) =>
              `<li class="lvl-${esc(f.level)}"><span class="flag-title">${esc(f.title)}</span><span class="flag-level">${esc(LEVELS[f.level][0])}</span><p>${esc(f.advice)}</p></li>`
          )
          .join("")}</ul></div>`
      : "";
    const fups = r.follow_up_questions.length
      ? `<div class="block"><h3>Questions the doctor may want to ask</h3><ul class="followups">${r.follow_up_questions.map((q) => `<li>${esc(q)}</li>`).join("")}</ul></div>`
      : "";
    outEl.innerHTML = `<article class="result">
      <div class="verdict lvl-${esc(r.attention_level)}">
        <div class="verdict-text">${esc(title)}<small>${esc(sub)}</small></div>
        <div class="verdict-actions">
          <button class="btn small" type="button" id="copy-note">Copy note</button>
          <button class="btn small" type="button" id="dl-report">⤓ Download report</button>
        </div>
      </div>
      <div class="block"><h3>Note for the doctor<span class="lang-badge" title="Detected input language">${esc(r.language ? (r.language.label || r.language.name) : "English")}</span></h3><p class="note">${esc(r.summary)}</p></div>
      ${flags}
      <div class="block"><h3>Structured symptoms</h3>${tableHtml(r.symptoms)}</div>
      ${fups}
    </article>`;
    renderMarked(r.text, r.highlights);
    renderTrace(r);
    $("#copy-note").addEventListener("click", copyNote);
    $("#dl-report").addEventListener("click", downloadReport);
  }

  function showError(msg) {
    outEl.innerHTML = `<div class="error" role="alert"><strong>Could not analyze the text.</strong> ${esc(msg)}</div>`;
  }

  /* ------------------------------------------------------------ actions */
  async function analyze() {
    const text = textEl.value.trim();
    if (!text) {
      showError("Please write a few words about the symptoms first.");
      markedWrap.hidden = true;
      return;
    }
    analyzeBtn.disabled = true;
    analyzeBtn.textContent = "Analyzing…";
    try {
      const res = await fetch("/api/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Something went wrong.");
      render(data);
    } catch (err) {
      showError(err.message || "The server could not be reached. Check that app.py is still running.");
    } finally {
      analyzeBtn.disabled = false;
      analyzeBtn.textContent = "Analyze text";
    }
  }

  function noteText(r) {
    const lines = [r.summary, ""];
    r.symptoms.forEach((s) => lines.push(`- ${s.summary}${s.status !== "present" ? " [" + s.status + "]" : ""}${s.subject !== "patient" ? " [" + s.subject + "]" : ""}`));
    if (r.red_flags.length) {
      lines.push("", "Red flags:");
      r.red_flags.forEach((f) => lines.push(`- ${f.title}`));
    }
    lines.push("", "Generated by SymptoScribe from the patient's own words. Not a diagnosis.");
    return lines.join("\n");
  }

  async function copyNote() {
    const btn = $("#copy-note");
    const text = noteText(lastResult);
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      ta.remove();
    }
    btn.textContent = "Copied";
    setTimeout(() => (btn.textContent = "Copy note"), 1500);
  }

  function download(name, mime, content) {
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([content], { type: mime }));
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  }

  function downloadReport() {
    const dlg = $("#report-dialog");
    if (!$("#rd-date").value) $("#rd-date").value = new Date().toLocaleDateString("en-CA");   // today, yyyy-mm-dd
    if (typeof dlg.showModal === "function") dlg.showModal();
    else buildReport({});
  }

  async function buildReport(details) {
    const btn = $("#dl-report");
    const idle = "⤓ Download report";
    btn.disabled = true;
    btn.textContent = "Preparing PDF…";
    try {
      const res = await fetch("/api/report", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: lastResult.text, details }),
      });
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || "Could not build the report.");
      const stamp = new Date().toISOString().slice(0, 16).replace(/[-:T]/g, "");
      const a = document.createElement("a");
      a.href = URL.createObjectURL(await res.blob());
      a.download = `symptoscribe-report-${stamp}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      btn.textContent = "✓ Report downloaded";
    } catch (err) {
      btn.textContent = "Could not download";
    } finally {
      btn.disabled = false;
      setTimeout(() => (btn.textContent = idle), 1800);
    }
  }

  function bindReportDialog() {
    const dlg = $("#report-dialog");
    if (!dlg) return;
    const close = () => dlg.close();
    $("#report-x").addEventListener("click", close);
    dlg.addEventListener("click", (e) => { if (e.target === dlg) close(); });
    $("#rd-skip").addEventListener("click", () => { close(); buildReport({}); });
    $("#report-form").addEventListener("submit", (e) => {
      e.preventDefault();
      const details = {
        name: $("#rd-name").value, age: $("#rd-age").value, date: $("#rd-date").value, doctor: $("#rd-doctor").value,
      };
      close();
      buildReport(details);   // typed values stay in this page only; nothing is stored
    });
  }

  /* ------------------------------------------------------------ evaluation view */
  const pct = (x) => (x * 100).toFixed(1) + "%";

  function metricRow(name, m) {
    return `<tr><td>${esc(name)}</td><td>${pct(m.precision)}</td><td>${pct(m.recall)}</td><td>${pct(m.f1)}</td><td>${m.tp}</td><td>${m.fp}</td><td>${m.fn}</td></tr>`;
  }
  const metricHead = '<thead><tr><th>Task</th><th>Precision</th><th>Recall</th><th>F1</th><th>Correct</th><th>Extra</th><th>Missed</th></tr></thead>';

  async function loadDataset() {
    const body = $("#dataset-body");
    try {
      const res = await fetch("/api/dataset");
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || "Could not read the dataset.");
      datasetLoaded = true;
      const max = d.top_symptoms[0].count;
      body.innerHTML = `
        <div class="cards">
          <div class="metric"><div class="num">${d.texts.toLocaleString()}</div><div class="lab">patient descriptions read</div></div>
          <div class="metric"><div class="num">${pct(d.coverage)}</div><div class="lab">had at least one symptom found</div></div>
          <div class="metric"><div class="num">${d.avg_symptoms.toFixed(1)}</div><div class="lab">symptoms found per description</div></div>
          <div class="metric"><div class="num">${d.distinct_symptoms}</div><div class="lab">different symptoms recognised</div></div>
        </div>
        <p class="muted src">Data: <a href="${esc(d.source.url)}" target="_blank" rel="noopener">${esc(d.source.name)}</a> on Kaggle (${esc(d.source.author)}), ${d.labels} categories of 50 descriptions each. Coverage shows what the engine finds, not accuracy: the dataset has no marked answers.</p>

        <h2 class="plain">Most common symptoms found</h2>
        <div class="card bars">${d.top_symptoms.map((t) => `<div class="bar-row"><span class="bar-name">${esc(cap(t.name))}</span><span class="bar-track"><i style="width:${(t.count / max) * 100}%"></i></span><span class="bar-n">${t.count}</span></div>`).join("")}</div>

        <h2 class="plain">Red flags raised</h2>
        <p class="muted">${d.texts_with_red_flag} of ${d.texts.toLocaleString()} descriptions (${pct(d.texts_with_red_flag / d.texts)}) raised at least one flag.</p>
        <div class="card bars">${d.red_flags.map((f) => `<div class="bar-row"><span class="bar-name">${esc(f.title)}</span><span class="bar-track"><i style="width:${(f.count / d.red_flags[0].count) * 100}%"></i></span><span class="bar-n">${f.count}</span></div>`).join("")}</div>

        <h2 class="plain">Coverage by category</h2>
        <p class="muted">Sorted from weakest to strongest. The top symptoms found in each category are shown.</p>
        <div class="eval-table table-wrap"><table><thead><tr><th>Dataset category</th><th>Coverage</th><th>Top symptoms found</th></tr></thead><tbody>
          ${d.by_label.map((l) => `<tr><td>${esc(cap(l.label))}</td><td><span class="cov"><i style="width:${l.coverage * 100}%"></i></span> ${pct(l.coverage)}</td><td>${esc(l.top.join(", ") || "—")}</td></tr>`).join("")}
        </tbody></table></div>

        <h2 class="plain">Where nothing was found</h2>
        <p class="muted">${d.miss_count} descriptions had no symptom found, usually wording the lexicon does not know yet (for example <em>peeling</em> or <em>scales</em>). These are the next words to add. Showing the first ${d.misses.length}; click one to open it in the analyzer.</p>
        <div class="misses">${d.misses.map((m) => `<button type="button" class="miss" data-text="${esc(m.text)}"><small>${esc(cap(m.label))}</small>${esc(m.text)}</button>`).join("")}</div>
      `;
      body.querySelectorAll(".miss").forEach((b) => b.addEventListener("click", () => {
        textEl.value = b.dataset.text;
        $("#count").textContent = `${textEl.value.length} / 5000`;
        location.hash = "#analyzer";
        analyze();
      }));
    } catch (err) {
      body.innerHTML = `<div class="error" role="alert"><strong>Could not load the dataset.</strong> ${esc(err.message)}</div>`;
    }
  }

  async function loadEvaluation() {
    const body = $("#eval-body");
    try {
      const res = await fetch("/api/evaluation");
      const e = await res.json();
      if (!res.ok) throw new Error(e.error || "Evaluation failed.");
      evalLoaded = true;
      const slotNames = { duration: "Duration", severity: "Severity", trend: "Course (trend)", location: "Body location", triggers: "Triggers" };
      body.innerHTML = `
        <div class="cards">
          <div class="metric"><div class="num">${pct(e.overall.detection.f1)}</div><div class="lab">Symptom finding (F1)</div></div>
          <div class="metric"><div class="num">${pct(e.overall.assertion.f1)}</div><div class="lab">Finding and present / denied (F1)</div></div>
          <div class="metric"><div class="num">${pct(e.overall.slots_micro.f1)}</div><div class="lab">All details together (F1)</div></div>
          <div class="metric"><div class="num">${e.dataset.cases}</div><div class="lab">annotated texts, ${e.dataset.symptom_annotations} symptom annotations</div></div>
        </div>
        <h2 class="plain">Finding symptoms and their status</h2>
        <div class="eval-table table-wrap"><table>${metricHead}<tbody>
          ${metricRow("Symptom found", e.overall.detection)}
          ${metricRow("Symptom found with correct status", e.overall.assertion)}
        </tbody></table></div>
        <h2 class="plain">Extracting the details</h2>
        <div class="eval-table table-wrap"><table>${metricHead}<tbody>
          ${Object.entries(e.slots).map(([k, v]) => metricRow(slotNames[k] || k, v)).join("")}
        </tbody></table></div>
        <h2 class="plain">Development set and held-out set</h2>
        <div class="eval-table table-wrap"><table>${metricHead}<tbody>
          ${Object.entries(e.by_set).map(([k, v]) => metricRow(`${({ indic: "Hindi and Marathi", mixed: "Mixed languages", heldout: "Held-out" }[k] || cap(k))} (${v.cases} texts) — symptom and status`, v.assertion)).join("")}
        </tbody></table></div>
        <p class="muted">${esc(e.note)}</p>
        ${e.history && e.history.heldout_first_run ? `<p class="muted">First run on the held-out set: ${pct(e.history.heldout_first_run.found_and_status_f1)} F1 for symptom and status, before its errors were studied. First run on the challenge set: ${pct(e.history.challenge_first_run.found_and_status_f1)}.</p>` : ""}
        <h2 class="plain">Where it still goes wrong</h2>
        ${e.failures.length ? e.failures.map((f) => `<div class="fail"><strong>${esc(f.id)}</strong> — ${esc(f.kind)}<br><code>${esc(f.text)}</code><br>${esc(f.detail)}</div>`).join("") : "<p>No errors on the annotated texts.</p>"}
      `;
    } catch (err) {
      body.innerHTML = `<div class="error" role="alert"><strong>Could not load the evaluation.</strong> ${esc(err.message)}</div>`;
    }
  }

  /* ------------------------------------------------------------ linking text <-> table */
  function focusSym(sym, on) {
    if (!sym) return;
    document.querySelectorAll("[data-sym]").forEach((el) => {
      const match = el.dataset.sym === sym;
      el.classList.toggle("linked", on && match);
      el.classList.toggle("dimmed", on && !match);
    });
  }
  function bindLinking() {
    ["#marked", "#out"].forEach((sel) => {
      const root = $(sel);
      root.addEventListener("mouseover", (e) => { const t = e.target.closest("[data-sym]"); if (t) focusSym(t.dataset.sym, true); });
      root.addEventListener("mouseout", (e) => { const t = e.target.closest("[data-sym]"); if (t) focusSym(t.dataset.sym, false); });
      root.addEventListener("focusin", (e) => { const t = e.target.closest("[data-sym]"); if (t) focusSym(t.dataset.sym, true); });
      root.addEventListener("focusout", (e) => { const t = e.target.closest("[data-sym]"); if (t) focusSym(t.dataset.sym, false); });
    });
    $("#marked").addEventListener("click", (e) => {
      const t = e.target.closest("mark[data-sym]");
      const row = t && [...outEl.querySelectorAll("tr[data-sym]")].find((r) => r.dataset.sym === t.dataset.sym);
      if (!row) return;
      row.scrollIntoView({ behavior: "smooth", block: "center" });
      row.classList.remove("flash");
      void row.offsetWidth;
      row.classList.add("flash");
    });
  }

  /* ------------------------------------------------------------ live analysis + voice */
  let liveTimer = null;
  function bindLive() {
    textEl.addEventListener("input", () => {
      if (!$("#live").checked) return;
      clearTimeout(liveTimer);
      if (!textEl.value.trim()) return;
      liveTimer = setTimeout(analyze, 600);
    });
  }
  function bindMic() {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const mic = $("#mic");
    if (!SR) return;
    mic.hidden = false;
    $("#mic-opt").hidden = false;
    const rec = new SR();
    rec.continuous = true;
    rec.interimResults = false;
    rec.lang = "en-IN";
    let on = false;
    const set = (v) => {
      on = v;
      mic.setAttribute("aria-pressed", v);
      mic.classList.toggle("recording", v);
      mic.textContent = v ? "⏺ Listening… (click to stop)" : "🎤 Speak";
    };
    rec.onresult = (e) => {
      const chunk = Array.from(e.results).slice(e.resultIndex).map((r) => r[0].transcript).join(" ").trim();
      if (!chunk) return;
      textEl.value = (textEl.value.trim() + " " + chunk).trim();
      $("#count").textContent = `${textEl.value.length} / 5000`;
      analyze();
    };
    rec.onend = () => set(false);
    rec.onerror = () => set(false);
    mic.addEventListener("click", () => {
      if (on) rec.stop();
      else { try { rec.lang = $("#mic-lang").value; rec.start(); set(true); } catch { set(false); } }
    });
  }

  /* ------------------------------------------------------------ blobs follow the pointer */
  function bindBlobs() {
    const g = document.querySelector(".glow");
    if (g && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
      window.addEventListener("pointermove", (e) => {
        g.style.setProperty("--mx", `${(e.clientX / innerWidth - 0.5) * 120}px`);
      });
    }
    const toAnalyzer = () => setTimeout(() => textEl.focus({ preventScroll: true }), 50);
    $("#try-demo").addEventListener("click", toAnalyzer);
  }

  /* ------------------------------------------------------------ cursor-following hover glow */
  function bindSpotlight() {
    if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const SEL = ".card, .steps li, .metric, .result, .fail";
    const dot = $(".cursor-glow");
    let active = null;
    window.addEventListener("pointermove", (e) => {
      if (dot) dot.style.transform = `translate(${e.clientX}px, ${e.clientY}px)`;
      const el = e.target.closest ? e.target.closest(SEL) : null;
      if (active && active !== el) {
        active.style.removeProperty("--sx");
        active.style.removeProperty("--sy");
      }
      active = el;
      if (el) {
        const r = el.getBoundingClientRect();
        el.style.setProperty("--sx", `${e.clientX - r.left}px`);
        el.style.setProperty("--sy", `${e.clientY - r.top}px`);
      }
    }, { passive: true });
    document.addEventListener("pointerleave", () => dot && (dot.style.opacity = 0));
    document.addEventListener("pointerenter", () => dot && (dot.style.opacity = ""));
  }

  /* ------------------------------------------------------------ light / dark toggle */
  function bindTheme() {
    const btn = $("#theme-toggle");
    const root = document.documentElement;
    const sync = () => {
      const light = root.dataset.theme === "light";
      btn.setAttribute("aria-label", light ? "Switch to dark theme" : "Switch to light theme");
      btn.setAttribute("aria-pressed", light);
    };
    sync();
    btn.addEventListener("click", () => {
      const next = root.dataset.theme === "light" ? "dark" : "light";
      root.dataset.theme = next;
      try { localStorage.setItem("theme", next); } catch { /* private mode */ }
      sync();
    });
  }

  /* ------------------------------------------------------------ welcome page */
  function bindWelcome() {
    // every load or refresh starts on the welcome page
    if (location.hash !== "#welcome") history.replaceState(null, "", "#welcome");
  }

  /* ------------------------------------------------------------ examples dropdown */
  function closeDropdown() {
    const menu = $("#example-buttons"), tg = $("#dd-toggle");
    if (!menu || menu.hidden) return;
    menu.hidden = true;
    tg.setAttribute("aria-expanded", "false");
    $("#examples-dd").classList.remove("open", "drop-up");
  }

  function bindDropdown() {
    const tg = $("#dd-toggle"), menu = $("#example-buttons"), box = $("#examples-dd");
    if (tg.dataset.bound) return;
    tg.dataset.bound = "1";
    const items = () => [...menu.querySelectorAll(".dd-item")];
    function open() {
      menu.hidden = false;
      tg.setAttribute("aria-expanded", "true");
      box.classList.add("open");
      box.classList.toggle("drop-up", innerHeight - tg.getBoundingClientRect().bottom < 340 && tg.getBoundingClientRect().top > 340);
      items()[0] && items()[0].focus({ preventScroll: true });
    }
    tg.addEventListener("click", () => (menu.hidden ? open() : closeDropdown()));
    document.addEventListener("click", (e) => { if (!box.contains(e.target)) closeDropdown(); });
    box.addEventListener("keydown", (e) => {
      if (e.key === "Escape") { closeDropdown(); tg.focus(); return; }
      if (menu.hidden && (e.key === "ArrowDown") && e.target === tg) { e.preventDefault(); open(); return; }
      if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
      e.preventDefault();
      const list = items(), i = list.indexOf(document.activeElement);
      list[(i + (e.key === "ArrowDown" ? 1 : -1) + list.length) % list.length].focus();
    });
  }

  /* ------------------------------------------------------------ pipeline viewer */
  const STAGES = [
    { title: "Clean and tokenise", concept: "Tokenisation",
      what: "The text is cut into sentences and words (tokens). Every token remembers the exact character where it started, so later results can be highlighted on the original text." },
    { title: "Normalise spelling", concept: "Text normalisation",
      what: "Common slips and shortcuts are corrected before matching, for example fevar → fever and dont → don't. Hindi and Marathi words are mapped onto the words the lexicon knows." },
    { title: "Find the symptoms", concept: "Named entity recognition (lexicon)",
      what: "The tokens are matched against a lexicon of symptoms. The longest phrase wins, plurals are handled, and misspelt words are matched by edit distance." },
    { title: "Split into clauses", concept: "Shallow syntax",
      what: "Each sentence is divided into clauses at commas that separate ideas and at words like but. A clause decides which words can describe which symptom." },
    { title: "Decide the status of each symptom", concept: "Negation scope (NegEx-style)",
      what: "Every symptom is marked present, denied, unsure, resolved, a past episode or someone else's, by looking at the words around it, such as no, maybe or my mother." },
    { title: "Extract the details", concept: "Temporal and attribute extraction",
      what: "Durations, severity, course, triggers, body locations, quality and temperatures are picked out of the text. At this point they are not yet tied to a symptom." },
    { title: "Link details to symptoms", concept: "Attachment heuristics",
      what: "Each detail is attached to the symptom it describes: usually the nearest one, or all symptoms in a list when the detail comes last." },
    { title: "Safety checks and the note", concept: "Rules and template generation",
      what: "Simple red-flag rules check what should not wait, missing details become follow-up questions, and a template writes the note for the doctor. No disease is ever named." },
  ];
  const METHOD = { lexicon: "dictionary match", fuzzy: "spelling-tolerant match", plural: "plural form", pattern: "pain-in-body-part pattern", inferred: "inferred from temperature", coreference: "linked to an earlier pain" };
  const KIND_LABEL = { duration: "duration", severity: "severity", course: "course", location: "location", trigger: "trigger", quality: "feels like", temperature: "temperature" };
  const KIND_HL = { duration: "duration", severity: "severity", course: "trend", location: "location", trigger: "trigger", quality: "quality", temperature: "severity" };
  const STATUS_HL = { present: "symptom", absent: "negated", resolved: "negated", uncertain: "uncertain", history: "history" };
  const STATUS_NAME = { present: "Present", absent: "Denied", resolved: "Resolved", uncertain: "Possible", history: "Past episode" };
  const AUTO_MS = 5200;
  const pl = { data: null, step: 0, timer: null, auto: false };

  // text with marked spans (offsets count code points, like the engine)
  function spanHtml(text, spans) {
    return `<p class="pl-text">${spanInner(text, spans)}</p>`;
  }

  function spanInner(text, spans) {
    const cps = Array.from(text), n = cps.length;
    const owner = new Array(n).fill(-1);
    spans.forEach((h, idx) => {
      for (let i = h.start; i < Math.min(h.end, n); i++) {
        if (owner[i] === -1 || (PRIORITY[h.label] || 9) < (PRIORITY[spans[owner[i]].label] || 9)) owner[i] = idx;
      }
    });
    let html = "", i = 0, k = 0;
    while (i < n) {
      const o = owner[i];
      let j = i;
      while (j < n && owner[j] === o) j++;
      const seg = esc(cps.slice(i, j).join(""));
      html += o === -1 ? seg : `<mark class="hl hl-${spans[o].label}" style="--i:${k++}" title="${esc(spans[o].title || "")}">${seg}</mark>`;
      i = j;
    }
    return html;
  }

  const chip = (t, cls = "", i = 0) => `<span class="pl-chip ${cls}" style="--i:${i}">${t}</span>`;

  const STAGE_VIEW = [
    (d) => `<div class="pl-sentences">${d.sentences.map((s) => `
        <div class="pl-sent"><span class="pl-badge">Sentence ${s.index}</span>
          <div class="pl-chips">${d.tokens.filter((t) => t.sent === s.index - 1).map((t, i) => chip(`${esc(t.text)}<sub>${t.start}</sub>`, "", i)).join("")}</div>
        </div>`).join("")}</div>
      <p class="pl-note">Small numbers show where each token starts in the original text.</p>`,
    (d) => d.changes.length
      ? `<div class="pl-changes">${d.changes.map((c, i) => `<div class="pl-change" style="--i:${i}"><span class="from">${esc(c.text)}</span><span class="arrow">→</span><span class="to">${esc(c.norm)}</span></div>`).join("")}</div>
         <p class="pl-note">${d.changes.length} word${d.changes.length > 1 ? "s were" : " was"} rewritten. The highlights still point at what was typed.</p>`
      : `<p class="pl-empty">No spelling fixes were needed in this text.</p><p class="pl-note">Try a text with a slip such as <em>fevar</em> or <em>dont</em> to see this stage work.</p>`,
    (d) => spanHtml(d.text, d.symptoms.flatMap((s) => s.evidence.map((e) => ({ start: e.start, end: e.end, label: "symptom", title: s.name })))) +
      (d.symptoms.length ? `<div class="pl-list">${d.symptoms.map((s, i) => `<div class="pl-row" style="--i:${i}"><b>${esc(cap(s.name))}</b><span class="pl-tag">${esc(METHOD[s.method] || s.method)}</span><span class="pl-conf"><i style="width:${Math.round(s.confidence * 100)}%"></i></span><small>${Math.round(s.confidence * 100)}%</small></div>`).join("")}</div>` : '<p class="pl-empty">No symptoms were found in this text.</p>'),
    (d) => `<div class="pl-clauses">${d.clauses.map((c, i) => `<div class="pl-clause" style="--i:${i}"><span class="pl-badge">S${c.sentence} · C${c.clause}</span>${esc(c.text)}</div>`).join("")}</div>`,
    (d) => spanHtml(d.text, d.symptoms.flatMap((s) => s.evidence.map((e) => ({ start: e.start, end: e.end, label: s.subject === "patient" ? STATUS_HL[s.status] : "other", title: STATUS_NAME[s.status] })))) +
      (d.symptoms.length ? `<div class="pl-list">${d.symptoms.map((s, i) => `<div class="pl-row" style="--i:${i}"><b>${esc(cap(s.name))}</b><span class="pl-tag st-${s.status}">${esc(STATUS_NAME[s.status])}${s.subject !== "patient" ? " · " + esc(s.subject) : ""}</span><small>${esc(s.reason || (s.status === "present" ? "no negation or hedge nearby" : ""))}</small></div>`).join("")}</div>` : '<p class="pl-empty">Nothing to classify.</p>'),
    (d) => {
      const seen = new Set(), uniq = d.details.filter((x) => { const k = x.start + ":" + x.end + x.kind; return seen.has(k) ? false : seen.add(k); });
      return spanHtml(d.text, uniq.map((x) => ({ start: x.start, end: x.end, label: KIND_HL[x.kind], title: KIND_LABEL[x.kind] }))) +
        (uniq.length ? `<div class="pl-chips">${uniq.map((x, i) => chip(`<em>${esc(KIND_LABEL[x.kind])}</em> ${esc(x.text)}`, "k-" + x.kind, i)).join("")}</div>` : '<p class="pl-empty">No durations, severity words or other details were found.</p>');
    },
    (d) => `<div class="pl-links">${d.symptoms.map((s, i) => `<div class="pl-link" style="--i:${i}"><div class="pl-link-head"><b>${esc(cap(s.name))}</b><span class="pl-tag st-${s.status}">${esc(STATUS_NAME[s.status])}</span></div>${s.details.length ? `<div class="pl-chips">${s.details.map((x, j) => chip(`<em>${esc(KIND_LABEL[x.kind])}</em> ${esc(x.text)}`, "k-" + x.kind, j)).join("")}</div>` : '<small class="muted">no details attached</small>'}</div>`).join("") || '<p class="pl-empty">No symptoms to link.</p>'}</div>` +
      (d.unlinked.length ? `<p class="pl-note">Could not be linked to any symptom: ${d.unlinked.map((u) => `“${esc(u.text)}” (${esc(u.kind)})`).join(", ")}</p>` : ""),
    (d) => {
      const [title] = LEVELS[d.attention_level] || LEVELS.routine;
      return `<div class="pl-verdict lvl-${esc(d.attention_level)}"><span>⚑</span><b>${esc(title)}</b></div>
        <h4 class="pl-sub">Red flags</h4>${d.red_flags.length ? d.red_flags.map((f) => `<p class="pl-flag"><b>${esc(f.title)}</b> <small>${esc(LEVELS[f.level][0])}</small><br>${esc(f.advice)}</p>`).join("") : '<p class="pl-empty">No red flags found.</p>'}
        <h4 class="pl-sub">Note for the doctor</h4><p class="pl-summary">${esc(d.summary)}</p>
        ${d.follow_up_questions.length ? `<h4 class="pl-sub">Questions to ask next</h4><ul class="pl-questions">${d.follow_up_questions.slice(0, 4).map((q) => `<li>${esc(q)}</li>`).join("")}</ul>` : ""}`;
    },
  ];

  function stageSummary(i, d) {
    return [
      `${d.token_count} tokens in ${d.sentences.length} sentence${d.sentences.length > 1 ? "s" : ""}`,
      d.changes.length ? `${d.changes.length} word${d.changes.length > 1 ? "s" : ""} normalised` : "nothing needed fixing",
      `${d.symptoms.length} symptom${d.symptoms.length !== 1 ? "s" : ""} found`,
      `${d.clauses.length} clause${d.clauses.length !== 1 ? "s" : ""}`,
      `${d.symptoms.filter((s) => s.status === "absent" || s.status === "resolved").length} denied, ${d.symptoms.filter((s) => s.status === "present").length} present`,
      `${new Set(d.details.map((x) => x.start + ":" + x.end)).size} detail${d.details.length !== 1 ? "s" : ""} found`,
      `${d.details.length} link${d.details.length !== 1 ? "s" : ""} made`,
      `${d.red_flags.length} red flag${d.red_flags.length !== 1 ? "s" : ""}, note written`,
    ][i];
  }

  function showStage(i) {
    const d = pl.data;
    if (!d) return;
    pl.step = Math.max(0, Math.min(STAGES.length - 1, i));
    const st = STAGES[pl.step];
    $("#pl-steps").innerHTML = STAGES.map((s, k) => `<li><button type="button" class="${k === pl.step ? "active" : k < pl.step ? "done" : ""}" data-k="${k}" aria-label="Stage ${k + 1}: ${esc(s.title)}"><i>${k < pl.step ? "✓" : k + 1}</i><span>${esc(s.title)}</span></button></li>`).join("");
    $("#pl-card").innerHTML = `<div class="pl-head"><span class="pl-num">Step ${pl.step + 1} of ${STAGES.length}</span><span class="pl-concept">${esc(st.concept)}</span></div>
      <h3>${esc(st.title)}</h3><p class="pl-what">${esc(st.what)}</p>
      <div class="pl-visual" key="${pl.step}">${STAGE_VIEW[pl.step](d)}</div>
      <p class="pl-result">→ ${esc(stageSummary(pl.step, d))}</p>
      ${pl.auto && pl.step < STAGES.length - 1 ? `<div class="pl-progress" aria-hidden="true"><i style="animation-duration:${AUTO_MS}ms"></i></div>` : ""}`;
    $("#pl-prev").disabled = pl.step === 0;
    $("#pl-next").textContent = pl.step === STAGES.length - 1 ? "Start over ↺" : "Next step →";
    $("#pl-hint").textContent = pl.auto
      ? (pl.step < STAGES.length - 1 ? "Playing automatically. Click a stage, or press ← or → to take over." : "")
      : "Use the buttons, click a stage, or press ← and → to move between stages.";
    clearTimeout(pl.timer);
    pl.timer = null;
    if (pl.auto && pl.step < STAGES.length - 1) pl.timer = setTimeout(() => showStage(pl.step + 1), AUTO_MS);
    else if (pl.auto) pl.auto = false;
  }

  function stopAuto() {
    pl.auto = false;
    clearTimeout(pl.timer);
    pl.timer = null;
  }

  async function runPipeline() {
    const text = $("#pl-text").value.trim(), err = $("#pl-error");
    err.innerHTML = "";
    if (!text) { err.innerHTML = '<div class="error" role="alert"><strong>Please write a few words about the symptoms first.</strong></div>'; return; }
    const btn = $("#pl-run");
    btn.disabled = true;
    btn.textContent = "Running…";
    try {
      const res = await fetch("/api/pipeline", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || "Something went wrong.");
      stopAuto();
      pl.data = d;
      $("#pl-stage").hidden = false;
      pl.auto = true;                 // plays through the stages by itself
      showStage(0);
    } catch (e) {
      err.innerHTML = `<div class="error" role="alert"><strong>Could not run the pipeline.</strong> ${esc(e.message)}</div>`;
    } finally {
      btn.disabled = false;
      btn.textContent = "Run pipeline";
    }
  }

  function bindPipeline() {
    $("#pl-run").addEventListener("click", runPipeline);
    $("#pl-sample").addEventListener("click", () => { $("#pl-text").value = "Headace and fevar since sunday, no cough. I took paracetamol but the headache gets worse after eating."; runPipeline(); });
    $("#pl-use").addEventListener("click", () => { $("#pl-text").value = textEl.value; if (textEl.value.trim()) runPipeline(); });
    $("#pl-prev").addEventListener("click", () => { stopAuto(); showStage(pl.step - 1); });
    $("#pl-next").addEventListener("click", () => {
      stopAuto();
      if (pl.step === STAGES.length - 1) { pl.auto = true; showStage(0); }   // "Start over" plays again
      else showStage(pl.step + 1);
    });
    $("#pl-steps").addEventListener("click", (e) => { const b = e.target.closest("button[data-k]"); if (b) { stopAuto(); showStage(+b.dataset.k); } });
    document.addEventListener("keydown", (e) => {
      if ($("#view-pipeline").hidden || !pl.data || /^(TEXTAREA|INPUT|SELECT)$/.test(document.activeElement.tagName)) return;
      if (e.key === "ArrowRight") { stopAuto(); showStage(pl.step + 1); }
      if (e.key === "ArrowLeft") { stopAuto(); showStage(pl.step - 1); }
    });
    window.addEventListener("hashchange", () => { if (location.hash !== "#pipeline") stopAuto(); });
  }

  /* ------------------------------------------------------------ live consultation */
  const DEMO_LINES = [
    "Doctor, mujhe teen din se bukhar hai.",
    "Sath me sar dard bhi hai, but cough nahi hai.",
    "मुझे पेट में दर्द भी है और उल्टी हो रही है।",
    "I took paracetamol but the headache gets worse after eating.",
    "Chest pain nahi hai, par thoda breathless feel hota hai.",
  ];
  const lv = { text: "", interim: "", rec: null, listening: false, last: null, seen: new Set(), seq: 0, demo: 0, restartTimer: null };
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;

  function lvStatus(msg, live = false) {
    const el = $("#lv-status");
    el.textContent = msg;
    el.classList.toggle("on", live);
  }

  function lvDrawTranscript() {
    const box = $("#lv-transcript");
    const r = lv.last;
    const body = r && r.text === lv.text ? spanInner(lv.text, r.highlights) : esc(lv.text);
    const interim = lv.interim ? ` <span class="lv-interim">${esc(lv.interim)}</span>` : "";
    box.innerHTML = body || interim
      ? `<p class="pl-text">${body}${interim}</p>`
      : '<span class="lv-placeholder">What the patient says appears here, sentence by sentence.</span>';
    box.scrollTop = box.scrollHeight;
  }

  function lvRender(r) {
    lv.last = r;
    lastResult = r;                                   // so Copy note and Download report work from this page
    lvDrawTranscript();
    const [title] = LEVELS[r.attention_level] || LEVELS.routine;
    const patient = r.symptoms.filter((s) => s.subject === "patient");
    const others = r.symptoms.filter((s) => s.subject !== "patient");
    const card = (s) => {
      const key = `${s.name}|${s.status}|${s.subject}`;
      const fresh = !lv.seen.has(key);
      lv.seen.add(key);
      const who = s.subject !== "patient" ? ` · ${esc(s.subject)}` : "";
      return `<div class="lv-card${fresh ? " is-new" : ""}"><div class="lv-card-top"><b>${esc(cap(s.name))}</b><span class="pl-tag st-${s.status}">${esc(STATUS_NAME[s.status])}${who}</span></div><p>${esc(s.summary.replace(/^[^(]*/, "").replace(/^\(|\)$/g, "") || (s.reason || "no details yet"))}</p></div>`;
    };
    $("#lv-out").innerHTML = `
      <div class="lv-verdict lvl-${esc(r.attention_level)}"><span>⚑</span><div><b>${esc(title)}</b><small>${r.red_flags.length ? esc(r.red_flags.map((f) => f.title).join(" · ")) : "No red flags so far"}</small></div><em class="lang-badge">${esc(r.language.label || r.language.name)}</em></div>
      <div class="lv-block"><div class="lv-label">Note for the doctor</div><p class="lv-note">${esc(r.summary)}</p></div>
      <div class="lv-block"><div class="lv-label">Symptoms (${patient.length})</div><div class="lv-cards">${patient.map(card).join("") || '<p class="muted">Nothing found yet.</p>'}${others.map(card).join("")}</div></div>
      <div class="lv-actions"><button class="btn small" type="button" id="lv-copy">Copy note</button><button class="btn small" type="button" id="lv-report">⤓ Download report</button></div>`;
    $("#lv-copy").addEventListener("click", async (e) => {
      try { await navigator.clipboard.writeText(noteText(r)); e.target.textContent = "Copied"; } catch { e.target.textContent = "Could not copy"; }
      setTimeout(() => (e.target.textContent = "Copy note"), 1500);
    });
    $("#lv-report").addEventListener("click", () => { lastResult = r; downloadReport(); });
  }

  async function lvAnalyze() {
    const mine = ++lv.seq;
    if (!lv.text.trim()) { lv.last = null; $("#lv-out").innerHTML = '<div class="empty"><p>The live note appears here.</p></div>'; lvDrawTranscript(); return; }
    try {
      const res = await fetch("/api/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: lv.text }) });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || "Could not analyze.");
      if (mine === lv.seq) lvRender(d);                // ignore answers that arrive out of order
    } catch (e) {
      lvStatus(e.message);
    }
  }

  function lvAdd(sentence) {
    let t = sentence.trim().replace(/\s+/g, " ");
    if (!t) return;
    if (!/[.!?\u0964]$/.test(t)) t += ".";
    lv.text = (lv.text ? lv.text + " " : "") + t;
    lv.interim = "";
    lvAnalyze();
  }

  function lvSetListening(on) {
    lv.listening = on;
    $("#lv-start").classList.toggle("listening", on);
    $("#lv-start-label").textContent = on ? "Stop listening" : "Start listening";
  }

  function lvStopMic(msg = "Stopped") {
    clearTimeout(lv.restartTimer);
    const wasOn = lv.listening;
    lvSetListening(false);
    try { lv.rec && lv.rec.stop(); } catch { /* already stopped */ }
    lv.interim = "";
    lvDrawTranscript();
    if (wasOn) lvStatus(msg);
  }

  function lvStartMic() {
    if (!SpeechRec) { lvStatus("This browser has no speech recognition. Type a sentence below or play the demo."); return; }
    lvStopDemo();
    const rec = new SpeechRec();
    rec.continuous = true;
    rec.interimResults = true;
    rec.lang = $("#lv-lang").value;
    rec.onresult = (e) => {
      let interim = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const res = e.results[i];
        if (res.isFinal) lvAdd(res[0].transcript);
        else interim += res[0].transcript;
      }
      lv.interim = interim.trim();
      lvDrawTranscript();
    };
    rec.onerror = (e) => {
      if (e.error === "not-allowed" || e.error === "service-not-allowed") lvStopMic("Microphone permission was denied. Allow it in the browser, or type instead.");
      else if (e.error !== "no-speech" && e.error !== "aborted") lvStatus("Speech recognition problem: " + e.error);
    };
    rec.onend = () => {                                 // browsers stop after a pause, so keep it running
      if (lv.listening) lv.restartTimer = setTimeout(() => { try { rec.start(); } catch { /* already running */ } }, 250);
    };
    lv.rec = rec;
    try { rec.start(); lvSetListening(true); lvStatus("Listening… speak naturally", true); }
    catch { lvStatus("Could not start the microphone."); }
  }

  function lvStopDemo() { lv.demo++; }

  async function lvRunDemo() {
    lvStopMic();
    lvClear();
    const run = ++lv.demo;
    lvStatus("Demo conversation playing…", true);
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    for (const line of DEMO_LINES) {
      const chars = Array.from(line);
      for (let i = 1; i <= chars.length; i++) {            // typed out like live speech
        if (run !== lv.demo) return;
        lv.interim = chars.slice(0, i).join("");
        lvDrawTranscript();
        await wait(26);
      }
      await wait(250);
      if (run !== lv.demo) return;
      lvAdd(line);
      await wait(1900);
    }
    if (run === lv.demo) lvStatus("Demo finished");
  }

  function lvClear() {
    lvStopDemo();
    lv.text = ""; lv.interim = ""; lv.last = null; lv.seen = new Set();
    lvAnalyze();
    if (!lv.listening) lvStatus("Ready");
  }

  function bindLive() {
    $("#lv-start").addEventListener("click", () => (lv.listening ? lvStopMic() : lvStartMic()));
    $("#lv-demo").addEventListener("click", lvRunDemo);
    $("#lv-clear").addEventListener("click", lvClear);
    $("#lv-lang").addEventListener("change", () => { if (lv.listening) { lvStopMic("Language changed"); lvStartMic(); } });
    $("#lv-form").addEventListener("submit", (e) => { e.preventDefault(); lvStopDemo(); lvAdd($("#lv-type").value); $("#lv-type").value = ""; });
    window.addEventListener("hashchange", () => { if (location.hash !== "#live") { lvStopMic(); lvStopDemo(); } });   // never keep recording in the background
  }

  /* ------------------------------------------------------------ compare visits */
  const CMP_SAMPLE = {
    before: "I have had fever and cough for 3 days, and a severe headache. No sore throat.",
    after: "The fever is gone. Cough is still there but mild and getting better. I have a new sore throat since yesterday. Headache is worse.",
  };

  function chips(items) {
    return items.map((t) => `<span class="pill">${esc(t)}</span>`).join("");
  }

  function renderCompare(d) {
    const group = (title, cls, rows) => rows.length
      ? `<div class="cmp-group ${cls}"><h3>${esc(title)} <span class="cmp-n">${rows.length}</span></h3>${rows.join("")}</div>`
      : "";
    const row = (name, tag, tagCls, lines) =>
      `<div class="cmp-row"><div class="cmp-name">${esc(cap(name))}<span class="tag ${tagCls}">${esc(tag)}</span></div>${lines.filter(Boolean).map((l) => `<p>${esc(l)}</p>`).join("")}</div>`;
    const dirLabel = { worse: "Worse", better: "Better", changed: "Changed", unchanged: "Unchanged" };
    const newRows = d.new.map((n) => row(n.name, "New", "t-new", [n.note ? `Was ${n.note} at the earlier visit.` : "Not mentioned at the earlier visit.", n.after.duration && `Since: ${n.after.duration}`, n.after.severity && `Severity: ${n.after.severity}`]));
    const contRows = d.continuing.map((c) => row(c.name, dirLabel[c.direction], "t-" + c.direction, c.changes.length ? c.changes : ["No change in the details given."]));
    const goneRows = d.resolved.map((r) => row(r.name, "Resolved or denied", "t-better", [`Now stated as ${r.after.status === "absent" ? "not present" : r.after.status}.`])).concat(
      d.not_mentioned.map((r) => row(r.name, "Not mentioned now", "t-unchanged", ["Present at the earlier visit and not mentioned at this one. Worth asking about."])));
    const flags = d.red_flags;
    const flagHtml = (flags.new.length || flags.cleared.length || flags.ongoing.length)
      ? `<div class="cmp-group"><h3>Red flags</h3>${flags.new.length ? `<p><b>New:</b> ${chips(flags.new)}</p>` : ""}${flags.ongoing.length ? `<p><b>Still present:</b> ${chips(flags.ongoing)}</p>` : ""}${flags.cleared.length ? `<p><b>Cleared:</b> ${chips(flags.cleared)}</p>` : ""}</div>`
      : "";
    $("#cmp-out").innerHTML = `
      <div class="cmp-summary"><span>Summary</span>${esc(d.summary)}</div>
      ${group("New symptoms", "g-new", newRows)}
      ${group("Continuing symptoms", "g-cont", contRows)}
      ${group("No longer present", "g-gone", goneRows)}
      ${flagHtml}
      <div class="cmp-sides">
        <div><h4>Earlier visit</h4><p>${esc(d.before.summary)}</p></div>
        <div><h4>Latest visit</h4><p>${esc(d.after.summary)}</p></div>
      </div>`;
  }

  function bindCompare() {
    const b = $("#cmp-before"), a = $("#cmp-after"), out = $("#cmp-out");
    async function run() {
      if (!b.value.trim() || !a.value.trim()) {
        out.innerHTML = '<div class="error" role="alert"><strong>Please fill in both visits.</strong></div>';
        return;
      }
      const btn = $("#cmp-run");
      btn.disabled = true;
      btn.textContent = "Comparing…";
      try {
        const res = await fetch("/api/compare", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ before: b.value, after: a.value }) });
        const d = await res.json();
        if (!res.ok) throw new Error(d.error || "Something went wrong.");
        renderCompare(d);
      } catch (err) {
        out.innerHTML = `<div class="error" role="alert"><strong>Could not compare.</strong> ${esc(err.message)}</div>`;
      } finally {
        btn.disabled = false;
        btn.textContent = "Compare visits";
      }
    }
    $("#cmp-run").addEventListener("click", run);
    $("#cmp-sample").addEventListener("click", () => { b.value = CMP_SAMPLE.before; a.value = CMP_SAMPLE.after; run(); });
    $("#cmp-clear").addEventListener("click", () => { b.value = ""; a.value = ""; out.innerHTML = ""; b.focus(); });
  }

  /* ------------------------------------------------------------ init */
  async function init() {
    document.querySelectorAll("a[data-view]").forEach((a) => a.addEventListener("click", () => {
      if (location.hash === a.getAttribute("href")) showView(a.dataset.view);
    }));
    textEl.addEventListener("input", () => ($("#count").textContent = `${textEl.value.length} / 5000`));
    textEl.addEventListener("keydown", (e) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") analyze();
    });
    analyzeBtn.addEventListener("click", analyze);
    $("#clear").addEventListener("click", () => {
      textEl.value = "";
      $("#count").textContent = "0 / 5000";
      markedWrap.hidden = true;
      outEl.innerHTML = '<div class="empty"><p>The structured note appears here.</p></div>';
      textEl.focus();
    });

    let examples = [];
    try {
      examples = await (await fetch("/api/examples")).json();
    } catch { /* offline demo still works with typed text */ }
    if (!Array.isArray(examples)) examples = [];
    const preview = (t) => (t.length > 70 ? t.slice(0, 70) + "…" : t);
    $("#example-buttons").innerHTML = examples.map((e, i) => `<li role="option"><button type="button" class="dd-item" data-i="${i}"><b>${esc(e.label)}</b><span>${esc(preview(e.text))}</span></button></li>`).join("")
      + '<li role="option" class="dd-sep"><button type="button" class="dd-item dd-random" data-random="1"><b>🎲 Random case</b><span>A random patient description from the dataset</span></button></li>';
    bindDropdown();
    let lastRandom = -1;
    async function loadRandom() {
      try {
        const c = await (await fetch(`/api/dataset/random?exclude=${lastRandom}`)).json();
        lastRandom = c.id;
        textEl.value = c.text;
        $("#count").textContent = `${textEl.value.length} / 5000`;
        analyze();
      } catch { /* keep current text */ }
    }
    $("#example-buttons").addEventListener("click", (ev) => {
      if (ev.target.closest(".dd-item")) closeDropdown();
      if (ev.target.closest("button[data-random]")) return loadRandom();
      const b = ev.target.closest("button[data-i]");
      if (!b) return;
      textEl.value = examples[+b.dataset.i].text;
      $("#count").textContent = `${textEl.value.length} / 5000`;
      analyze();
    });

    bindLinking();
    bindBlobs();
    bindTheme();
    bindReportDialog();
    bindCompare();
    bindPipeline();
    bindLive();
    bindWelcome();
    bindSpotlight();
    bindLive();
    bindMic();
    routeFromHash();
    if (examples.length && !textEl.value) {
      textEl.value = examples[0].text;
      $("#count").textContent = `${textEl.value.length} / 5000`;
      analyze();
    }
  }
  init();
})();
