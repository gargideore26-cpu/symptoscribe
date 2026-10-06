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
  const VIEWS = ["welcome", "home", "analyzer", "live", "queue", "intake", "evaluation", "about"];
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
    if (name === "intake") loadIntake();
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
    trigger: 2, duration: 3, severity: 4, vital: 4, location: 5, trend: 6, onset: 6, frequency: 6,
    quality: 7, medication: 8, condition: 8, context: 8,
  };
  const LABEL_NAMES = {
    symptom: "Symptom", negated: "Not present", uncertain: "Unsure", history: "Past episode", other: "Someone else",
    duration: "Duration", severity: "Severity", trend: "Course", onset: "Course", frequency: "Course",
    trigger: "Trigger", location: "Location", quality: "Feels like",
    medication: "Background", condition: "Background", context: "Background", vital: "Vital sign",
  };
  const LEGEND_ORDER = ["symptom", "negated", "uncertain", "history", "other", "duration", "severity", "trend", "trigger", "location", "quality", "vital", "context"];

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

  function render(r) {
    lastResult = r;
    const [title, fallback] = LEVELS[r.attention_level] || LEVELS.routine;
    const sub = r.red_flags.length ? r.red_flags[0].title : fallback;
    const flags = r.red_flags.length
      ? `<div class="block"><h3>Red flags</h3><ul class="flags">${r.red_flags
          .map(
            (f) =>
              `<li class="lvl-${esc(f.level)}"><span class="flag-title">${esc(f.title)}</span><span class="flag-level">${esc(LEVELS[f.level][0])}</span><p>${esc(f.advice)}</p>${f.why ? `<small class="flag-why">${esc(f.why)}</small>` : ""}</li>`
          )
          .join("")}</ul></div>`
      : "";
    const vit = (r.vitals && r.vitals.length)
      ? `<div class="block"><h3>Vital signs</h3><div class="vitals">${r.vitals.map((v) => `<div class="vital vs-${esc(v.status)}"><span class="v-label">${esc(v.label)}</span><span class="v-value">${esc(v.value)}<small>${esc(v.unit)}</small></span><span class="v-status">${esc(v.status === "normal" ? "Normal" : cap(v.status))}</span>${v.note ? `<small class="v-note">${esc(v.note)}</small>` : ""}</div>`).join("")}</div></div>`
      : "";
    const chk = (r.checklist && r.checklist.length)
      ? `<div class="block"><h3>Still to ask <span class="chk-count" id="chk-count"></span></h3><ul class="checklist">${r.checklist.map((c, i) => `<li class="${c.done ? "is-done" : ""}"><label><input type="checkbox" data-i="${i}"${c.done ? " checked disabled" : ""}><span>${esc(c.label)}</span>${c.done ? "<small>mentioned</small>" : ""}</label></li>`).join("")}</ul></div>`
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
      ${vit}
      <div class="block"><h3>Structured symptoms</h3>${tableHtml(r.symptoms)}</div>
      ${chk}
      <p class="safety-note">Decision support only. This is not a diagnosis; the doctor decides.</p>
    </article>`;
    renderMarked(r.text, r.highlights);
    const boxes = outEl.querySelectorAll(".checklist input");
    const countChk = () => { const c = $("#chk-count"); if (c) c.textContent = `${[...boxes].filter((b) => b.checked).length} of ${boxes.length} covered`; };
    boxes.forEach((b) => b.addEventListener("change", () => { b.closest("li").classList.toggle("is-done", b.checked); countChk(); }));
    countChk();
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

  // text with marked spans (offsets count code points, like the engine)
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

  /* ------------------------------------------------------------ triage queue */
  const Q_SAMPLE = [
    { name: "Meera", text: "I have had a cold and a mild sore throat for 2 days. No fever." },
    { name: "Mr Kulkarni, 72", text: "72 year old man with severe chest pain since morning, sweating and feeling breathless. BP 90/60." },
    { name: "Baby Arjun", text: "My 2 month old baby has had fever since last night and is not feeding well." },
    { name: "Rohit", text: "Mujhe 3 din se bukhar hai aur sar dard bhi hai, khansi nahi hai." },
  ];
  const q = { rows: [{ name: "", text: "" }] };

  function qSync() {
    $("#q-rows").querySelectorAll(".q-row").forEach((row, i) => {
      q.rows[i] = { name: $(".q-name", row).value, text: $(".q-text", row).value };
    });
  }
  function qRender() {
    $("#q-rows").innerHTML = q.rows.map((r, i) => `<div class="q-row">
      <span class="q-n">${i + 1}</span>
      <input class="q-name" type="text" maxlength="60" placeholder="Name (optional)" value="${esc(r.name)}" aria-label="Patient ${i + 1} name">
      <textarea class="q-text" rows="2" placeholder="What the patient says" aria-label="Patient ${i + 1} description">${esc(r.text)}</textarea>
      <button class="an-del" type="button" data-del="${i}" aria-label="Remove patient ${i + 1}">×</button></div>`).join("");
  }
  function qRenderResult(list) {
    $("#q-out").innerHTML = `<h3 class="q-title">Seen in this order</h3><ol class="q-list">${list.map((p) => `
      <li class="q-card lvl-${esc(p.level)}">
        <span class="q-rank">${p.rank}</span>
        <div class="q-main">
          <div class="q-top"><b>${esc(p.name)}</b><span class="q-level">${esc(LEVELS[p.level][0])}</span></div>
          <p class="q-flag">${p.top_flag ? esc(p.top_flag) + (p.flags > 1 ? ` <small>+${p.flags - 1} more</small>` : "") : "No red flags found."}</p>
          <div class="q-chips">${p.symptoms.map((s) => `<span>${esc(s)}</span>`).join("") || '<span class="muted">No symptoms found</span>'}</div>
        </div>
        <div class="q-side"><small>${p.to_ask} to ask</small><button class="btn small" type="button" data-open="${p.index}">Open note</button></div>
      </li>`).join("")}</ol>`;
    q.result = list;
  }
  async function qSort() {
    qSync();
    const out = $("#q-out"), btn = $("#q-sort");
    const patients = q.rows.filter((r) => r.text.trim());
    if (!patients.length) { out.innerHTML = '<div class="error" role="alert">Add at least one patient with a description.</div>'; return; }
    btn.disabled = true; btn.textContent = "Sorting…";
    try {
      const res = await fetch("/api/triage", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ patients }) });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || "Could not sort.");
      q.sorted = patients;
      qRenderResult(d);
    } catch (e) {
      out.innerHTML = `<div class="error" role="alert"><strong>Could not sort.</strong> ${esc(e.message)}</div>`;
    } finally {
      btn.disabled = false; btn.textContent = "Sort by urgency";
    }
  }
  function openInAnalyzer(text) {
    textEl.value = text;
    location.hash = "#analyzer";
    analyze();
  }
  function bindQueue() {
    qRender();
    $("#q-add").addEventListener("click", () => { qSync(); q.rows.push({ name: "", text: "" }); qRender(); $("#q-rows").lastElementChild.querySelector("textarea").focus(); });
    $("#q-sort").addEventListener("click", qSort);
    $("#q-sample").addEventListener("click", () => { q.rows = Q_SAMPLE.map((r) => ({ ...r })); qRender(); qSort(); });
    $("#q-clear").addEventListener("click", () => { q.rows = [{ name: "", text: "" }]; q.sorted = null; qRender(); $("#q-out").innerHTML = ""; });
    $("#q-rows").addEventListener("click", (e) => {
      const d = e.target.closest("[data-del]");
      if (!d) return;
      qSync(); q.rows.splice(+d.dataset.del, 1); if (!q.rows.length) q.rows.push({ name: "", text: "" }); qRender();
    });
    $("#q-out").addEventListener("click", (e) => {
      const b = e.target.closest("[data-open]");
      if (b && q.sorted) openInAnalyzer(q.sorted[+b.dataset.open].text);
    });
    $("#q-inbox").addEventListener("click", async () => {
      try {
        const d = await (await fetch("/api/intake")).json();
        const got = d.items.filter((i) => i.submitted);
        if (!got.length) { $("#q-out").innerHTML = '<p class="muted">No patient has sent a form yet.</p>'; return; }
        qSync();
        q.rows = q.rows.filter((r) => r.text.trim()).concat(got.map((i) => ({ name: i.name || i.label, text: i.text })));
        qRender(); qSort();
      } catch { $("#q-out").innerHTML = '<div class="error" role="alert">Could not read the intake forms.</div>'; }
    });
  }

  /* ------------------------------------------------------------ patient intake */
  let inItems = [], inLan = "", inTimer = null;
  const LVL_SHORT = { routine: "Routine", attention: "Needs attention", urgent: "See soon", emergency: "Urgent care" };

  function inBase() {
    const local = ["localhost", "127.0.0.1", "[::1]"].includes(location.hostname);
    return local && inLan ? `http://${inLan}${location.port ? ":" + location.port : ""}` : location.origin;
  }
  function inRender() {
    const base = inBase();
    $("#in-hint").textContent = ["localhost", "127.0.0.1"].includes(location.hostname) && !inLan
      ? "These links open on this computer only. To let a patient on the same Wi-Fi open one, start the app with HOST=0.0.0.0."
      : "";
    if (!inItems.length) { $("#in-list").innerHTML = '<div class="empty"><p>No links yet. Create one above.</p></div>'; return; }
    $("#in-list").innerHTML = inItems.map((it) => {
      const when = new Date((it.submitted || it.created) * 1000).toLocaleString([], { dateStyle: "medium", timeStyle: "short" });
      if (!it.submitted) {
        const url = base + "/p/" + it.token;
        return `<div class="in-card"><div class="in-top"><b>${esc(it.label || "Patient link")}</b><span class="in-state wait">Waiting for the patient</span></div>
          <div class="in-link"><input type="text" readonly value="${esc(url)}" aria-label="Patient link"><button class="btn small" type="button" data-copy="${esc(url)}">Copy link</button><button class="btn small" type="button" data-del="${esc(it.token)}">Delete</button></div>
          <small class="muted">Created ${esc(when)}</small></div>`;
      }
      return `<div class="in-card lvl-${esc(it.level)}"><div class="in-top"><b>${esc(it.name || it.label || "Patient")}</b><span class="in-state got">Received</span><span class="q-level">${esc(LVL_SHORT[it.level])}</span></div>
        <p class="q-flag">${it.top_flag ? esc(it.top_flag) : "No red flags found."}</p>
        <div class="q-chips">${it.symptoms.map((s) => `<span>${esc(s)}</span>`).join("")}</div>
        <p class="in-text">${esc(it.text.length > 220 ? it.text.slice(0, 220) + "…" : it.text)}</p>
        <div class="in-link"><button class="btn small primary" type="button" data-open="${esc(it.token)}">Open note</button><button class="btn small" type="button" data-del="${esc(it.token)}">Delete</button><small class="muted">Received ${esc(when)}</small></div></div>`;
    }).join("");
  }
  async function loadIntake() {
    clearInterval(inTimer);
    try {
      const d = await (await fetch("/api/intake")).json();
      inItems = d.items; inLan = d.lan_ip || "";
      const typing = document.activeElement && document.activeElement.closest && document.activeElement.closest("#in-list");
      if (!typing) inRender();
    } catch { $("#in-list").innerHTML = '<div class="error" role="alert">Could not load the forms.</div>'; }
    inTimer = setInterval(() => { if ($("#view-intake").hidden) clearInterval(inTimer); else loadIntake(); }, 8000);
  }
  function bindIntake() {
    $("#in-create").addEventListener("click", async () => {
      const btn = $("#in-create");
      btn.disabled = true;
      try {
        await fetch("/api/intake", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ label: $("#in-label").value }) });
        $("#in-label").value = "";
        await loadIntake();
      } finally { btn.disabled = false; }
    });
    $("#in-refresh").addEventListener("click", loadIntake);
    $("#in-list").addEventListener("click", async (e) => {
      const c = e.target.closest("[data-copy]"), d = e.target.closest("[data-del]"), o = e.target.closest("[data-open]");
      if (c) {
        try { await navigator.clipboard.writeText(c.dataset.copy); c.textContent = "Copied"; } catch { c.previousElementSibling.select(); c.textContent = "Press Ctrl+C"; }
      } else if (d) {
        if (!confirm("Delete this form? Anything the patient wrote is removed from this computer.")) return;
        await fetch("/api/intake/" + encodeURIComponent(d.dataset.del), { method: "DELETE" });
        loadIntake();
      } else if (o) {
        const it = inItems.find((x) => x.token === o.dataset.open);
        if (it) openInAnalyzer(it.text);
      }
    });
  }

  /* ------------------------------------------------------------ side menu hide / show */
  function bindNavToggle() {
    const btn = $("#nav-toggle"), root = document.documentElement, side = $(".top"), hot = $("#nav-hot");
    let timer = null;
    const sync = () => {
      const hidden = root.classList.contains("nav-collapsed");
      btn.setAttribute("aria-expanded", String(!hidden));
      btn.setAttribute("aria-label", hidden ? "Show menu" : "Hide menu");
    };
    // while the menu is hidden, pointing at the left edge or at the logo slides it out over the page
    const peek = () => { clearTimeout(timer); if (root.classList.contains("nav-collapsed")) root.classList.add("nav-peek"); };
    const unpeek = () => { clearTimeout(timer); timer = setTimeout(() => root.classList.remove("nav-peek"), 250); };
    [hot, side, btn].forEach((el) => {
      el.addEventListener("mouseenter", peek);
      el.addEventListener("mouseleave", unpeek);
    });
    side.addEventListener("focusin", peek);
    side.addEventListener("focusout", unpeek);
    sync();
    btn.addEventListener("click", () => {
      root.classList.toggle("nav-collapsed");
      root.classList.remove("nav-peek");
      try { localStorage.setItem("navCollapsed", root.classList.contains("nav-collapsed") ? "1" : "0"); } catch { /* private mode */ }
      sync();
    });
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
    bindLive();
    bindNavToggle();
    bindQueue();
    bindIntake();
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
