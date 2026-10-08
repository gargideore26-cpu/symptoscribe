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
  const VIEWS = ["welcome", "home", "analyzer", "intake", "dashboard", "evaluation"];
  let accuracyLoaded = false;

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
    if (name === "dashboard") loadDashboard();
    if (name === "evaluation") {
      if (!accuracyLoaded) loadAccuracy();
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

  function render(r, animate = false) {
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
    </article>`;
    renderMarked(r.text, r.highlights);
    $("#copy-note").addEventListener("click", copyNote);
    $("#dl-report").addEventListener("click", downloadReport);
    if (animate) {
      const calm = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      if (!calm) playResult();
      // take the reader down to the review
      const top = outEl.getBoundingClientRect().top + window.scrollY - 24;
      glideTo(top, calm ? 0 : 800);
    }
  }

  // a gentle scroll that does not depend on the browser's own smooth-scroll support
  let glideTimer = 0;
  function glideTo(y, ms) {
    clearTimeout(glideTimer);
    const from = window.scrollY, to = Math.max(0, Math.round(y)), t0 = performance.now();
    if (!ms || Math.abs(to - from) < 4) { window.scrollTo(0, to); return; }
    const stop = () => clearTimeout(glideTimer);
    window.addEventListener("wheel", stop, { once: true, passive: true });   // the reader takes over
    window.addEventListener("touchstart", stop, { once: true, passive: true });
    const step = () => {
      const p = Math.min(1, (performance.now() - t0) / ms), e = 1 - Math.pow(1 - p, 3);
      window.scrollTo(0, from + (to - from) * e);
      if (p < 1) glideTimer = setTimeout(step, 16);
    };
    step();
  }

  // the result builds up step by step: banner, then the note word by word, then the other blocks and table rows
  function playResult() {
    const art = outEl.querySelector(".result");
    if (!art) return;
    art.classList.add("reveal");
    const note = art.querySelector(".note");
    let t = 0.5;                                    // seconds
    if (note) {
      const words = note.textContent.split(/(\s+)/);
      const count = words.filter((w) => w.trim()).length;
      const per = Math.min(0.045, 2.2 / Math.max(1, count));
      let k = 0;
      note.innerHTML = words.map((w) => (w.trim() ? `<span class="w" style="animation-delay:${(0.5 + k++ * per).toFixed(2)}s">${esc(w)}</span>` : w)).join("");
      t = 0.5 + count * per + 0.15;
    }
    [...art.children].forEach((el, i) => {
      if (i === 0) { el.style.animationDelay = "0s"; return; }
      if (el.contains(note)) { el.style.animationDelay = "0.3s"; return; }
      el.style.animationDelay = `${t.toFixed(2)}s`;
      el.querySelectorAll("tbody tr").forEach((tr, n) => { tr.style.animationDelay = `${(t + 0.25 + n * 0.09).toFixed(2)}s`; });
      el.querySelectorAll(".vital, .flags li").forEach((x, n) => { x.style.animationDelay = `${(t + 0.2 + n * 0.1).toFixed(2)}s`; });
      t += 0.55;
    });
  }

  // an example only fills the text box; the old result is cleared so it never sits next to different text
  function resetResult() {
    lastResult = null;
    markedWrap.hidden = true;
    outEl.innerHTML = '<div class="empty"><p>The structured note appears here.</p></div>';
  }

  function showError(msg) {
    outEl.innerHTML = `<div class="error" role="alert"><strong>Could not analyze the text.</strong> ${esc(msg)}</div>`;
  }

  /* ------------------------------------------------------------ actions */
  async function analyze(record = false) {
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
        body: JSON.stringify({ text, record: record === true }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Something went wrong.");
      render(data, record === true);
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

  /* ------------------------------------------------------------ how it works: one line of accuracy */
  async function loadAccuracy() {
    const line = $("#accuracy-line");
    try {
      const e = await (await fetch("/api/evaluation")).json();
      const pct = (x) => Math.round(x * 100) + "%";
      accuracyLoaded = true;
      line.textContent = `On ${e.dataset.cases} texts marked by hand, it finds ${pct(e.overall.detection.f1)} of the symptoms correctly (${pct(e.by_set.challenge.detection.f1)} on the hardest, unseen set). The author marked these texts, so real patient text will score lower.`;
    } catch { line.textContent = ""; }
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

  /* ------------------------------------------------------------ dashboard */
  const DB_LEVEL = { routine: "Routine", attention: "Needs attention", urgent: "See soon", emergency: "Urgent care" };

  function dbBars(rows, cls = "") {
    const max = Math.max(1, ...rows.map((x) => x.count));
    if (!rows.length) return '<p class="muted">Nothing yet.</p>';
    return `<ul class="db-bars">${rows.map((x) => `<li class="${cls || (x.level ? "lvl-" + x.level : "")}"><span class="db-name">${esc(cap(x.label || x.name || DB_LEVEL[x.level]))}</span><span class="db-track"><i style="width:${Math.round((x.count / max) * 100)}%"></i></span><b>${x.count}</b></li>`).join("")}</ul>`;
  }
  function dbRender(s) {
    if (!s.total) { $("#db-out").innerHTML = '<div class="empty"><p>No notes yet. Analyse a text on the Analyzer page and the summary will appear here.</p></div>'; return; }
    $("#db-out").innerHTML = `
      <div class="cards db-cards">
        <div class="metric"><div class="num">${s.total}</div><div class="lab">notes analysed</div></div>
        <div class="metric"><div class="num">${s.attention_soon}</div><div class="lab">needed a doctor soon or urgent care</div></div>
        <div class="metric"><div class="num">${s.avg_symptoms}</div><div class="lab">symptoms per note, on average</div></div>
        <div class="metric"><div class="num">${s.languages.length}</div><div class="lab">input languages seen</div></div>
      </div>
      <div class="db-grid">
        <div class="db-card"><h3>Most common symptoms</h3>${dbBars(s.top_symptoms)}</div>
        <div class="db-card"><h3>How urgent</h3>${dbBars(s.by_level.map((x) => ({ ...x, name: DB_LEVEL[x.level] })))}</div>
        <div class="db-card"><h3>Input language</h3>${dbBars(s.languages)}</div>
        <div class="db-card"><h3>Red flags raised</h3>${dbBars(s.top_flags)}</div>
      </div>`;
  }
  let dbTimer = null;
  async function loadDashboard() {
    clearInterval(dbTimer);
    try { dbRender(await (await fetch("/api/stats")).json()); }
    catch { $("#db-out").innerHTML = '<div class="error" role="alert">Could not load the insights.</div>'; }
    // keeps itself up to date while the page is open
    dbTimer = setInterval(() => { if ($("#view-dashboard").hidden) clearInterval(dbTimer); else loadDashboard(); }, 10000);
  }

  function openInAnalyzer(text) {
    textEl.value = text;
    location.hash = "#analyzer";
    analyze(true);
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
      if ((e.ctrlKey || e.metaKey) && e.key === "Enter") analyze(true);
    });
    analyzeBtn.addEventListener("click", () => analyze(true));
    $("#clear").addEventListener("click", () => {
      textEl.value = "";
      $("#count").textContent = "0 / 5000";
      resetResult();
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
        resetResult();
      } catch { /* keep current text */ }
    }
    $("#example-buttons").addEventListener("click", (ev) => {
      if (ev.target.closest(".dd-item")) closeDropdown();
      if (ev.target.closest("button[data-random]")) return loadRandom();
      const b = ev.target.closest("button[data-i]");
      if (!b) return;
      textEl.value = examples[+b.dataset.i].text;
      $("#count").textContent = `${textEl.value.length} / 5000`;
      resetResult();
    });

    bindLinking();
    bindBlobs();
    bindTheme();
    bindReportDialog();
    bindLive();
    bindNavToggle();
    bindIntake();
    bindWelcome();
    bindSpotlight();
    bindMic();
    routeFromHash();
    if (examples.length && !textEl.value) {
      textEl.value = examples[0].text;
      $("#count").textContent = `${textEl.value.length} / 5000`;
    }
  }
  init();
})();
