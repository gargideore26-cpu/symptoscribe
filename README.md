# SymptoScribe

**Turning a patient's own words into a structured note for the doctor.**

A patient writes (or pastes) something like

> *My stomach has been burning since Sunday and gets worse after eating. I also have a mild headache but no fever.*

and SymptoScribe returns

| Symptom | Since | Severity | Details |
|---|---|---|---|
| Stomach pain | since Sunday (~1 day) | – | burning, worse after eating |
| Headache | – | mild | – |
| ~~Fever~~ | denied | | |

plus a one-paragraph note, red flags, and follow-up questions. A website shows the patient's text with colour-coded markup, so every extracted fact can be checked against the sentence it came from.

---

## 1. Run it

```bash
cd symptoscribe
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                      # open http://127.0.0.1:5000
```

Set `PORT=5001` if port 5000 is busy (macOS AirPlay uses it).

```bash
python -m unittest discover -s tests -v      # 77 tests
python evaluation/evaluate.py --failures     # accuracy on the annotated texts
```

Flask serves the site and fpdf2 builds the PDF report. The NLP engine itself uses only the Python standard library.

## 2. Project structure

```
symptoscribe/
├── app.py                  Flask server and JSON API
├── nlp/
│   ├── lexicon.py          all knowledge: symptoms, negation words, severity, units, red flags...
│   └── extractor.py        the NLP pipeline (about 1,300 lines, one function per stage)
├── templates/index.html    the website
├── static/style.css, app.js
├── tests/test_extractor.py 60 unit and API tests
└── evaluation/
    ├── gold.json           91 hand-annotated texts (183 symptom annotations)
    └── evaluate.py         precision / recall / F1 and error list
```

Extras: **age-aware red flags** (fever in a baby or an older adult, dehydration risk at the extremes of age, bleeding and other warning signs in pregnancy, each flag showing why it fired) and **vital signs** (BP, pulse, SpO2, breathing rate, blood sugar, weight, temperature) that are extracted, marked normal, low, high or critical, and can raise flags. **Live** page for consultations: the microphone stays on (Web Speech API, English, Hindi or Marathi), each finished sentence is analysed, and the note, symptom cards and red flags update as the patient talks; a typed fallback and a scripted demo are included. Sentences may **mix languages** (for example `mujhe fever hai aur पेट में दर्द`); the result shows a Mixed label with its parts. **Pipeline** page (`/api/pipeline`) steps through the eight stages on any text, with tokens, normalisation, symptoms, clauses, negation, details, links and the note. **Compare** page (`/api/compare`) diffs two visits (new, resolved, worse/better); the PDF report can carry typed-in patient name, age, date and doctor, which are never stored.

API: `POST /api/analyze` with `{"text": "..."}`, `GET /api/examples`, `GET /api/evaluation`, `GET /api/health`.

## 3. The NLP pipeline

| # | Stage | NLP concept | Example |
|---|---|---|---|
| 1 | Sentence splitting and tokenising with character offsets | tokenisation | offsets let the UI highlight the original text |
| 2 | Spelling normalisation | text normalisation | `fevar` → `fever`, `dont` → `don't` |
| 3 | Symptom recognition | named entity recognition by lexicon, longest match, plural rules, fuzzy matching (`difflib`), body-part patterns | `sore throat` beats `throat`; `pain in my chest` → chest pain |
| 4 | Clause segmentation | shallow syntax | list commas (`fever, cough and cold`) vs clause commas |
| 5 | Assertion status | negation scope (NegEx-style), hedging, history, subject detection | `no fever, cough or cold`; `maybe`; `my mother has fever` |
| 6 | Detail extraction | temporal expression parsing, numeric and lexical attribute extraction | `a couple of weeks`, `since Sunday`, `7/10`, `101 F` |
| 7 | Linking details to symptoms | attachment heuristics, discourse carry-over | `It started 3 days ago` attaches to the last symptom |
| 8 | Safety layer and summary | rule-based flags, template natural-language generation | red flags, follow-up questions, doctor's note |

