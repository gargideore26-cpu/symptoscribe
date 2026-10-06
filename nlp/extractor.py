"""SymptoScribe extraction engine.

Turns a patient's free-text description of their symptoms into structured data
for a doctor.  The pipeline is deliberately transparent (rules + lexicons +
fuzzy matching) so every decision can be explained in a viva:

  1. Normalise text, split sentences, tokenise (with character offsets)
  2. Spelling normalisation and symptom entity recognition (longest match,
     plurals, fuzzy matching, generic "pain in <body part>" patterns)
  3. Clause segmentation
  4. Assertion status: negation (NegEx-style scope), uncertainty,
     past history, and "someone else's symptom"
  5. Attribute extraction: duration, onset, frequency, severity, trend,
     triggers, location, quality, temperature
  6. Attribute-to-symptom linking (clause logic + discourse carry-over)
  7. Context (age, gender, medicines, known conditions), red flags,
     follow-up questions and a natural-language summary
"""
from __future__ import annotations

import datetime as dt
import difflib
import re
from dataclasses import dataclass, field
from typing import Optional

from . import indic
from . import lexicon as L

APOS = str.maketrans({"’": "'", "‘": "'", "`": "'", **indic.DEVANAGARI_DIGITS})   # same length, so offsets never shift
# a "letter" is any alphabetic character plus Devanagari vowel signs and joiners (they are not \w in Python)
_LET = r"(?:[^\W\d_]|[\u0900-\u0963\u0971-\u097F\u200c\u200d])"
TOKEN_RE = re.compile(r"\d+(?:\.\d+)?(?:/\d+)?|" + _LET + r"+(?:'" + _LET + r"+)*|\S", re.UNICODE)
SENT_SPLIT_RE = re.compile(r"[!?\n\u0964\u0965]+|(?<!\d)\.+|\.(?!\d)")
NUM_RE = re.compile(r"^\d+(?:\.\d+)?$")
SCALE_RE = re.compile(r"^(\d{1,2})/10$")


# ------------------------------------------------------------------ helpers
def is_num(s: str) -> bool:
    return bool(NUM_RE.match(s))


def norm_token(s: str) -> str:
    if indic.has_devanagari(s):
        key = indic.deva_key(s)
        return indic.NORMALISE.get(key, key)
    s = s.lower()
    return L.SPELLING.get(s, s)


def tokenize_phrase(s: str) -> tuple:
    return tuple(norm_token(t) for t in TOKEN_RE.findall(s.translate(APOS)))


def build_table(items) -> dict:
    """items: iterable of (phrase, value)."""
    return {tokenize_phrase(p): v for p, v in items}


def table_max(table: dict) -> int:
    return max(len(k) for k in table) if table else 1


@dataclass
class Tok:
    text: str
    norm: str
    start: int
    end: int
    sent: int = 0
    clause: int = 0
    subj: str = "patient"


@dataclass
class Mention:
    name: str
    start: int            # token index (sentence-local)
    end: int              # exclusive
    method: str           # lexicon | fuzzy | plural | pattern | inferred
    conf: float
    sent: int = 0
    clause: int = 0
    status: str = "present"          # present | absent | uncertain | history | resolved
    reason: str = ""
    subject: str = "patient"
    cstart: int = 0       # char offsets in the original text
    cend: int = 0
    attrs: dict = field(default_factory=lambda: {
        "duration": None, "severity": None, "trend": None, "triggers": [], "location": None,
        "radiates_to": None, "quality": [], "frequency": None, "onset": None, "temperature": None})


@dataclass
class Cand:
    kind: str
    start: int
    end: int
    data: dict


# ------------------------------------------------------------------ tables
SYMPTOM_TABLE = build_table((f, canon) for canon, forms in L.SYMPTOMS.items() for f in forms)
SYMPTOM_MAX = table_max(SYMPTOM_TABLE)
SINGLE_SYMPTOM = {k[0]: v for k, v in SYMPTOM_TABLE.items() if len(k) == 1}
FUZZY_TARGETS = [w for w in SINGLE_SYMPTOM if len(w) >= 6 and w.isalpha()]

SEV_TABLE = build_table((w, lab) for lab, ws in L.SEVERITY.items() for w in ws)
SEV_MAX = table_max(SEV_TABLE)
TREND_TABLE = build_table((w, lab) for lab, ws in L.TREND.items() for w in ws)
TREND_MAX = table_max(TREND_TABLE)
ONSET_TABLE = build_table((w, lab) for lab, ws in L.ONSET.items() for w in ws)
ONSET_MAX = table_max(ONSET_TABLE)
LOC_TABLE = build_table((w, w) for w in L.LOCATIONS)
LOC_MAX = table_max(LOC_TABLE)
TRIG_OBJ_TABLE = build_table((w, w) for w in L.TRIGGER_OBJECTS)
TRIG_OBJ_MAX = table_max(TRIG_OBJ_TABLE)
NEG_TABLE = build_table((w, w) for w in L.NEG_TRIGGERS)
NEG_MAX = table_max(NEG_TABLE)
PSEUDO_TABLE = {tuple(p): True for p in L.PSEUDO_NEG}
UNCERTAIN_TABLE = {tuple(p): True for p in L.UNCERTAIN_TRIGGERS}
REL_TABLE = build_table((k, v) for k, v in L.RELATIVE_DAYS.items())
REL_MAX = table_max(REL_TABLE)
MED_TABLE = build_table((w, w) for w in L.MEDICATIONS)
MED_MAX = table_max(MED_TABLE)
COND_TABLE = build_table((w, canon) for canon, ws in L.CONDITIONS.items() for w in ws)
COND_MAX = table_max(COND_TABLE)

POSS_SET = frozenset(L.POSSESSIVES)
PAIN_WORDS_BARE = {"pain", "pains", "ache", "aches"}
PAIN_WORDS_NEEDS_LOC = {"painful", "aching", "hurts", "hurting", "hurt", "paining", "sore", "soreness", "cramps", "cramping", "burning", "tenderness"}
COLD_NOT_SYMPTOM = {"water", "weather", "drink", "drinks", "food", "air", "room", "shower", "bath", "milk", "coffee", "tea", "storage", "wind"}
DUR_CUES = {"for", "since", "from", "past", "last", "over", "nearly", "almost", "about", "around", "approximately", "roughly", "the", "now"}
FREQ_BLOCK = {"times", "time", "once", "twice", "thrice", "per", "every", "each", "x"}
PARTS_OF_DAY = {"morning", "afternoon", "evening", "night"}
ONSET_CUES = {"since", "from", "started", "starting", "began", "begun", "start", "onwards", "onward", "woke", "waking", "till"}
TRIGGER_STOP = {"and", "but", "or", "since", "for", "at", "in", "on", "with", "it", "the", "i", "my", "so", "because", "then", "also", "to", "is", "are", "was", "after", "before", "when", "while", "if", "now", "too", "again", "worse", "better", "this", "that"}
CLAUSE_VERBS = {"is", "are", "was", "has", "have", "gets", "getting", "feels", "becomes", "seems", "keeps", "hurts", "aches", "started", "began"}
CLAUSE_WORDS = {"but", "however", "although", "though", "whereas", "lekin", "par", "magar", "because"}
STRONG_INTENSIFIERS = set(L.INTENSIFIERS)
KNOWN_WORDS = set()
for _t in (SYMPTOM_TABLE, SEV_TABLE, TREND_TABLE, LOC_TABLE, TRIG_OBJ_TABLE, NEG_TABLE, REL_TABLE, MED_TABLE, COND_TABLE):
    for _k in _t:
        KNOWN_WORDS.update(_k)
KNOWN_WORDS.update(L.NUM_WORDS)
KNOWN_WORDS.update(L.UNIT_DAYS)
KNOWN_WORDS.update(L.QUALITY)
KNOWN_WORDS.update(L.WEEKDAYS)


# ------------------------------------------------------------------ tokenising
def split_sentences(text: str):
    spans, pos = [], 0
    for m in SENT_SPLIT_RE.finditer(text):
        if text[pos:m.start()].strip():
            spans.append((pos, m.start()))
        pos = m.end()
    if text[pos:].strip():
        spans.append((pos, len(text)))
    return spans


def tokenize(text: str, s: int, e: int, sent: int):
    toks = []
    for m in TOKEN_RE.finditer(text, s, e):
        raw = m.group(0)
        toks.append(Tok(raw, norm_token(raw), m.start(), m.end(), sent))
    return toks


def longest(table: dict, maxlen: int, toks, i: int, blocked=None):
    """Longest phrase in `table` starting at token i. Returns (length, value)."""
    for ln in range(min(maxlen, len(toks) - i), 0, -1):
        if blocked and any(j in blocked for j in range(i, i + ln)):
            continue
        key = tuple(t.norm for t in toks[i:i + ln])
        if key in table:
            return ln, table[key]
    return 0, None


def span_text(text: str, toks, s: int, e: int) -> str:
    return text[toks[s].start:toks[e - 1].end]


