"""Symptom2Disease dataset (Kaggle, niyarrbarman): 1,200 patient-style symptom descriptions.

The dataset has only a disease label and the patient's text, with no hand-marked symptoms,
so it is used two ways: as real example inputs for the analyzer, and as a coverage report
(what the engine finds across all 1,200 texts). SymptoScribe itself never predicts a disease.
"""
import csv
import os
import pathlib
import random
from collections import Counter, defaultdict
from functools import lru_cache

from nlp import analyze

DATA_PATH = pathlib.Path(os.environ.get("SYMPTO_DATASET", pathlib.Path(__file__).parent / "data" / "Symptom2Disease.csv"))
SOURCE = {
    "name": "Symptom2Disease",
    "author": "niyarrbarman",
    "url": "https://www.kaggle.com/datasets/niyarrbarman/symptom2disease",
}
EXAMPLE_DISEASES = ["Migraine", "Pneumonia", "Dengue", "gastroesophageal reflux disease", "urinary tract infection"]


class DatasetMissing(RuntimeError):
    pass


@lru_cache(maxsize=1)
def load() -> list:
    if not DATA_PATH.exists():
        raise DatasetMissing(f"Dataset not found. Put Symptom2Disease.csv at {DATA_PATH}.")
    with open(DATA_PATH, encoding="utf-8-sig", newline="") as f:
        rows = [{"label": r["label"].strip(), "text": r["text"].strip()} for r in csv.DictReader(f) if r.get("text", "").strip()]
    for i, r in enumerate(rows):
        r["id"] = i
    return rows


def _found(a: dict) -> list:
    return [s for s in a["symptoms"] if s["subject"] == "patient" and s["status"] in ("present", "uncertain")]


@lru_cache(maxsize=1)
def _analysed() -> list:
    return [(r, analyze(r["text"])) for r in load()]


def _title(a: dict) -> str:
    """Plain title from the first symptoms the engine finds, e.g. "Headache, nausea and vomiting"."""
    names = []
    for s in _found(a):
        if s["name"] not in names:
            names.append(s["name"])
    names = names[:3]
    t = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return t[:1].upper() + t[1:]


def examples() -> list:
    """One fixed, readable case from each of a few categories (the category is not shown to users)."""
    out = []
    for label in EXAMPLE_DISEASES:
        for r, a in _analysed():
            if r["label"] == label and len(_found(a)) >= 2:
                out.append({"label": _title(a), "text": r["text"], "id": r["id"]})
                break
    return out


def random_case(exclude: int = -1) -> dict:
    rows = [r for r in load() if r["id"] != exclude]
    r = random.choice(rows)
    return {"label": "Random case", "text": r["text"], "id": r["id"]}


@lru_cache(maxsize=1)
def coverage() -> dict:
    data = _analysed()
    total = len(data)
    symptom_counts, flag_counts = Counter(), Counter()
    per_label = defaultdict(lambda: {"texts": 0, "covered": 0, "symptoms": Counter()})
    misses, per_text = [], []
    for r, a in data:
        found = _found(a)
        per_text.append(len(found))
        b = per_label[r["label"]]
        b["texts"] += 1
        if found:
            b["covered"] += 1
        else:
            misses.append({"id": r["id"], "label": r["label"], "text": r["text"]})
        for s in found:
            symptom_counts[s["name"]] += 1
            b["symptoms"][s["name"]] += 1
        for f in a["red_flags"]:
            flag_counts[f["title"]] += 1
    covered = total - len(misses)
    return {
        "source": SOURCE,
        "texts": total,
        "labels": len(per_label),
        "covered": covered,
        "coverage": covered / total,
        "avg_symptoms": sum(per_text) / total,
        "distinct_symptoms": len(symptom_counts),
        "top_symptoms": [{"name": n, "count": c} for n, c in symptom_counts.most_common(15)],
        "red_flags": [{"title": t, "count": c} for t, c in flag_counts.most_common()],
        "texts_with_red_flag": sum(1 for _, a in data if a["red_flags"]),
        "by_label": sorted(
            ({"label": k, "texts": v["texts"], "coverage": v["covered"] / v["texts"],
              "top": [n for n, _ in v["symptoms"].most_common(3)]} for k, v in per_label.items()),
            key=lambda x: (x["coverage"], x["label"]),
        ),
        "misses": misses[:40],
        "miss_count": len(misses),
    }
