"""Clinic dashboard counts. Only counts are kept (symptom names, urgency level, language), never the patient's words.

Saved in data/stats.json (or $STATS_FILE).
"""
import json
import os
import tempfile
import threading
import time
from collections import Counter

MAX_EVENTS = 5000
_lock = threading.Lock()
LEVELS = ("routine", "attention", "urgent", "emergency")
LANG_LABEL = {"en": "English", "hi-Latn": "Hinglish", "hi": "Hindi", "mr": "Marathi", "mixed": "Mixed"}


def _path() -> str:
    return os.environ.get("STATS_FILE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "stats.json")


def _load() -> list:
    try:
        with open(_path(), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, list) else []
    except (OSError, ValueError):
        return []


def _save(rows: list) -> None:
    p = _path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(p), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False)
    os.replace(tmp, p)


def event(a: dict, sample: bool = False, ts: float = None) -> dict:
    return {
        "ts": ts or time.time(),
        "level": a["attention_level"],
        "language": (a.get("language") or {}).get("code", "en"),
        "symptoms": sorted({s["name"] for s in a["symptoms"] if s["subject"] == "patient" and s["status"] in ("present", "uncertain")}),
        "flags": [f["title"] for f in a["red_flags"]],
        "sample": sample,
    }


def add(events: list) -> None:
    with _lock:
        rows = _load() + events
        _save(rows[-MAX_EVENTS:])


def clear(sample_only: bool = False) -> int:
    with _lock:
        rows = _load()
        keep = [r for r in rows if not r.get("sample")] if sample_only else []
        _save(keep)
        return len(rows) - len(keep)


def summary(now: float = None, days: int = 14) -> dict:
    rows = _load()
    now = now or time.time()
    by_level = Counter(r["level"] for r in rows)
    sym = Counter(s for r in rows for s in r["symptoms"])
    flags = Counter(f for r in rows for f in r["flags"])
    langs = Counter(r["language"] for r in rows)
    day = 86400
    today = int(now // day)
    per_day = Counter(int(r["ts"] // day) for r in rows)
    series = [{"date": time.strftime("%d %b", time.gmtime((today - i) * day)), "count": per_day.get(today - i, 0)} for i in range(days - 1, -1, -1)]
    total = len(rows)
    return {
        "total": total,
        "samples": sum(1 for r in rows if r.get("sample")),
        "attention_soon": by_level["urgent"] + by_level["emergency"],
        "avg_symptoms": round(sum(len(r["symptoms"]) for r in rows) / total, 1) if total else 0,
        "by_level": [{"level": lv, "count": by_level[lv]} for lv in LEVELS],
        "languages": [{"code": c, "label": LANG_LABEL.get(c, c), "count": n} for c, n in langs.most_common()],
        "top_symptoms": [{"name": n, "count": c} for n, c in sym.most_common(10)],
        "top_flags": [{"name": n, "count": c} for n, c in flags.most_common(6)],
        "per_day": series,
    }