# ------------------------------------------------------------------ step 2: symptom NER
def find_symptom_mentions(toks) -> list:
    mentions, i, n = [], 0, len(toks)
    while i < n:
        ln, canon = longest(SYMPTOM_TABLE, SYMPTOM_MAX, toks, i)
        if ln:
            if canon == "cold" and ln == 1 and i + 1 < n and toks[i + 1].norm in COLD_NOT_SYMPTOM:
                i += 1
                continue
            if toks[i].norm in {"tired", "weak"} and ln == 1 and i + 1 < n and toks[i + 1].norm in {"of", "spot"}:
                i += 1
                continue
            mentions.append(Mention(canon, i, i + ln, "lexicon", 0.95, toks[i].sent))
            i += ln
            continue
        w = toks[i].norm
        if w.isalpha() and w not in KNOWN_WORDS:
            if w.endswith("s") and w[:-1] in SINGLE_SYMPTOM:
                mentions.append(Mention(SINGLE_SYMPTOM[w[:-1]], i, i + 1, "plural", 0.9, toks[i].sent))
                i += 1
                continue
            if len(w) >= 6:
                close = difflib.get_close_matches(w, [x for x in FUZZY_TARGETS if x[0] == w[0]], n=1, cutoff=0.86)
                if close:
                    mentions.append(Mention(SINGLE_SYMPTOM[close[0]], i, i + 1, "fuzzy", 0.7, toks[i].sent))
                    i += 1
                    continue
        i += 1
    return mentions


def find_locations(toks, blocked) -> list:
    """Body-location phrases; adjacent ones are merged ('lower right abdomen')."""
    raw, i, n = [], 0, len(toks)
    while i < n:
        ln, val = longest(LOC_TABLE, LOC_MAX, toks, i, blocked)
        if ln:
            raw.append([i, i + ln])
            i += ln
        else:
            i += 1
    merged = []
    for s, e in raw:
        if merged and s - merged[-1][1] <= 1 and (s == merged[-1][1] or toks[merged[-1][1]].norm in {"the", "of", "side"}):
            merged[-1][1] = e
        else:
            merged.append([s, e])
    return merged


def add_generic_pain(toks, mentions) -> None:
    """'pain in my chest', 'left arm hurts' -> symptom named after the location."""
    covered = {j for m in mentions for j in range(m.start, m.end)}
    locs = find_locations(toks, covered)
    for i, t in enumerate(toks):
        if i in covered:
            continue
        w = t.norm
        if w not in PAIN_WORDS_BARE and w not in PAIN_WORDS_NEEDS_LOC:
            continue
        best, bestd = None, 99
        for ls, le in locs:
            if any(j in covered for j in range(ls, le)):
                continue
            d = (ls - i - 1) if ls > i else (i - le)
            if d <= 3 and d < bestd:
                best, bestd = (ls, le), d
        if best:
            ls, le = best
            loc_text = " ".join(x.norm for x in toks[ls:le])
            name = L.LOCATION_TO_SYMPTOM.get(loc_text) or f"{loc_text} pain"
            s, e = min(i, ls), max(i + 1, le)
            m = Mention(name, s, e, "pattern", 0.8, t.sent)
            m.attrs["location"] = {"text": loc_text, "start": toks[ls].start, "end": toks[le - 1].end}
            mentions.append(m)
            covered.update(range(s, e))
        elif w in PAIN_WORDS_BARE:
            mentions.append(Mention("pain", i, i + 1, "pattern", 0.6, t.sent))
            covered.add(i)
    mentions.sort(key=lambda m: m.start)


# ------------------------------------------------------------------ step 3: clauses
def assign_clauses(toks, mentions) -> None:
    n = len(toks)
    mstarts = {m.start for m in mentions}

    def is_list_comma(i: int) -> bool:
        j = i + 1
        while j < n and toks[j].norm in {"and", "or", "also", "aur", "with", "even", "plus"}:
            j += 1
        if j >= n:
            return False
        if j in mstarts:
            m = next(x for x in mentions if x.start == j)
            after = toks[m.end].norm if m.end < n else ""
            return after not in CLAUSE_VERBS
        w = toks[j].norm
        if (w in L.INTENSIFIERS or w in SEV_TABLE_FIRST) and any(k in mstarts for k in (j + 1, j + 2)):
            return True
        return False

    cid = 0
    for i, t in enumerate(toks):
        w = t.norm
        starts_new = w in CLAUSE_WORDS or (w in {"and", "aur"} and i + 1 < n and toks[i + 1].norm in L.CLAUSE_PRONOUNS)
        if starts_new:
            cid += 1
        t.clause = cid
        if w in {";", ":"} or (w == "," and not is_list_comma(i)):
            cid += 1
    for m in mentions:
        m.clause = toks[m.start].clause


SEV_TABLE_FIRST = {k[0] for k in SEV_TABLE}


# ------------------------------------------------------------------ step 4: assertion status
POST_UNCERTAIN = [("not", "sure"), ("maybe",), ("i", "guess"), ("i", "think"), ("shayad",)]
CONTRAST_ONLY = {"but", "however", "although", "though", "except", "yet", "still", "whereas", "lekin", "par", "magar"}
UNCERTAIN_GLUE = {"i", "i'm", "i've", "it", "it's", "there", "be", "might", "could", "may", "have", "has", "might", "is", "am", "think"}


def _starts_duration(toks, k) -> bool:
    if k >= len(toks):
        return False
    w = toks[k].norm
    if w in {"since", "from"}:
        return True
    return w == "for" and k + 1 < len(toks) and (is_num(toks[k + 1].norm) or toks[k + 1].norm in L.NUM_WORDS)


def _scope_walk(toks, start, mention_at, on_mention, limit=2, terminators=None, extra_glue=frozenset()):
    """Walk right from `start`, calling on_mention(m) for each symptom inside the
    scope.  The scope ends at a terminator, or when a content word / conjunction
    shows that a new idea has started."""
    j, n, nonglue, seen = start, len(toks), 0, 0
    while j < n:
        if j in mention_at:
            m = mention_at[j]
            # "no fever, cough since 2 days": a listed symptom followed by its own duration
            # after a comma starts a new, positive statement
            if seen and j > 0 and toks[j - 1].norm == "," and _starts_duration(toks, m.end):
                break
            seen += 1
            on_mention(m)
            nonglue = 0
            j = m.end
            continue
        w = toks[j].norm
        if w in (terminators if terminators is not None else L.SCOPE_TERMINATORS):
            break
        if w in {"and", "or", "nor", ","} and nonglue > 0:
            break
        if w in L.SCOPE_GLUE or w in extra_glue or w in {",", "-", "/"}:
            j += 1
            continue
        nonglue += 1
        if nonglue > limit:
            break
        j += 1


def mark_status(toks, mentions) -> None:
    mention_at = {m.start: m for m in mentions}
    in_mention = {j for m in mentions for j in range(m.start, m.end)}
    n = len(toks)

    # --- pre-negation triggers
    i = 0
    while i < n:
        if i in in_mention:
            i += 1
            continue
        ln, _ = longest(NEG_TABLE, NEG_MAX, toks, i, in_mention)
        w = toks[i].norm
        if not ln and w.endswith("n't") and w not in {"can't", "won't"}:
            ln = 1
        if ln:
            if any(tuple(x.norm for x in toks[i:i + len(p)]) == p for p in PSEUDO_TABLE):
                i += ln
                continue
            trig = " ".join(x.text for x in toks[i:i + ln])

            def neg(m, trig=trig):
                if m.status == "present":
                    m.status, m.reason = "absent", f"negated by '{trig}'"
            _scope_walk(toks, i + ln, mention_at, neg)
            i += ln
        else:
            i += 1

    # --- post-negation (Hindi style) and resolved
    for idx, m in enumerate(mentions):
        if m.status != "present":
            continue
        nxt = mentions[idx + 1].start if idx + 1 < len(mentions) else n
        for j in range(m.end, min(m.end + 4, nxt, n)):
            w = toks[j].norm
            if w in L.SCOPE_TERMINATORS or w == ",":
                break
            if w in L.POST_NEG_TOKENS:
                m.status, m.reason = "absent", f"negated by '{toks[j].text}'"
                break
            if w in L.RESOLVED_TOKENS:
                m.status, m.reason = "resolved", f"'{toks[j].text}'"
                break
            if any(tuple(x.norm for x in toks[j:j + len(p)]) == tuple(p) for p in L.POST_NEG_PHRASES):
                m.status, m.reason = "absent", "negated after the symptom"
                break
            if any(tuple(x.norm for x in toks[j:j + len(p)]) == tuple(p) for p in POST_UNCERTAIN):
                m.status, m.reason = "uncertain", "hedged after the symptom"
                break

    # --- uncertainty
    for i in range(n):
        for plen in (3, 2, 1):
            key = tuple(x.norm for x in toks[i:i + plen])
            if len(key) == plen and key in UNCERTAIN_TABLE:
                trig = " ".join(x.text for x in toks[i:i + plen])

                def unc(m, trig=trig):
                    if m.status == "present":
                        m.status, m.reason = "uncertain", f"hedged by '{trig}'"
                _scope_walk(toks, i + plen, mention_at, unc, limit=3, terminators=CONTRAST_ONLY, extra_glue=UNCERTAIN_GLUE)
                break


