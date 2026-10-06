"""Evaluate the extraction engine against hand-annotated texts.

    python evaluation/evaluate.py              # summary tables
    python evaluation/evaluate.py --failures   # also list every mistake
    python evaluation/evaluate.py --save       # write evaluation/results.json

Metrics (per annotation, micro-averaged):
  * Symptom found        - the symptom name was extracted (any status)
  * Found + status       - name, present/absent/uncertain/history and whose symptom it is
  * Details              - for symptoms that are present in both gold and prediction:
                           duration, severity, trend, location and triggers
"""
import datetime as dt
import json
import pathlib
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from nlp import analyze  # noqa: E402

GOLD_PATH = ROOT / "gold.json"
SLOTS = ["duration", "severity", "trend", "location", "triggers"]


# ------------------------------------------------------------------ comparison helpers
def stem_word(w: str) -> str:
    w = w.lower().strip()
    if len(w) > 5 and w.endswith("ing"):
        w = w[:-3]
    return w[:-1] if w.endswith("e") else w


def stem_phrase(p: str) -> str:
    return " ".join(stem_word(w) for w in p.split())


def trigger_match(a: str, b: str) -> bool:
    sa, sb = stem_phrase(a), stem_phrase(b)
    return sa == sb or (min(len(sa), len(sb)) >= 4 and (sa.startswith(sb) or sb.startswith(sa)))


def days_close(g: float, p: float) -> bool:
    return abs(g - p) <= max(0.02, 0.15 * g)


def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f, 4), "tp": tp, "fp": fp, "fn": fn}


def subject_class(subject: str) -> str:
    return "patient" if subject == "patient" else "other"


# ------------------------------------------------------------------ per-case scoring
def score_case(case: dict, ref: dt.date) -> dict:
    pred = analyze(case["text"], ref)["symptoms"]
    gold = case["symptoms"]

    g_names = Counter(g["name"] for g in gold)
    p_names = Counter(p["name"] for p in pred)
    g_assert = Counter((g["name"], g.get("status", "present"), subject_class(g.get("subject", "patient"))) for g in gold)
    p_assert = Counter((p["name"], p["status"] if p["status"] != "resolved" else "absent", subject_class(p["subject"])) for p in pred)

    det_tp = sum((g_names & p_names).values())
    as_tp = sum((g_assert & p_assert).values())
    result = {
        "detection": (det_tp, sum(p_names.values()) - det_tp, sum(g_names.values()) - det_tp),
        "assertion": (as_tp, sum(p_assert.values()) - as_tp, sum(g_assert.values()) - as_tp),
        "slots": {s: [0, 0, 0] for s in SLOTS},
        "problems": [],
    }
    for key in (g_assert - p_assert):
        result["problems"].append(f"missed {key[0]} ({key[1]}{'' if key[2] == 'patient' else ', someone else'})")
    for key in (p_assert - g_assert):
        result["problems"].append(f"extra {key[0]} ({key[1]}{'' if key[2] == 'patient' else ', someone else'})")

    def find_pred(name):
        for p in pred:
            if p["name"] == name and p["status"] == "present" and p["subject"] == "patient":
                return p
        return None

    for g in gold:
        if g.get("status", "present") != "present" or g.get("subject", "patient") != "patient":
            continue
        p = find_pred(g["name"])
        if p is None:
            continue  # already counted as a missed symptom
        slots = result["slots"]

        def tally(slot, gold_val, pred_val, ok):
            if gold_val is None and pred_val is None:
                return
            if gold_val is not None and pred_val is not None and ok:
                slots[slot][0] += 1
            else:
                if pred_val is not None:
                    slots[slot][1] += 1
                if gold_val is not None:
                    slots[slot][2] += 1
                result["problems"].append(f"{g['name']} {slot}: expected {gold_val!r}, got {pred_val!r}")

        gd = g.get("days")
        pd = p["duration"]["days"] if p["duration"] else None
        tally("duration", gd, pd, gd is not None and pd is not None and days_close(gd, pd))
        gs = g.get("severity")
        ps = p["severity"]["label"] if p["severity"] else None
        tally("severity", gs, ps, gs == ps)
        gt = g.get("trend")
        pt = p["trend"]["label"] if p["trend"] else None
        tally("trend", gt, pt, gt == pt)
        gl = g.get("location")
        pl = p["location"]["text"] if p["location"] else None
        tally("location", gl, pl, gl is not None and pl is not None and gl.lower() == pl.lower())

        gtr = list(g.get("triggers", []))
        ptr = [t["object"] for t in p["triggers"]]
        matched = 0
        used = set()
        for x in gtr:
            for k, y in enumerate(ptr):
                if k not in used and trigger_match(x, y):
                    used.add(k)
                    matched += 1
                    break
        slots["triggers"][0] += matched
        slots["triggers"][1] += len(ptr) - matched
        slots["triggers"][2] += len(gtr) - matched
        if matched != len(gtr) or len(ptr) != matched:
            result["problems"].append(f"{g['name']} triggers: expected {gtr!r}, got {ptr!r}")
    return result


