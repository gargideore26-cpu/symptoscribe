"""Compare two visits: what is new, what went away, and what changed in the symptoms that continue."""
from nlp import analyze

ACTIVE = ("present", "uncertain")
DENIED = ("absent", "resolved")
RANK = {"present": 0, "uncertain": 1, "history": 2, "resolved": 3, "absent": 4}


def _by_name(result: dict) -> dict:
    """Best record per symptom name for the patient (present beats denied)."""
    out = {}
    for s in result["symptoms"]:
        if s["subject"] != "patient":
            continue
        cur = out.get(s["name"])
        if cur is None or RANK[s["status"]] < RANK[cur["status"]]:
            out[s["name"]] = s
    return out


def _snap(s: dict) -> dict:
    return {
        "status": s["status"],
        "duration": s["duration"]["text"] if s.get("duration") else None,
        "days": s["duration"]["days"] if s.get("duration") else None,
        "severity": s["severity"]["label"] if s.get("severity") else None,
        "score": s["severity"]["score"] if s.get("severity") else None,
        "trend": s["trend"]["label"] if s.get("trend") else None,
    }


def _continuing(name: str, b: dict, a: dict) -> dict:
    sb, sa = _snap(b), _snap(a)
    changes, up, down = [], 0, 0
    if sb["score"] and sa["score"] and sb["score"] != sa["score"]:
        changes.append(f"severity {sb['severity']} → {sa['severity']}")
        up, down = (1, 0) if sa["score"] > sb["score"] else (0, 1)
    elif sa["severity"] and not sb["severity"]:
        changes.append(f"now described as {sa['severity']}")
        up = 1 if sa["score"] >= 2 else 0
    elif sb["severity"] and not sa["severity"]:
        changes.append(f"was {sb['severity']}, severity no longer stated")
    if sa["trend"] and sa["trend"] != sb["trend"]:
        changes.append(f"course: {sa['trend']}")
        if sa["trend"] in ("worsening",):
            up = 1
        elif sa["trend"] in ("improving",):
            down = 1
    if sa["duration"] and sa["duration"] != sb["duration"]:
        changes.append(f"duration: {sa['duration']}" + (f" (before: {sb['duration']})" if sb["duration"] else ""))
    if b["status"] != a["status"]:
        changes.append(f"status {b['status']} → {a['status']}")
    direction = "worse" if up and not down else "better" if down and not up else "changed" if changes else "unchanged"
    return {"name": name, "direction": direction, "changes": changes, "before": sb, "after": sa}


def _flag_titles(result: dict) -> set:
    return {f["title"] for f in result["red_flags"]}


def compare_visits(before_text: str, after_text: str) -> dict:
    rb, ra = analyze(before_text), analyze(after_text)
    b, a = _by_name(rb), _by_name(ra)
    new, resolved, gone, continuing = [], [], [], []
    for name, sa in a.items():
        sb = b.get(name)
        if sa["status"] in ACTIVE:
            if sb is None or sb["status"] not in ACTIVE:
                note = "previously denied" if sb and sb["status"] in DENIED else None
                new.append({"name": name, "note": note, "after": _snap(sa)})
            else:
                continuing.append(_continuing(name, sb, sa))
        elif sa["status"] in DENIED and sb and sb["status"] in ACTIVE:
            resolved.append({"name": name, "before": _snap(sb), "after": _snap(sa)})
    for name, sb in b.items():
        if sb["status"] in ACTIVE and name not in a:
            gone.append({"name": name, "before": _snap(sb)})

    order = {"worse": 0, "changed": 1, "better": 2, "unchanged": 3}
    continuing.sort(key=lambda c: order[c["direction"]])
    fb, fa = _flag_titles(rb), _flag_titles(ra)
    counts = {d: sum(1 for c in continuing if c["direction"] == d) for d in order}

    def names(items):
        return ", ".join(i["name"] for i in items)

    parts = []
    if new:
        parts.append(f"{len(new)} new symptom{'s' if len(new) != 1 else ''} ({names(new)})")
    if resolved or gone:
        both = resolved + gone
        parts.append(f"{len(both)} no longer present ({names(both)})")
    if continuing:
        bits = [f"{counts[d]} {d}" for d in ("worse", "better", "changed", "unchanged") if counts[d]]
        parts.append(f"{len(continuing)} continuing ({', '.join(bits)})")
    summary = "Since the earlier visit: " + "; ".join(parts) + "." if parts else "No symptoms were found to compare."

    def side(r):
        return {"summary": r["summary"], "attention_level": r["attention_level"], "language": r["language"], "text": r["text"],
                "symptoms": sum(1 for s in r["symptoms"] if s["subject"] == "patient" and s["status"] in ACTIVE)}

    return {
        "summary": summary,
        "new": new, "resolved": resolved, "not_mentioned": gone, "continuing": continuing,
        "red_flags": {"new": sorted(fa - fb), "cleared": sorted(fb - fa), "ongoing": sorted(fa & fb)},
        "before": side(rb), "after": side(ra),
    }