def mark_clause_context(text, toks, mentions) -> None:
    """Subject (patient / someone else) and past-history, decided per clause."""
    by_clause = {t.clause: [] for t in toks}
    for m in mentions:
        by_clause.setdefault(m.clause, []).append(m)
    for cid, ms in by_clause.items():
        ctoks = [t for t in toks if t.clause == cid]
        words = [t.norm for t in ctoks]
        first_person = any(w in L.FIRST_PERSON for w in words)
        subject = "patient"
        for k, w in enumerate(words):
            if w in L.FAMILY_NOUNS and any(x in POSS_SET for x in words[max(0, k - 5):k]):
                subject = w
                break
        if subject == "patient" and not first_person and any(w in {"he", "she", "his", "her"} for w in words):
            subject = "someone else"
        for t in ctoks:
            t.subj = subject
        joined = " ".join(words)
        history = any(p in joined for p in L.HISTORY_STRONG)
        if not history and any(p in joined for p in L.HISTORY_WEAK):
            history = not any(c in words or c in joined for c in L.CURRENT_CUES)
        for m in ms:
            m.subject = subject
            if history and m.status == "present":
                m.status, m.reason = "history", "past episode"


# ------------------------------------------------------------------ step 5: attribute candidates
def find_temperatures(toks, used) -> list:
    out = []
    for i, t in enumerate(toks):
        if i in used or not is_num(t.norm):
            continue
        v = float(t.norm)
        unit = None
        if 95 <= v <= 110:
            unit = "F"
        elif 35 <= v <= 42:
            unit = "C"
        else:
            continue
        nxt = toks[i + 1].norm if i + 1 < len(toks) else ""
        prv = toks[i - 1].norm if i > 0 else ""
        if nxt in L.UNIT_DAYS or prv in {"for", "since", "last", "past"}:
            continue
        has_unit = nxt in L.TEMP_UNITS
        has_word = any(toks[k].norm in L.TEMP_WORDS for k in range(max(0, i - 3), i))
        if not (has_unit or has_word):
            continue
        end = i + 2 if has_unit else i + 1
        if has_unit and nxt in {"degree", "degrees", "deg"} and i + 2 < len(toks) and toks[i + 2].norm in {"f", "c", "fahrenheit", "celsius"}:
            end = i + 3
            if toks[i + 2].norm in {"c", "celsius"}:
                unit = "C"
            else:
                unit = "F"
        elif has_unit and nxt in {"c", "celsius", "°c"}:
            unit = "C"
        elif has_unit and nxt in {"f", "fahrenheit", "°f"}:
            unit = "F"
        elif unit == "C" and v > 42:
            continue
        celsius = v if unit == "C" else (v - 32) * 5 / 9
        out.append(Cand("temperature", i, end, {"value": v, "unit": unit, "celsius": round(celsius, 1)}))
        used.update(range(i, end))
    return out


def find_frequencies(toks, used) -> list:
    out, n = [], len(toks)

    def unit_tail(k):
        if k < n and toks[k].norm in {"a", "per", "in", "every", "each"}:
            k2 = k + 1
            if k2 < n and toks[k2].norm in {"a", "an", "the", "one"}:
                k2 += 1
            if k2 < n and toks[k2].norm in L.UNIT_DAYS:
                return k2 + 1
        return None

    for i, t in enumerate(toks):
        if i in used:
            continue
        w = t.norm
        s = e = None
        if w == "times" and i > 0 and (is_num(toks[i - 1].norm) or toks[i - 1].norm in L.NUM_WORDS or toks[i - 1].norm in {"many", "several", "multiple", "few"}):
            s, e = i - 1, i + 1
            if s >= 2 and toks[s - 1].norm in {"-", "to", "or"} and is_num(toks[s - 2].norm):
                s -= 2
            tail = unit_tail(e)
            if tail:
                e = tail
        elif w in {"once", "twice", "thrice"}:
            tail = unit_tail(i + 1)
            if tail:
                s, e = i, tail
            elif w != "once":
                s, e = i, i + 1
        elif w == "every" and i + 1 < n:
            k = i + 1
            if is_num(toks[k].norm) or toks[k].norm in L.NUM_WORDS:
                k += 1
            if k < n and toks[k].norm in L.UNIT_DAYS:
                s, e = i, k + 1
        elif w in {"daily", "nightly", "hourly"}:
            s, e = i, i + 1
        if s is not None and not any(j in used for j in range(s, e)):
            out.append(Cand("frequency", s, e, {}))
            used.update(range(s, e))
    return out


def find_scale_severity(toks, used) -> list:
    out = []
    for i, t in enumerate(toks):
        if i in used:
            continue
        score = None
        end = i + 1
        m = SCALE_RE.match(t.norm)
        if m and int(m.group(1)) <= 10:
            score = int(m.group(1))
        elif is_num(t.norm) and i + 3 < len(toks) + 0 and toks[i + 1].norm == "out" and toks[i + 2].norm == "of" and toks[i + 3].norm == "10":
            score, end = int(float(t.norm)), i + 4
        if score is not None:
            label = "severe" if score >= 8 else "moderate" if score >= 4 else "mild"
            out.append(Cand("severity", i, end, {"label": label, "source": "scale", "scale": score}))
            used.update(range(i, end))
    return out


def find_durations(toks, used, ref: dt.date, mention_idx=frozenset()) -> list:
    out, n = [], len(toks)

    def claim(s, e, lo, hi, kind):
        out.append(Cand("duration", s, e, {"days_min": lo, "days_max": hi, "kind": kind}))
        used.update(range(s, e))

    # A) quantity + unit
    for j, t in enumerate(toks):
        if j in used or t.norm not in L.UNIT_DAYS:
            continue
        unit = L.UNIT_DAYS[t.norm]
        prev = toks[j - 1].norm if j > 0 else ""
        s, lo, hi = j, None, None
        if j > 0 and is_num(prev):
            lo = hi = float(prev)
            s = j - 1
            if j >= 3 and toks[j - 2].norm in {"-", "to", "or"} and is_num(toks[j - 3].norm):
                lo, s = float(toks[j - 3].norm), j - 3
        elif j > 0 and prev in L.NUM_WORDS:
            lo = hi = L.NUM_WORDS[prev]
            s = j - 1
            if prev in {"few", "couple", "several"} and s > 0 and toks[s - 1].norm == "a":
                s -= 1
        elif j > 1 and prev == "of" and toks[j - 2].norm in {"couple", "few"}:
            lo = hi = L.NUM_WORDS[toks[j - 2].norm]
            s = j - 2
            if s > 0 and toks[s - 1].norm == "a":
                s -= 1
        elif prev in {"last", "past", "this"} and t.norm in {"week", "month", "year"}:
            lo = hi = 1
            s = j - 1
        else:
            continue
        pre = toks[s - 1].norm if s > 0 else ""
        after = toks[j + 1].norm if j + 1 < n else ""
        if pre in FREQ_BLOCK or after == "old" or any(k in used for k in range(s, j + 1)):
            continue
        # extend over cue words on the left and "ago/now" on the right
        steps = 0
        while s > 0 and steps < 3 and toks[s - 1].norm in DUR_CUES and (s - 1) not in used:
            s -= 1
            steps += 1
        e = j + 1
        if e < n and toks[e].norm in {"ago", "now", "back", "se", "tak"}:
            e += 1
        claim(s, e, lo * unit, hi * unit, "quantity")

    # B) relative phrases (yesterday, this morning, kal se ...)
    i = 0
    while i < n:
        if i in used:
            i += 1
            continue
        ln, days = longest(REL_TABLE, REL_MAX, toks, i, used)
        if ln:
            first = toks[i].norm
            cue_ok = (first == "since" or i <= 1 or any(toks[k].norm in ONSET_CUES for k in range(max(0, i - 3), i))
                      or any(k in mention_idx for k in (i - 1, i - 2)))
            if first in {"kal", "aaj", "parso"}:
                cue_ok = i + ln < n and toks[i + ln].norm == "se"
            if cue_ok:
                e = i + ln
                if first in {"yesterday", "kal"} and e < n and toks[e].norm in PARTS_OF_DAY:
                    e += 1
                if e < n and toks[e].norm == "se":
                    e += 1
                s = i
                if s > 0 and toks[s - 1].norm in {"since", "from", "started", "began", "begun", "starting"} and (s - 1) not in used:
                    s -= 1
                d = 0.5 if days == 0 else float(days)
                claim(s, e, d, d, "relative")
                i = e
                continue
        # C) weekday names
        w = toks[i].norm
        if w in L.WEEKDAYS and any(toks[k].norm in {"since", "from", "on", "last", "started", "began", "begun"} for k in range(max(0, i - 3), i)):
            diff = (ref.weekday() - L.WEEKDAYS[w]) % 7 or 7
            s = i
            while s > 0 and toks[s - 1].norm in {"since", "from", "on", "last", "started", "began", "begun"} and (s - 1) not in used:
                s -= 1
            if i + 1 < n and toks[i + 1].norm in PARTS_OF_DAY:
                e = i + 2
            else:
                e = i + 1
            claim(s, e, float(diff), float(diff), "weekday")
            i = e
            continue
        i += 1
    return out


