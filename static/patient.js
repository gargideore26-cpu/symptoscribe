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

  // example texts, for showing the form
  const EXAMPLES = [
    { name: "Asha", text: "I have had a fever and sore throat for 3 days. No cough. I take paracetamol." },
    { name: "Asha", text: "Mujhe 2 din se bukhar hai aur sar dard bhi hai, khansi nahi hai. Kal se pet me dard bhi ho raha hai." },
    { name: "आशा", text: "मुझे 3 दिन से तेज बुखार है, बदन दर्द और कमजोरी है। उल्टी नहीं है।" },
    { name: "आशा", text: "मला २ दिवसांपासून ताप आहे आणि डोकेदुखी आहे, खोकला नाही." },
  ];
  document.querySelectorAll(".p-ex").forEach((b) => b.addEventListener("click", () => {
    const ex = EXAMPLES[+b.dataset.i];
    text.value = ex.text;
    if (!$("#p-name").value.trim()) $("#p-name").value = ex.name;
    err.hidden = true;
  }));
})();
