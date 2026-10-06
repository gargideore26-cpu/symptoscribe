"""Triage queue: analyse several patients and sort them by urgency."""
from nlp import analyze
from nlp import lexicon as L

MAX_PATIENTS = 30
MAX_CHARS = 5000


def triage(patients: list) -> list:
    rows = []
    for i, p in enumerate(patients[:MAX_PATIENTS]):
        text = (p.get("text") or "").strip()[:MAX_CHARS]
        if not text:
            continue
        a = analyze(text)
        flags = a["red_flags"]
        present = [s["name"] for s in a["symptoms"] if s["subject"] == "patient" and s["status"] in ("present", "uncertain")]
        rows.append({
            "index": i,
            "name": (p.get("name") or "").strip()[:60] or f"Patient {i + 1}",
            "text": text,
            "level": a["attention_level"],
            "top_flag": flags[0]["title"] if flags else "",
            "flags": len(flags),
            "symptoms": present[:6],
            "to_ask": sum(1 for c in a["checklist"] if not c["done"]),
            "language": (a.get("language") or {}).get("label", ""),
        })
    # most urgent first; more red flags first; otherwise keep the order they arrived in
    rows.sort(key=lambda r: (-L.LEVEL_RANK[r["level"]], -r["flags"], r["index"]))
    for n, r in enumerate(rows, 1):
        r["rank"] = n
    return rows