def find_simple_candidates(toks, used, mention_idx, mention_starts=frozenset()) -> list:
    """Onset, triggers, trend, severity words, locations and quality."""
    out, n = [], len(toks)
    blocked = set(used) | set(mention_idx)

    # onset
    i = 0
    while i < n:
        ln, val = longest(ONSET_TABLE, ONSET_MAX, toks, i, blocked)
        if ln:
            out.append(Cand("onset", i, i + ln, {"label": val}))
            blocked.update(range(i, i + ln))
            i += ln
        else:
            i += 1

    # triggers: cue [fillers] object
    i = 0
    while i < n:
        w = toks[i].norm
        if w in L.TRIGGER_CUES and i not in blocked:
            k = i + 1
            while k < n and toks[k].norm in L.TRIGGER_FILLERS and k - i <= 3:
                k += 1
            ln, obj = longest(TRIG_OBJ_TABLE, TRIG_OBJ_MAX, toks, k, blocked)
            if ln:
                s = i
                effect = "occurs"
                back = [toks[x].norm for x in range(max(0, i - 3), i)]
                if any(b in L.RELIEVE_WORDS for b in back) or w == "relieved":
                    effect = "relieves"
                elif any(b in L.WORSEN_WORDS for b in back) or w in {"triggered", "aggravated", "caused", "worsened", "brought", "induced"}:
                    effect = "worsens"
                for x in range(max(0, i - 3), i):
                    if toks[x].norm in L.RELIEVE_WORDS + L.WORSEN_WORDS and x not in blocked:
                        s = x
                        if x > 0 and toks[x - 1].norm in L.NEGATORS_FOR_SEVERITY and effect == "relieves":
                            effect, s = "no_relief", x - 1
                        break
                end = k + ln
                if obj in {"eating", "eat", "drinking", "drink"}:
                    while end < n and end - (k + ln) < 2 and toks[end].norm.isalpha() and toks[end].norm not in TRIGGER_STOP and end not in blocked:
                        end += 1
                    obj = " ".join(x.norm for x in toks[k:end])
                out.append(Cand("trigger", s, end, {"effect": effect, "object": obj}))
                blocked.update(range(s, end))
                i = end
                continue
        i += 1

    # trend
    i = 0
    while i < n:
        ln, val = longest(TREND_TABLE, TREND_MAX, toks, i, blocked)
        if ln:
            back = [toks[x].norm for x in range(max(0, i - 2), i)]
            if any(b in L.NEGATORS_FOR_SEVERITY or b.endswith("n't") for b in back):
                val = {"improving": "not improving", "worsening": "stable"}.get(val, val)
            out.append(Cand("trend", i, i + ln, {"label": val}))
            blocked.update(range(i, i + ln))
            i += ln
        else:
            i += 1

    # severity words (+ intensifier, negation)
    i = 0
    while i < n:
        ln, lab = longest(SEV_TABLE, SEV_MAX, toks, i, blocked)
        if ln:
            s = i
            prev = toks[i - 1].norm if i > 0 else ""
            prev2 = toks[i - 2].norm if i > 1 else ""
            if prev in L.NEGATORS_FOR_SEVERITY or prev2 in L.NEGATORS_FOR_SEVERITY or prev.endswith("n't"):
                blocked.update(range(i, i + ln))
                i += ln
                continue
            if prev in STRONG_INTENSIFIERS and (i - 1) not in blocked:
                s = i - 1
                lab = {"mild": "moderate", "moderate": "severe", "severe": "severe"}[lab]
            out.append(Cand("severity", s, i + ln, {"label": lab, "source": "word"}))
            blocked.update(range(s, i + ln))
            i += ln
        else:
            i += 1

    # a strong intensifier right before a symptom ("very weak") signals at least moderate severity
    for i, t in enumerate(toks):
        if t.norm in STRONG_INTENSIFIERS and i not in blocked and (i + 1) in mention_starts:
            out.append(Cand("severity", i, i + 1, {"label": "moderate", "source": "intensifier"}))
            blocked.add(i)

    # locations (+ radiation words)
    for ls, le in find_locations(toks, blocked):
        radiate = any(toks[x].norm in L.RADIATION_WORDS for x in range(max(0, ls - 3), ls))
        s = ls
        if radiate:
            for x in range(max(0, ls - 3), ls):
                if toks[x].norm in L.RADIATION_WORDS:
                    s = x
                    break
        out.append(Cand("radiation" if radiate else "location", s, le, {"text": " ".join(x.norm for x in toks[ls:le])}))
        blocked.update(range(s, le))

    # quality (allowed inside a symptom surface, e.g. "stomach has been burning")
    for i, t in enumerate(toks):
        if t.norm in L.QUALITY and i not in used:
            out.append(Cand("quality", i, i + 1, {"label": t.norm}))
    return out


# ------------------------------------------------------------------ step 6: linking
FOLLOW_KINDS = {"duration", "trend", "trigger", "frequency", "onset"}
ADJ_KINDS = {"severity", "location", "radiation", "quality"}
BE_FILLERS = {"is", "are", "was", "has", "been", "being", "feels", "feel", "feeling", "seems", "very", "really", "extremely", "quite", "so", "too",
              "a", "bit", "little", "getting", "become", "becomes", "became", "gets", "also", "pretty"}


def _dist(m: Mention, c: Cand) -> int:
    return max(m.start - c.end, c.start - m.end, 0)


def _attach(m: Mention, c: Cand, text: str, toks) -> None:
    cs, ce = toks[c.start].start, toks[c.end - 1].end
    base = {"text": text[cs:ce], "start": cs, "end": ce}
    a = m.attrs
    if c.kind == "duration":
        if a["duration"] is None:
            a["duration"] = {**base, "days_min": c.data["days_min"], "days_max": c.data["days_max"], "days": c.data["days_max"], "kind": c.data["kind"]}
    elif c.kind == "frequency":
        if a["frequency"] is None:
            a["frequency"] = base
    elif c.kind == "onset":
        if a["onset"] is None:
            a["onset"] = {**base, "label": c.data["label"]}
    elif c.kind == "trend":
        if a["trend"] is None:
            a["trend"] = {**base, "label": c.data["label"]}
    elif c.kind == "trigger":
        a["triggers"].append({**base, "effect": c.data["effect"], "object": c.data["object"]})
    elif c.kind == "severity":
        score = L.SEVERITY_SCORE[c.data["label"]]
        if a["severity"] is None or score > a["severity"]["score"]:
            a["severity"] = {**base, "label": c.data["label"], "score": score, "source": c.data["source"]}
    elif c.kind == "location":
        if a["location"] is None:
            a["location"] = {**base, "text": c.data["text"]}
    elif c.kind == "radiation":
        if a["radiates_to"] is None:
            a["radiates_to"] = {**base, "text": c.data["text"]}
    elif c.kind == "quality":
        if not any(q["label"] == c.data["label"] for q in a["quality"]):
            a["quality"].append({**base, "label": c.data["label"]})


LOC_FILLERS = {"on", "in", "at", "my", "the", "of", "over", "around", "near", "both", "a", "his", "her", "all"}
LIST_GLUE = {"and", "or", ",", "also", "with", "aur", "plus", "&", "along"}


def _group_before(c, elig, toks, cand_tokens):
    """Mentions that form one coordinated group ending right before candidate c.
    'fever and headache since 2 days' -> both; tokens that belong to other
    candidates (e.g. 'mild' in 'and mild fever') do not break the group."""
    preceding = [m for m in elig if m.end <= c.start]
    if not preceding:
        return []
    group = [preceding[-1]]
    for prev in reversed(preceding[:-1]):
        gap = range(prev.end, group[0].start)
        if all(toks[k].norm in LIST_GLUE or k in cand_tokens for k in gap):
            group.insert(0, prev)
        else:
            break
    return group