# ------------------------------------------------------------------ aggregate
def run_evaluation(gold_path=None) -> dict:
    gold = json.loads(pathlib.Path(gold_path or GOLD_PATH).read_text())
    ref = dt.date.fromisoformat(gold["ref_date"])
    sets = {}
    slot_totals = {s: [0, 0, 0] for s in SLOTS}
    overall = {"detection": [0, 0, 0], "assertion": [0, 0, 0]}
    failures = []
    for case in gold["cases"]:
        res = score_case(case, ref)
        bucket = sets.setdefault(case["set"], {"cases": 0, "detection": [0, 0, 0], "assertion": [0, 0, 0]})
        bucket["cases"] += 1
        for k in ("detection", "assertion"):
            for i in range(3):
                bucket[k][i] += res[k][i]
                overall[k][i] += res[k][i]
        for s in SLOTS:
            for i in range(3):
                slot_totals[s][i] += res["slots"][s][i]
        if res["problems"]:
            failures.append({"id": case["id"], "set": case["set"], "text": case["text"], "kind": f"{len(res['problems'])} issue(s)",
                             "detail": "; ".join(res["problems"])})
    micro = [sum(slot_totals[s][i] for s in SLOTS) for i in range(3)]
    return {
        "dataset": {"cases": len(gold["cases"]), "symptom_annotations": sum(len(c["symptoms"]) for c in gold["cases"]),
                    **{k: v["cases"] for k, v in sets.items()}},
        "overall": {"detection": prf(*overall["detection"]), "assertion": prf(*overall["assertion"]), "slots_micro": prf(*micro)},
        "by_set": {k: {"cases": v["cases"], "detection": prf(*v["detection"]), "assertion": prf(*v["assertion"])} for k, v in sets.items()},
        "slots": {s: prf(*slot_totals[s]) for s in SLOTS},
        "failures": failures,
        "history": gold.get("history", {}),
        "note": ("Three sets are scored. The development set guided the rules. The held-out set was written afterwards, "
                 "but it was used for one round of error analysis, so it no longer counts as unseen. The challenge set holds longer, messier "
                 "texts and was not tuned on, so it is the fairest guide to real use. All sets were annotated by the project author, "
                 "so every number here is optimistic compared with real patient text. The Hindi and Marathi set (20 short texts) and the mixed-language set (10 texts, English with Hinglish, Hindi or Marathi inside one sentence) were written and annotated together with the word list, so they show that the support works, not how well it generalises."),
    }


def main(argv) -> None:
    gold_path = argv[argv.index("--gold") + 1] if "--gold" in argv else None   # e.g. --gold gold_annotated.json
    res = run_evaluation(gold_path)
    d = res["dataset"]
    print(f"{d['cases']} texts, {d['symptom_annotations']} symptom annotations\n")

    def line(name, m):
        print(f"{name:<44}P {m['precision']:.3f}  R {m['recall']:.3f}  F1 {m['f1']:.3f}   (tp {m['tp']}, fp {m['fp']}, fn {m['fn']})")

    line("Symptom found", res["overall"]["detection"])
    line("Symptom found + correct status", res["overall"]["assertion"])
    line("All details (micro)", res["overall"]["slots_micro"])
    print()
    for name, m in res["slots"].items():
        line(f"  {name}", m)
    print()
    for name, m in res["by_set"].items():
        line(f"{name} set ({m['cases']} texts): found+status", m["assertion"])
    if "--failures" in argv:
        print(f"\n{len(res['failures'])} texts with at least one issue:\n")
        for f in res["failures"]:
            print(f"[{f['id']}] {f['text']}\n      {f['detail']}\n")
    if "--save" in argv:
        (ROOT / "results.json").write_text(json.dumps(res, indent=1))
        print("\nSaved evaluation/results.json")


if __name__ == "__main__":
    main(sys.argv[1:])
