"""Stage-by-stage view of how the engine reads a text, for the Pipeline page.

Everything here is derived from the engine's own output (nothing is re-implemented), so the viewer
always shows exactly what the real pipeline did.
"""
from nlp import analyze

DETAIL_KEYS = ("duration", "severity", "trend", "onset", "frequency", "location", "radiates_to", "temperature")
KIND = {"duration": "duration", "severity": "severity", "trend": "course", "onset": "course", "frequency": "course",
        "location": "location", "radiates_to": "location", "temperature": "temperature"}


def _details(rec: dict) -> list:
    out = []
    for key in DETAIL_KEYS:
        v = rec.get(key)
        if not v or "start" not in v:
            continue
        if key == "severity" and v.get("source") == "temperature":
            continue                      # the temperature itself is listed instead
        label = v.get("label") or v.get("text")
        out.append({"kind": KIND[key], "key": key, "text": v["text"], "start": v["start"], "end": v["end"], "label": label})
    for t in rec.get("triggers", []):
        out.append({"kind": "trigger", "key": "trigger", "text": t["text"], "start": t["start"], "end": t["end"], "label": t.get("label") or t["text"]})
    for q in rec.get("quality", []):
        out.append({"kind": "quality", "key": "quality", "text": q["text"], "start": q["start"], "end": q["end"], "label": q["label"]})
    return out


def _group(tokens: list, key) -> list:
    groups = {}
    for t in tokens:
        groups.setdefault(key(t), []).append(t)
    return [(k, v) for k, v in groups.items()]


def build_pipeline(text: str) -> dict:
    a = analyze(text)
    cps = list(a["text"])
    tokens = a["tokens"]

    def span(ts):
        s, e = min(t["start"] for t in ts), max(t["end"] for t in ts)
        return s, e, "".join(cps[s:e])

    sentences = []
    for k, ts in _group(tokens, lambda t: t["sent"]):
        s, e, txt = span(ts)
        sentences.append({"index": k + 1, "start": s, "end": e, "text": txt, "tokens": len(ts)})
    clauses = []
    for (si, ci), ts in _group(tokens, lambda t: (t["sent"], t["clause"])):
        s, e, txt = span(ts)
        clauses.append({"sentence": si + 1, "clause": ci + 1, "start": s, "end": e, "text": txt})
    changes = [{"text": t["text"], "norm": t["norm"], "start": t["start"], "end": t["end"]}
               for t in tokens if t["text"].lower() != t["norm"]]

    symptoms, flat = [], []
    for r in a["symptoms"]:
        d = _details(r)
        for x in d:
            flat.append({**x, "symptom": r["name"]})
        symptoms.append({
            "name": r["name"], "status": r["status"], "reason": r["reason"], "subject": r["subject"], "system": r["system"],
            "method": r["method"], "confidence": r["confidence"], "evidence": r["evidence"], "details": d, "summary": r["summary"],
        })
    return {
        "text": a["text"], "language": a["language"],
        "sentences": sentences, "tokens": tokens[:200], "token_count": len(tokens),
        "changes": changes, "clauses": clauses,
        "symptoms": symptoms, "details": flat, "unlinked": a["unlinked_details"],
        "red_flags": a["red_flags"], "attention_level": a["attention_level"],
        "summary": a["summary"], "follow_up_questions": a["follow_up_questions"],
    }