def link_candidates(text, toks, mentions, cands, state) -> list:
    """Attach candidates to mentions.  Returns candidates that could not be linked."""
    unlinked = []
    by_clause = {}
    for m in mentions:
        by_clause.setdefault(m.clause, []).append(m)
    cand_by_clause = {}
    for c in cands:
        cand_by_clause.setdefault(toks[c.start].clause, []).append(c)
    cand_tokens = {k for c in cands for k in range(c.start, c.end)}
    local_group = []

    for cid in sorted(set(by_clause) | set(cand_by_clause)):
        elig = [m for m in by_clause.get(cid, []) if m.status != "absent"]
        ccs = cand_by_clause.get(cid, [])
        if not ccs:
            if elig:
                local_group = elig
            continue
        if not elig:
            # discourse carry-over: attach to the most recent symptom group
            words = {t.norm for t in toks if t.clause == cid}
            group = local_group or state.get("last_group", [])
            first = next((k for k, t in enumerate(toks) if t.clause == cid and t.norm not in {"and", "but", ",", "also", "then", "aur"}), None)
            fragment = first is not None and any(c.start <= first for c in ccs)
            if ((words & set(L.FIRST_PERSON)) and not fragment) or not group:
                unlinked.extend(ccs)      # the patient starts a new idea; do not guess
                continue
            plural = bool(words & {"they", "these", "all", "sab", "both", "dono", "those"})
            singular = bool(words & {"it", "this", "that", "yeh", "woh", "ye"})
            for c in ccs:
                if c.kind in ADJ_KINDS and not plural:
                    _attach(group[-1], c, text, toks)
                else:
                    for m in (group if (plural or not singular) else [group[-1]]):
                        _attach(m, c, text, toks)
            continue

        for kind in FOLLOW_KINDS | ADJ_KINDS:
            kc = [c for c in ccs if c.kind == kind]
            for c in kc:
                lead = next((m for m in elig if 0 <= m.start - c.end <= 1 and all(toks[k].norm not in LIST_GLUE for k in range(c.end, m.start))), None) if kind == "trend" else None
                if lead is not None:                     # "persistent dry cough"
                    targets = [lead]
                elif kind in FOLLOW_KINDS:
                    if len(elig) == 1:
                        targets = [elig[0]]
                    else:
                        preceding = [m for m in elig if m.end <= c.start]
                        trailing = c.start >= elig[-1].end
                        if preceding:
                            if trailing and len(kc) == 1:
                                targets = elig
                            elif len(kc) == 1:
                                targets = _group_before(c, elig, toks, cand_tokens)
                            else:
                                targets = [preceding[-1]]
                        else:
                            targets = elig if len(kc) == 1 else [min(elig, key=lambda m: _dist(m, c))]
                else:
                    target = None
                    for m in elig:                       # pre-modifier: "severe headache"
                        if m.start == c.end:
                            target = m
                            break
                    if target is None and kind == "location":      # "rash on my arms"
                        k = c.start - 1
                        while k >= 0 and toks[k].norm in LOC_FILLERS:
                            k -= 1
                        for m in elig:
                            if m.end == k + 1 and k + 1 < c.start:
                                target = m
                                break
                    if target is None:                   # predicate: "headache is severe"
                        k = c.start - 1
                        while k >= 0 and toks[k].norm in BE_FILLERS:
                            k -= 1
                        for m in elig:
                            if m.end == k + 1:
                                target = m
                                break
                    if target is None:
                        target = min(elig, key=lambda m: (_dist(m, c), 0 if m.start >= c.end else 1))
                    targets = [target]
                for m in targets:
                    _attach(m, c, text, toks)
        local_group = elig
    return unlinked


# ------------------------------------------------------------------ one sentence
def process_sentence(text, toks, state, ref):
    mentions = find_symptom_mentions(toks)
    add_generic_pain(toks, mentions)
    assign_clauses(toks, mentions)
    mark_status(toks, mentions)
    mark_clause_context(text, toks, mentions)

    mention_idx = {j for m in mentions for j in range(m.start, m.end)}
    used = set()
    temps = find_temperatures(toks, used | mention_idx)
    for c in temps:
        used.update(range(c.start, c.end))
    freqs = find_frequencies(toks, used | mention_idx)
    for c in freqs:
        used.update(range(c.start, c.end))
    scales = find_scale_severity(toks, used | mention_idx)
    for c in scales:
        used.update(range(c.start, c.end))
    durs = find_durations(toks, used | mention_idx, ref, mention_idx)
    for c in durs:
        used.update(range(c.start, c.end))
    simple = find_simple_candidates(toks, used, mention_idx, {m.start for m in mentions})

    # a trend word followed directly by a trigger ("worse after eating") is the trigger's effect
    trig_starts = {c.start for c in simple if c.kind == "trigger"}
    simple = [c for c in simple if not (c.kind == "trend" and c.end in trig_starts)]

    for m in mentions:
        m.cstart, m.cend = toks[m.start].start, toks[m.end - 1].end

    # temperature readings: attach to fever in this sentence, else the latest fever
    for c in temps:
        fevers = [m for m in mentions if m.name == "fever" and m.status != "absent"]
        if not fevers:
            fevers = [m for m in reversed(state["all"]) if m.name == "fever" and m.status != "absent"][:1]
        if not fevers and c.data["celsius"] >= 38.0:
            fm = Mention("fever", c.start, c.end, "inferred", 0.7, toks[0].sent)
            fm.cstart, fm.cend = toks[c.start].start, toks[c.end - 1].end
            fm.clause = toks[c.start].clause
            mentions.append(fm)
            fevers = [fm]
        for fm in fevers[:1]:
            if fm.attrs["temperature"] is None:
                fm.attrs["temperature"] = {"text": text[toks[c.start].start:toks[c.end - 1].end], "start": toks[c.start].start,
                                           "end": toks[c.end - 1].end, "celsius": c.data["celsius"], "value": c.data["value"], "unit": c.data["unit"]}
                if fm.attrs["severity"] is None:
                    cel = c.data["celsius"]
                    lab = "severe" if cel >= 39.4 else "moderate" if cel >= 38.0 else "mild"
                    fm.attrs["severity"] = {"text": fm.attrs["temperature"]["text"], "start": fm.attrs["temperature"]["start"],
                                            "end": fm.attrs["temperature"]["end"], "label": lab, "score": L.SEVERITY_SCORE[lab], "source": "temperature"}
    mentions.sort(key=lambda m: m.start)

    unlinked = link_candidates(text, toks, mentions, simple + freqs + scales + durs, state)

    live = [m for m in mentions if m.status not in ("absent",) and m.subject == "patient"]
    if live:
        last_clause = max(m.clause for m in live)
        state["last_group"] = [m for m in live if m.clause == last_clause]
    state["all"].extend(mentions)
    return mentions, unlinked