What is extracted for each symptom: status (present / denied / unsure / resolved / past / someone else's), duration, onset, frequency, severity (words, pain scale, temperature), course, triggers (and whether they worsen or relieve), body location, radiation, quality, temperature. Also patient age, gender, medicines mentioned, known conditions and allergies.

Languages: English, romanised Hindi (Hinglish), and **Hindi and Marathi in Devanagari script**. Devanagari words are mapped one-to-one onto the tokens the lexicon already knows (`nlp/indic.py`), so highlights and offsets stay on the patient's original text. To add a Hindi or Marathi word, add it to the word map in `nlp/indic.py`. Known limit: PDF fonts cover Latin text only, so for Devanagari input the report lists the recognised symptoms in English instead of reprinting the original text.

### Why rules and not a neural model?

For clinical text, every decision should be explainable and fixable. Rules need no training data, are deterministic, and the interface shows a reason for each decision. They are also a strong **baseline** to compare a learned model against (see Section 7).

## 4. Dataset and evaluation

**Public dataset:** [Symptom2Disease](https://www.kaggle.com/datasets/niyarrbarman/symptom2disease) (Kaggle, niyarrbarman), 1,200 patient-style symptom descriptions in 24 categories. Put `Symptom2Disease.csv` in `data/` (or set `SYMPTO_DATASET` to its path). The website uses it for the example cases ("Case 1-5" and "Random case") and for the coverage report on the Evaluation page (`dataset.py`, `/api/dataset`). The dataset has only category labels, no marked symptoms, so the report shows **coverage** (about 88% of the texts have at least one symptom found), not accuracy. SymptoScribe never uses or predicts the disease labels.

**Accuracy check:** the numbers below come from a small hand-marked set, kept only because the public dataset cannot give accuracy scores.


`evaluation/gold.json` holds 91 texts that were annotated by hand. Three sets, scored separately:

| Set | Texts | Purpose |
|---|---|---|
| dev | 31 | used while building the rules |
| held-out | 42 | written afterwards; used for **one** round of error analysis, so no longer unseen |
| challenge | 18 | long, messy, paragraph-style texts; annotated before it was ever run and **not tuned on** |

Current results (micro-averaged):

| Measure | Precision | Recall | F1 |
|---|---|---|---|
| Symptom found | 99.5% | 98.4% | 98.9% |
| Symptom found + correct status | 98.9% | 97.8% | 98.4% |
| Details (duration, severity, course, location, triggers) | 97.2% | 96.7% | 96.9% |
| **Challenge set only** (found + status) | 95.8% | 92.0% | **93.9%** |

Honest reading of these numbers:

* The held-out set scored **94.9% F1 the first time** it was run. After its errors were studied and the rules fixed it reached 100%, which is why it should not be quoted as a test score.
* The challenge set first scored **92.9%**. After that, two generic bugs were fixed (fuzzy matching changed the first letter, so *redness* became *weakness*; a trailing trend phrase attached to the next symptom), and two annotations were corrected to follow the written location convention. Nothing else was tuned on it. **Use the challenge score, about 93-94%, as your honest estimate.**
* Every text was written and annotated by the same person who built the system, so real patient text will score lower. For your viva, collect 30 or more fresh examples from classmates and family (no real patient data), annotate them **before** running the system, and report that number.
* Annotation conventions are in `gold.json` (for example, duration is stored in days, using the upper bound for ranges; `since yesterday` is 1 day).

### Known failure cases (from `--failures`)

* **Subject changes between sentences.** *My daughter has a fever. No rash.* The second sentence is read as the patient's own.
* **Words missing from the lexicon.** *vision goes blurry*, *lost 5 kg*, *Kal raat se* (last night, Hinglish).
* **Cue words not handled.** *Everytime I eat…* is not recognised as a trigger; *helps a bit* is not read as relief.
* **Ambiguous attachment.** *Sore throat… and I am feeling weak since morning* may or may not apply to both. *Pain in my right side of the abdomen … now it's a bit better* attaches *better* to the wrong symptom.
* **Coordinated lists with one shared duration** are attached to every symptom in the list, which is sometimes wrong (see case D07).

Each of these is a good extension task.

## 5. Ethics and limits

* **Not a diagnostic tool.** It organises what the patient wrote, and names no disease.
* The red flags are coarse rules for attention, not clinical triage. They err on the side of caution.
* A missing symptom does not mean the patient did not mention it. The marked-up text is there so that humans can check.
* **Privacy:** text is processed in memory and not stored. Do not use real patient data, names or phone numbers in demos.
* Self-harm language triggers a message with the Tele-MANAS number (14416 / 1-800-891-4416, India).

## 6. How to extend the lexicon

Open `nlp/lexicon.py`. To add a symptom, add a line to `SYMPTOMS`:

```python
"photophobia": ["photophobia", "light hurts my eyes", "sensitive to light"],
```

and, optionally, a body system in `SYSTEM`. Then add a test sentence to `gold.json` and run `python evaluation/evaluate.py`. Other tables: `SEVERITY`, `TREND`, `TRIGGER_OBJECTS`, `LOCATIONS`, `RED_FLAGS`, `MEDICATIONS`, `UNIT_DAYS`.

## 7. Ideas for the next semester

1. **Learned baseline:** fine-tune a token-classification model (BioBERT, or MuRIL for Indian languages) on the annotated data and compare it with the rules (same `evaluate.py`).
2. Devanagari and Marathi input (AI4Bharat resources).
3. Speech input (Whisper) for patients who cannot type.
4. Coreference for "She", "he" and "both" across sentences.
5. Grow the annotated set and measure inter-annotator agreement with a classmate.

## 8. Viva cheat-sheet

* **Problem:** patients describe symptoms in free text; doctors have minutes. Structuring the text saves time and avoids missed details such as denied symptoms.
* **Why NLP:** the same fact has many surface forms (*burning*, *been burning since Sunday*, *Sunday se*). Negation, scope and attachment decide meaning.
* **Hardest part:** deciding which detail belongs to which symptom and where a negation ends.
* **Baseline vs ML:** the rule system is explainable and needs no data; the ML model would generalise better but needs labelled data. Both are scored with the same F1 metric.
* **Metric choices:** entity-level precision and recall, because a missed symptom is worse than an extra one.
* **Limits:** same-author annotation, a small lexicon, English and Hinglish only.
