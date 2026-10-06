"""Patient pre-visit intake: the doctor makes a link, the patient writes their symptoms, the doctor reads the note.

Stored in one JSON file (data/intake.json, or $INTAKE_FILE). There is no login: this is a prototype for
one clinic computer. Anyone who can open the site can read the inbox, so do not expose it to the internet as it is.
"""
import json
import os
import secrets
import tempfile
import threading
import time

MAX_RECORDS = 200
_lock = threading.Lock()


def _path() -> str:
    return os.environ.get("INTAKE_FILE") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "intake.json")


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
        json.dump(rows, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def create(label: str) -> dict:
    with _lock:
        rows = _load()
        rec = {"token": secrets.token_urlsafe(9), "label": label.strip()[:60], "created": time.time(),
               "submitted": None, "name": "", "text": ""}
        rows.append(rec)
        _save(rows[-MAX_RECORDS:])
        return rec


def get(token: str):
    return next((r for r in _load() if secrets.compare_digest(r["token"], token)), None)


def list_all() -> list:
    return sorted(_load(), key=lambda r: -r["created"])


def submit(token: str, name: str, text: str) -> str:
    """Returns "ok", "missing" or "done"."""
    with _lock:
        rows = _load()
        rec = next((r for r in rows if secrets.compare_digest(r["token"], token)), None)
        if rec is None:
            return "missing"
        if rec["submitted"]:
            return "done"
        rec.update(name=name.strip()[:60], text=text.strip(), submitted=time.time())
        _save(rows)
        return "ok"


def delete(token: str) -> bool:
    with _lock:
        rows = _load()
        keep = [r for r in rows if r["token"] != token]
        if len(keep) == len(rows):
            return False
        _save(keep)
        return True