# ------------------------------------------------------------------ step 7: context, flags, summary
def extract_context(text, toks_all, symptom_spans) -> dict:
    low = text.translate(APOS)
    ctx = {"age": None, "gender": None, "medications": [], "conditions": [], "allergies": [], "spans": []}
    ctx["age_months"] = None
    ctx["age_label"] = None
    inf = re.search(r"(\d{1,2})\s*[- ]?\s*(months?|mos?|weeks?|wks?|days?)\s*[- ]?\s*old", low, re.I)
    m = re.search(r"(\d{1,3})\s*[- ]?\s*(?:years?|yrs?|y/o|yo)\s*[- ]?\s*old", low, re.I)
    if inf and not m:
        n, unit = int(inf.group(1)), inf.group(2).lower()
        months = n if unit.startswith("mo") else (n / 4.3 if unit.startswith(("week", "wk")) else n / 30)
        if 0 < n and months < 24:
            ctx["age"] = 0 if months < 12 else int(months // 12)
            ctx["age_months"] = round(months, 1)
            ctx["age_label"] = f"{n}-{unit.rstrip('s')}-old"
            ctx["spans"].append({"label": "context", "start": inf.start(), "end": inf.end(), "text": low[inf.start():inf.end()]})
    if not m and not inf:
        m = re.search(r"\bage\s*(?:is|:)?\s*(\d{1,3})\b", low, re.I)
    if not m:
        m = re.search(r"\bi(?:'m| am)\s+(\d{1,3})\b(?!\s*(?:days?|hours?|weeks?|months?|kg|cm|%|/|years? of))", low, re.I)
    if m and 0 < int(m.group(1)) < 120 and ctx["age_label"] is None:
        ctx["age"] = int(m.group(1))
        ctx["age_months"] = ctx["age"] * 12
        ctx["age_label"] = f"{ctx['age']}-year-old"
        ctx["spans"].append({"label": "context", "start": m.start(), "end": m.end(), "text": low[m.start():m.end()]})
    g = re.search(r"\b(?:i(?:'m| am)\s+(?:a\s+|an\s+)?(?:\d{1,3}\s*[- ]?\s*(?:years?|yrs?)\s*[- ]?\s*old\s+)?)(male|female|man|woman|boy|girl)\b", low, re.I)
    if not g:
        g = re.search(r"\b\d{1,3}\s*[- ]?\s*(?:years?|yrs?)\s*[- ]?\s*old\s+(male|female|man|woman|boy|girl)\b", low, re.I)
    if not g:
        g = re.search(r"\bgender\s*(?:is|:)?\s*(male|female)\b", low, re.I)
    if g:
        word = g.group(1).lower()
        ctx["gender"] = "male" if word in {"male", "man", "boy"} else "female"
        ctx["spans"].append({"label": "context", "start": g.start(1), "end": g.end(1), "text": g.group(1)})
    for a in re.finditer(r"allergic to ([a-z]+(?: [a-z]+)?)", low, re.I):
        name = re.split(r"\b(?:and|but|since|for|from)\b", a.group(1))[0].strip()
        if name:
            ctx["allergies"].append(name)
            ctx["spans"].append({"label": "condition", "start": a.start(), "end": a.start() + len("allergic to ") + len(name), "text": low[a.start():a.start() + len("allergic to ") + len(name)]})
    for toks in toks_all:
        blocked = set()
        i = 0
        while i < len(toks):
            if toks[i].subj != "patient":
                i += 1
                continue
            ln, med = longest(MED_TABLE, MED_MAX, toks, i)
            if ln:
                name = " ".join(t.text for t in toks[i:i + ln])
                if name.lower() not in [x.lower() for x in ctx["medications"]]:
                    ctx["medications"].append(name)
                ctx["spans"].append({"label": "medication", "start": toks[i].start, "end": toks[i + ln - 1].end, "text": name})
                i += ln
                continue
            ln, cond = longest(COND_TABLE, COND_MAX, toks, i)
            if ln:
                if cond not in ctx["conditions"]:
                    ctx["conditions"].append(cond)
                ctx["spans"].append({"label": "condition", "start": toks[i].start, "end": toks[i + ln - 1].end, "text": " ".join(t.text for t in toks[i:i + ln])})
                i += ln
                continue
            i += 1
    return ctx


def evaluate_red_flags(records, text) -> list:
    low = text.lower().translate(APOS)
    present = [r for r in records if r["status"] == "present" and r["subject"] == "patient"]
    names = {r["name"] for r in present}
    flags = []
    for rule in L.RED_FLAGS:
        hit, evidence = False, []
        if rule.get("modifier_only"):
            hit = any(mod in low for mod in rule["modifiers"])
            evidence = [mod for mod in rule["modifiers"] if mod in low][:1]
        elif rule.get("severe_any"):
            sev = [r["name"] for r in present if r["severity"] and r["severity"]["label"] == "severe"]
            hit, evidence = bool(sev), sev
        else:
            for r in present:
                if r["name"] not in rule["any_symptoms"]:
                    continue
                if rule.get("min_days"):
                    d = r["duration"]["days"] if r["duration"] else None
                    if d is None or d < rule["min_days"]:
                        continue
                if rule["modifiers"] and not any(mod in low for mod in rule["modifiers"]):
                    continue
                hit = True
                evidence.append(r["name"])
        if hit:
            flags.append({"id": rule["id"], "title": rule["title"], "level": rule["level"], "advice": rule["advice"], "evidence": evidence})
    flags.sort(key=lambda f: -L.LEVEL_RANK[f["level"]])
    return flags


# ------------------------------------------------------------------ age-aware red flags
def _present(records, *names):
    return [r for r in records if r["status"] == "present" and r["name"] in names]


def age_flags(records, ctx) -> list:
    """Safety rules that depend on age or pregnancy. They raise attention, they never name a disease."""
    months = ctx.get("age_months")
    flags = []

    def add(rid, title, level, advice, evidence, why):
        flags.append({"id": rid, "title": title, "level": level, "advice": advice, "evidence": [r["name"] for r in evidence], "why": why})

    fever = _present(records, "fever")
    gi = _present(records, "vomiting", "diarrhea")
    dizzy = _present(records, "dizziness", "fainting")
    pregnant = "pregnancy" in ctx.get("conditions", [])
    if months is not None:
        label = ctx["age_label"]
        if months < 3 and fever:
            add("AG1", "Fever in a very young baby", "emergency", "Fever in a baby under 3 months needs emergency evaluation.", fever, f"Age: {label}")
        elif months < 12 and fever:
            add("AG1", "Fever in an infant", "urgent", "Fever in an infant should be assessed the same day.", fever, f"Age: {label}")
        elif months < 60 and fever:
            days = max((r["duration"]["days"] for r in fever if r["duration"]), default=0)
            add("AG2", "Fever in a young child", "urgent" if days >= 2 else "attention",
                "Fever in a young child that lasts more than a day or two should be assessed.", fever, f"Age: {label}")
        if months >= 65 * 12 and fever:
            add("AG3", "Fever in an older adult", "urgent", "Older adults can become seriously ill with fever and may show few other signs.", fever, f"Age: {label}")
        if (months < 60 or months >= 65 * 12) and gi:
            add("AG4", "Vomiting or loose motions at this age", "urgent", "Dehydration develops faster in young children and older adults.", gi, f"Age: {label}")
        if months >= 65 * 12 and dizzy:
            add("AG5", "Dizziness or fainting in an older adult", "urgent", "Dizziness at this age raises the risk of falls and may reflect blood pressure or heart rhythm problems.", dizzy, f"Age: {label}")
    if pregnant:
        bleed = _present(records, "bleeding")
        if bleed:
            add("AG6", "Bleeding in pregnancy", "emergency", "Any bleeding in pregnancy needs urgent medical assessment.", bleed, "Pregnancy mentioned")
        pain = _present(records, "stomach pain", "back pain")
        if pain:
            add("AG7", "Abdominal or back pain in pregnancy", "urgent", "Pain in pregnancy should be assessed promptly.", pain, "Pregnancy mentioned")
        pre = _present(records, "headache")
        if pre and _present(records, "swelling", "blurred vision"):
            add("AG8", "Headache with swelling or blurred vision in pregnancy", "emergency", "This combination in pregnancy needs urgent assessment of blood pressure.", pre, "Pregnancy mentioned")
        if fever:
            add("AG9", "Fever in pregnancy", "urgent", "Fever in pregnancy needs prompt evaluation.", fever, "Pregnancy mentioned")
    return flags


# ------------------------------------------------------------------ vitals
VITAL_LABEL = {"bp": "Blood pressure", "pulse": "Pulse", "spo2": "Oxygen saturation", "rr": "Respiratory rate",
               "temp": "Temperature", "weight": "Weight", "glucose": "Blood sugar"}
_SEP = r"(?:\s*(?:is|was|of|at|around|about|approx|reading|showing|shows|=|:|-)\s*)*\s*"
VITAL_PATTERNS = [
    ("bp", re.compile(r"\b(?:bp|b\.p\.?|blood pressure)" + _SEP + r"(\d{2,3})\s*/\s*(\d{2,3})\b(?:\s*mm\s*hg)?", re.I)),
    ("bp", re.compile(r"\b(\d{2,3})\s*/\s*(\d{2,3})\s*mm\s*hg\b", re.I)),
    ("pulse", re.compile(r"\b(?:pulse(?: rate)?|heart rate|hr)" + _SEP + r"(\d{2,3})\b(?:\s*(?:bpm|/min|per minute|beats(?: per minute)?))?", re.I)),
    ("pulse", re.compile(r"\b(\d{2,3})\s*(?:bpm|beats per minute)\b", re.I)),
    ("spo2", re.compile(r"\b(?:spo\s?2|sp02|o2 sat(?:uration)?|oxygen(?: level| saturation| sat)?|saturation)" + _SEP + r"(\d{2,3})\s*%?", re.I)),
    ("spo2", re.compile(r"\b(\d{2,3})\s*%\s*(?:spo\s?2|oxygen|saturation)", re.I)),
    ("rr", re.compile(r"\b(?:rr|resp(?:iratory)? rate|breathing rate)" + _SEP + r"(\d{1,2})\b(?:\s*(?:/min|per minute|breaths))?", re.I)),
    ("weight", re.compile(r"\b(?:weight|weighs?|weighed|wt)" + _SEP + r"(\d{2,3}(?:\.\d)?)\s*(kg|kgs|kilos?|lbs?|pounds)\b", re.I)),
    ("glucose", re.compile(r"\b(?:blood sugar|sugar|glucose|bsl|rbs|fbs|ppbs)(?: level)?" + _SEP + r"(\d{2,3})\b(?:\s*mg\s*/?\s*dl)?", re.I)),
]


def _status(kind, v, v2=None, fasting=False):
    """-> (status, note). status is normal | low | high | critical."""
    if kind == "bp":
        if v >= 180 or v2 >= 120:
            return "critical", "very high (180/120 or above)"
        if v >= 140 or v2 >= 90:
            return "high", "above 140/90"
        if v < 90 or v2 < 60:
            return "low", "below 90/60"
        return "normal", "within 90/60 to 140/90"
    if kind == "pulse":
        if v > 130 or v < 40:
            return "critical", "far outside 60 to 100"
        if v > 100:
            return "high", "above 100 per minute"
        if v < 60:
            return "low", "below 60 per minute"
        return "normal", "60 to 100 per minute"
    if kind == "spo2":
        if v < 90:
            return "critical", "below 90%"
        if v < 95:
            return "low", "below 95%"
        return "normal", "95% or above"
    if kind == "rr":
        if v > 30 or v < 8:
            return "critical", "far outside 12 to 20"
        if v > 20:
            return "high", "above 20 per minute"
        if v < 12:
            return "low", "below 12 per minute"
        return "normal", "12 to 20 per minute"
    if kind == "glucose":
        if v < 54 or v > 400:
            return "critical", "dangerously low or high"
        if v < 70:
            return "low", "below 70 mg/dL"
        if v >= (126 if fasting else 200):
            return "high", ("126 mg/dL or above when fasting" if fasting else "200 mg/dL or above")
        return "normal", "in the usual range"
    if kind == "temp":
        c = (v - 32) * 5 / 9 if v > 45 else v
        if c >= 40:
            return "critical", "40 C (104 F) or above"
        if c >= 38:
            return "high", "38 C (100.4 F) or above"
        if c < 35:
            return "low", "below 35 C"
        return "normal", "usual range"
    return "normal", ""


def extract_vitals(text, records) -> list:
    low = text.translate(APOS)
    found, taken = [], []

    def free(a, b):
        return all(b <= s or a >= e for s, e in taken)

    for kind, rx in VITAL_PATTERNS:
        for m in rx.finditer(low):
            a, b = m.start(), m.end()
            if not free(a, b):
                continue
            if kind == "bp":
                sys_, dia = int(m.group(1)), int(m.group(2))
                if not (60 <= sys_ <= 260 and 30 <= dia <= 160 and sys_ > dia):
                    continue
                value, unit, st = f"{sys_}/{dia}", "mmHg", _status("bp", sys_, dia)
            else:
                n = float(m.group(1))
                if kind == "pulse" and not 30 <= n <= 220: continue
                if kind == "spo2" and not 50 <= n <= 100: continue
                if kind == "rr" and not 6 <= n <= 60: continue
                if kind == "glucose" and not 30 <= n <= 600: continue
                if kind == "weight":
                    value, unit, st = f"{n:g}", m.group(2).lower(), ("normal", "")
                else:
                    fasting = bool(re.search(r"fasting|fbs", low[max(0, a - 12):b], re.I))
                    unit = {"pulse": "per min", "spo2": "%", "rr": "per min", "glucose": "mg/dL"}[kind]
                    value, st = f"{n:g}", _status(kind, n, fasting=fasting)
            taken.append((a, b))
            found.append({"kind": kind, "label": VITAL_LABEL[kind], "value": value, "unit": unit, "status": st[0], "note": st[1],
                          "text": low[a:b], "start": a, "end": b})
    for r in records:
        t = r.get("temperature")
        if t and not any(v["kind"] == "temp" for v in found):
            st = _status("temp", t["value"])
            found.append({"kind": "temp", "label": VITAL_LABEL["temp"], "value": f"{t['value']:g}", "unit": "°" + t["unit"], "status": st[0], "note": st[1],
                          "text": t["text"], "start": t["start"], "end": t["end"]})
    found.sort(key=lambda v: v["start"])
    return found


VITAL_FLAG = {
    ("spo2", "critical"): ("emergency", "Low oxygen saturation", "An oxygen saturation below 90% needs urgent medical help."),
    ("spo2", "low"): ("urgent", "Slightly low oxygen saturation", "An oxygen saturation below 95% should be assessed promptly."),
    ("bp", "critical"): ("emergency", "Very high blood pressure", "A reading of 180/120 or above needs urgent assessment."),
    ("bp", "high"): ("attention", "Raised blood pressure", "Blood pressure above 140/90 should be reviewed."),
    ("bp", "low"): ("urgent", "Low blood pressure", "Low blood pressure with symptoms needs prompt assessment."),
    ("pulse", "critical"): ("emergency", "Very abnormal pulse", "A pulse far outside the usual range needs urgent assessment."),
    ("pulse", "high"): ("attention", "Fast pulse", "A resting pulse above 100 should be reviewed."),
    ("rr", "critical"): ("emergency", "Very abnormal breathing rate", "A breathing rate far outside the usual range needs urgent assessment."),
    ("rr", "high"): ("attention", "Fast breathing", "A breathing rate above 20 per minute should be reviewed."),
    ("glucose", "critical"): ("emergency", "Dangerous blood sugar", "A blood sugar this far outside the usual range needs urgent help."),
    ("glucose", "low"): ("urgent", "Low blood sugar", "Low blood sugar can worsen quickly and should be treated promptly."),
    ("glucose", "high"): ("attention", "High blood sugar", "A raised blood sugar should be reviewed."),
}


def vital_flags(vitals) -> list:
    out = []
    for v in vitals:
        rule = VITAL_FLAG.get((v["kind"], v["status"]))
        if rule:
            level, title, advice = rule
            out.append({"id": "V-" + v["kind"], "title": title, "level": level, "advice": advice, "evidence": [v["label"]],
                        "why": f"{v['label']} {v['value']} {v['unit']}".strip()})
    return out


HINDI_UNITS = {"din", "dino", "hafte", "hafta", "haftey", "hafton", "mahine", "mahina", "mahino", "saal", "saalon", "ghante", "ghanta"}
DURATION_PREPS = {"for", "since", "from", "past", "last", "over", "about", "around", "nearly", "almost", "started", "the", "approximately", "roughly", "this", "yesterday", "today"}


def fmt_days(d) -> str:
    if d is None:
        return ""
    if d < 1:
        h = round(d * 24)
        return "today" if h >= 6 or h == 0 else f"{h} hour{'s' if h != 1 else ''}"
    if d < 14:
        v = round(d)
        return f"{v} day{'s' if v != 1 else ''}"
    if d < 60:
        v = round(d / 7)
        return f"{v} week{'s' if v != 1 else ''}"
    if d < 730:
        v = round(d / 30)
        return f"{v} month{'s' if v != 1 else ''}"
    v = round(d / 365)
    return f"{v} year{'s' if v != 1 else ''}"


def trigger_label(t) -> str:
    txt = t["text"].lower()
    if t["effect"] == "worsens" and not txt.startswith(tuple(L.WORSEN_WORDS)):
        txt = "worse " + txt
    elif t["effect"] == "relieves" and not txt.startswith(tuple(L.RELIEVE_WORDS)):
        txt = "better " + txt
    return txt


def describe(rec) -> str:
    parts = []
    if rec["severity"]:
        parts.append(rec["severity"]["label"])
    if rec["quality"]:
        parts.append("/".join(q["label"] for q in rec["quality"]))
    if rec["temperature"]:
        t = rec["temperature"]
        parts.append(f"{t['value']:g}°{t['unit']}")
    if rec["duration"]:
        d = rec["duration"]
        txt = d["text"][:1].lower() + d["text"][1:]
        txt = {"kal se": "since yesterday", "aaj se": "since today", "parso se": "since 2 days"}.get(txt, txt)
        words = txt.split()
        hindi_unit = any(w in HINDI_UNITS for w in words)
        if indic.has_devanagari(txt):   # keep the English note readable: say the length, not the Devanagari words
            parts.append(f"for {fmt_days(d['days'])}" if d["days"] >= 1 else "since today")
        elif hindi_unit:
            parts.append(f"for {fmt_days(d['days'])}" if d["days"] >= 1 else txt)
        elif d["kind"] in ("relative", "weekday") and d["days"] >= 1 and not any(ch.isdigit() for ch in txt):
            parts.append(f"{txt} (~{fmt_days(d['days'])})")
        elif words[0] in DURATION_PREPS or txt.endswith(("ago", "now")):
            parts.append(txt)
        else:
            parts.append(f"for {txt}")
    if rec["onset"]:
        parts.append(f"{rec['onset']['label']} onset")
    if rec["trend"]:
        parts.append(rec["trend"]["label"])
    if rec["frequency"]:
        parts.append(rec["frequency"]["text"].lower())
    if rec["location"] and rec["location"]["text"] not in rec["name"] and L.LOCATION_TO_SYMPTOM.get(rec["location"]["text"]) != rec["name"]:
        parts.append(f"location: {rec['location']['text']}")
    if rec["radiates_to"]:
        parts.append(f"radiating to {rec['radiates_to']['text']}")
    for t in rec["triggers"]:
        parts.append(trigger_label(t))
    return f"{rec['name']} ({'; '.join(parts)})" if parts else rec["name"]


def build_summary(records, ctx) -> str:
    present = [r for r in records if r["status"] == "present" and r["subject"] == "patient"]
    uncertain = [r for r in records if r["status"] == "uncertain" and r["subject"] == "patient"]
    absent = [r for r in records if r["status"] == "absent" and r["subject"] == "patient"]
    resolved = [r for r in records if r["status"] == "resolved" and r["subject"] == "patient"]
    history = [r for r in records if r["status"] == "history" and r["subject"] == "patient"]
    others = [r for r in records if r["subject"] != "patient" and r["status"] in ("present", "uncertain")]
    lines = []
    who = "Patient"
    if ctx["age_label"] or ctx["gender"]:
        bits = []
        if ctx["age_label"]:
            bits.append(ctx["age_label"])
        if ctx["gender"]:
            bits.append(ctx["gender"])
        who = "Patient (" + " ".join(bits) + ")"
    if present:
        present = sorted(present, key=lambda r: (-(r["severity"]["score"] if r["severity"] else 0), -(r["duration"]["days"] if r["duration"] else 0)))
        lines.append(f"{who} reports " + _join([describe(r) for r in present]) + ".")
    elif others or absent or uncertain:
        lines.append("No confirmed current symptom was reported for the patient.")
    else:
        return "No symptoms were detected in the text. Try describing what you feel, for example: \"I have had a fever and headache since yesterday.\""
    if uncertain:
        lines.append("Possible (patient unsure): " + _join([describe(r) for r in uncertain]) + ".")
    if absent:
        lines.append("Denies " + _join([r["name"] for r in absent]) + ".")
    if resolved:
        lines.append("Resolved: " + _join([r["name"] for r in resolved]) + ".")
    if history:
        lines.append("Past history of " + _join([r["name"] for r in history]) + ".")
    for subj in dict.fromkeys(r["subject"] for r in others):
        mine = [describe(r) for r in others if r["subject"] == subj]
        lines.append(f"Reported for {subj if subj == 'someone else' else 'their ' + subj}: " + _join(mine) + ".")
    if ctx["medications"]:
        lines.append("Medicines/remedies mentioned: " + _join(ctx["medications"]) + ".")
    if ctx["conditions"]:
        lines.append("Known conditions mentioned: " + _join(ctx["conditions"]) + ".")
    if ctx["allergies"]:
        lines.append("Allergic to " + _join(ctx["allergies"]) + ".")
    return " ".join(lines)


def vitals_sentence(vitals) -> str:
    if not vitals:
        return ""
    bits = []
    for v in vitals:
        tag = "" if v["status"] == "normal" else f" ({v['status']})"
        bits.append(f"{v['label'].lower() if v['kind'] != 'bp' else 'BP'} {v['value']} {v['unit']}".strip() + tag)
    return " Vitals: " + ", ".join(bits) + "."


def _join(items) -> str:
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def follow_up_questions(records) -> list:
    qs = []
    for r in records:
        if r["status"] not in ("present", "uncertain") or r["subject"] != "patient":
            continue
        if not r["duration"]:
            qs.append(f"How long have you had {r['name']}?")
        if not r["severity"]:
            qs.append(f"How severe is the {r['name']} (mild, moderate or severe)?")
        if len(qs) >= 6:
            break
    return qs[:6]


def build_checklist(text, records, ctx, vitals) -> list:
    """What the doctor still has to ask. An item is done when the patient already said it."""
    present = [r for r in records if r["status"] in ("present", "uncertain") and r["subject"] == "patient"]
    if not present:
        return []
    low = text.lower()
    items = []

    def add(key, label, done):
        items.append({"id": key, "label": label, "done": bool(done)})

    no_dur = [r["name"] for r in present if not r["duration"]]
    add("duration", "How long: " + ", ".join(no_dur[:4]) if no_dur else "How long each symptom has lasted", not no_dur)
    no_sev = [r["name"] for r in present if not r["severity"]]
    add("severity", "How severe: " + ", ".join(no_sev[:4]) if no_sev else "How severe each symptom is", not no_sev)
    if vitals and any(r["name"] == "fever" for r in present) and not any(v["kind"] == "temp" for v in vitals):
        add("temperature", "Measured temperature", False)
    has_age = ctx["age"] is not None or ctx.get("age_months") is not None
    add("age", "Age", has_age)
    add("allergies", "Allergies", ctx["allergies"] or re.search(r"allerg|nkda|\bnka\b", low))
    add("medicines", "Medicines being taken", ctx["medications"] or re.search(r"medicin|tablet|\bpills?\b|syrup|taking|\btook\b|dawai|goli", low))
    add("conditions", "Existing conditions", ctx["conditions"] or re.search(r"no other (illness|problem|condition)|history of|diabet|hypertens|asthma", low))
    if ctx["gender"] == "female" and (ctx["age"] is None or 12 <= ctx["age"] <= 50):
        add("pregnancy", "Pregnancy status", re.search(r"pregnan|\blmp\b|expecting", low))
    if not vitals:
        add("vitals", "Vital signs (BP, pulse, temperature)", False)
    return items


# ------------------------------------------------------------------ public API
STATUS_LABEL = {"present": "symptom", "absent": "negated", "uncertain": "uncertain", "history": "history", "resolved": "negated"}


def analyze(text: str, ref_date: Optional[dt.date] = None) -> dict:
    ref = ref_date or dt.date.today()
    text = text.translate(APOS)
    state = {"all": [], "last_group": []}
    toks_all, all_mentions, unlinked_all = [], [], []
    for si, (s, e) in enumerate(split_sentences(text)):
        toks = tokenize(text, s, e, si)
        if not toks:
            continue
        toks_all.append(toks)
        ms, unl = process_sentence(text, toks, state, ref)
        all_mentions.extend(ms)
        for c in unl:
            unlinked_all.append({"kind": c.kind, "text": text[toks[c.start].start:toks[c.end - 1].end]})

    last_pain = None
    for m in all_mentions:
        if m.name == "pain" and last_pain is not None and m.status == "present" and m.subject == last_pain.subject:
            m.name, m.method = last_pain.name, "coreference"
        elif m.status == "present" and ("pain" in m.name or "ache" in m.name) and m.name != "pain":
            last_pain = m

    # merge mentions of the same symptom
    records = {}
    for m in all_mentions:
        key = (m.name, m.status, m.subject)
        r = records.get(key)
        if r is None:
            r = records[key] = {
                "name": m.name, "status": m.status, "reason": m.reason, "subject": m.subject,
                "system": L.SYSTEM.get(m.name, "Other"), "confidence": m.conf, "method": m.method,
                "evidence": [], "duration": None, "severity": None, "trend": None, "triggers": [], "location": None,
                "radiates_to": None, "quality": [], "frequency": None, "onset": None, "temperature": None}
        r["confidence"] = max(r["confidence"], m.conf)
        r["evidence"].append({"text": text[m.cstart:m.cend], "start": m.cstart, "end": m.cend})
        a = m.attrs
        for k in ("duration", "trend", "location", "radiates_to", "frequency", "onset", "temperature"):
            if r[k] is None and a[k] is not None:
                r[k] = a[k]
        if a["severity"] and (r["severity"] is None or a["severity"]["score"] > r["severity"]["score"]):
            r["severity"] = a["severity"]
        for t in a["triggers"]:
            if not any(x["text"].lower() == t["text"].lower() for x in r["triggers"]):
                r["triggers"].append(t)
        for q in a["quality"]:
            if not any(x["label"] == q["label"] for x in r["quality"]):
                r["quality"].append(q)
    recs = list(records.values())
    for r in recs:
        r["confidence"] = round(r["confidence"], 2)
    order = {"present": 0, "uncertain": 1, "history": 2, "resolved": 3, "absent": 4}
    recs.sort(key=lambda r: (r["subject"] != "patient", order[r["status"]], r["evidence"][0]["start"]))
    for i, r in enumerate(recs, 1):
        r["id"] = i
        if r["duration"]:
            r["duration"]["approx"] = fmt_days(r["duration"]["days"])
        for t in r["triggers"]:
            t["label"] = trigger_label(t)
        r["summary"] = describe(r)

    ctx = extract_context(text, toks_all, None)
    flags = evaluate_red_flags(recs, text)
    vitals = extract_vitals(text, recs)
    flags += age_flags(recs, ctx) + vital_flags(vitals)
    flags.sort(key=lambda f: -L.LEVEL_RANK[f["level"]])
    level = max((f["level"] for f in flags), key=lambda x: L.LEVEL_RANK[x], default="routine")

    highlights = []
    for r in recs:
        label = STATUS_LABEL[r["status"]] if r["subject"] == "patient" else "other"
        for ev in r["evidence"]:
            highlights.append({"start": ev["start"], "end": ev["end"], "label": label, "text": ev["text"], "symptom": r["name"]})
        for key, lab in (("duration", "duration"), ("severity", "severity"), ("trend", "trend"), ("location", "location"),
                         ("radiates_to", "location"), ("frequency", "frequency"), ("onset", "onset"), ("temperature", "severity")):
            v = r[key]
            if v and r["status"] in ("present", "uncertain", "history") and not (key == "severity" and v.get("source") == "temperature"):
                highlights.append({"start": v["start"], "end": v["end"], "label": lab, "text": v["text"], "symptom": r["name"]})
        for t in r["triggers"]:
            highlights.append({"start": t["start"], "end": t["end"], "label": "trigger", "text": t["text"], "symptom": r["name"]})
        for q in r["quality"]:
            highlights.append({"start": q["start"], "end": q["end"], "label": "quality", "text": q["text"], "symptom": r["name"]})
    highlights.extend(ctx["spans"])
    for v in vitals:
        if v["kind"] != "temp":
            highlights.append({"start": v["start"], "end": v["end"], "label": "vital", "text": v["text"], "symptom": ""})
    seen, uniq = set(), []
    for h in highlights:
        k = (h["start"], h["end"], h["label"])
        if k not in seen:
            seen.add(k)
            uniq.append(h)
    uniq.sort(key=lambda h: (h["start"], -(h["end"] - h["start"])))

    tokens = [{"text": t.text, "norm": t.norm, "start": t.start, "end": t.end, "sent": t.sent, "clause": t.clause}
              for toks in toks_all for t in toks][:600]
    return {
        "text": text,
        "language": indic.detect_language(text),
        "reference_date": ref.isoformat(),
        "patient": {"age": ctx["age"], "age_months": ctx["age_months"], "age_label": ctx["age_label"], "gender": ctx["gender"], "medications": ctx["medications"],
                    "conditions": ctx["conditions"], "allergies": ctx["allergies"]},
        "symptoms": recs,
        "red_flags": flags,
        "attention_level": level,
        "vitals": vitals,
        "summary": build_summary(recs, ctx) + vitals_sentence(vitals),
        "follow_up_questions": follow_up_questions(recs),
        "checklist": build_checklist(text, recs, ctx, vitals),
        "unlinked_details": unlinked_all,
        "highlights": uniq,
        "tokens": tokens,
        "stats": {"tokens": len(tokens), "sentences": len(toks_all),
                  "symptoms_present": sum(1 for r in recs if r["status"] == "present" and r["subject"] == "patient"),
                  "symptoms_negated": sum(1 for r in recs if r["status"] in ("absent", "resolved"))},
    }
