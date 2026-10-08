(() => {
  "use strict";
  const $ = (s) => document.querySelector(s);
  const form = $("#p-form");
  if (!form) return;
  const text = $("#p-text"), err = $("#p-error"), send = $("#p-send");

  send.addEventListener("click", async () => {
    err.hidden = true;
    if (!text.value.trim()) { err.textContent = "Please write how you feel first."; err.hidden = false; return; }
    send.disabled = true;
    try {
      const res = await fetch(`/api/intake/${encodeURIComponent(form.dataset.token)}/submit`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: $("#p-name").value, text: text.value }),
      });
      const d = await res.json();
      if (!res.ok) throw new Error(d.error || "Could not send.");
      form.hidden = true; $("#p-thanks").hidden = false; window.scrollTo(0, 0);
    } catch (e) {
      err.textContent = e.message; err.hidden = false; send.disabled = false;
    }
  });

  // optional dictation (Chrome and Safari only)
  const Rec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Rec) return;
  const mic = $("#p-mic"), lang = $("#p-lang"), status = $("#p-status");
  mic.hidden = false; lang.hidden = false;
  let rec = null;
  const stop = () => { if (rec) { rec.onend = null; try { rec.stop(); } catch { /* already stopped */ } rec = null; } mic.textContent = "🎤 Speak"; status.textContent = ""; };
  mic.addEventListener("click", () => {
    if (rec) return stop();
    rec = new Rec(); rec.lang = lang.value; rec.continuous = true; rec.interimResults = false;
    rec.onresult = (e) => {
      for (let i = e.resultIndex; i < e.results.length; i++) if (e.results[i].isFinal) text.value = (text.value.trim() + " " + e.results[i][0].transcript.trim()).trim();
    };
    rec.onerror = () => { status.textContent = "The microphone could not start."; stop(); };
    rec.onend = stop;
    try { rec.start(); mic.textContent = "■ Stop"; status.textContent = "Listening…"; } catch { stop(); }
  });
})();
