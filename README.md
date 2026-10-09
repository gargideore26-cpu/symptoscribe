# SymptoScribe

SymptoScribe turns what a patient writes about their symptoms into a short, organised note for the doctor.

You type something like this:

> My stomach has been burning since Sunday and gets worse after eating. I also have a mild headache but no fever.

and it shows:

| Symptom | Since | Severity | Details |
|---|---|---|---|
| Stomach pain | since Sunday | - | burning, worse after eating |
| Headache | - | mild | - |
| Fever | denied | | |

It also writes a one-paragraph note and lists any red flags. The patient's text is shown with colours, so a doctor can check every fact against the sentence it came from. It never names a disease.

## What is on the website

- **Analyzer**: paste or type the patient's words, press Analyze, and read the review. You can download it as a PDF report.
- **Check in**: the doctor makes a link and sends it to a patient. The patient opens it on their phone, writes their symptoms, and sends them. The note then shows up in the doctor's list.
- **Insights**: simple counts of the notes analysed (common symptoms, how urgent, which language). It stores counts only, never the patient's words.
- **How does it work**: a short explanation of the steps.

It understands English, Hinglish (Hindi in English letters), and Hindi and Marathi in Devanagari script, even when they are mixed in one sentence.

## Run it

```bash
cd symptoscribe
python -m venv .venv
source .venv/bin/activate          # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py                      # then open http://127.0.0.1:5000
```

If port 5000 is busy, run it with `PORT=5002 python app.py`.

To let a phone on the same Wi-Fi open a Check in link, start it with `HOST=0.0.0.0`.

Tests and accuracy check:

```bash
python -m unittest discover -s tests
python evaluation/evaluate.py --failures
```

The example texts come from the public [Symptom2Disease](https://www.kaggle.com/datasets/niyarrbarman/symptom2disease) dataset on Kaggle. Download `Symptom2Disease.csv` and put it in the `data/` folder.

## How it works

The program uses plain rules, not a trained model. It goes through the text in these steps:

1. Split the text into sentences and words, and fix common spelling mistakes (`fevar` becomes `fever`).
2. Find symptoms by matching words and phrases against a list of about 40 symptoms.
3. Decide the status of each one: present, denied (`no fever`), unsure, from the past, or about someone else.
4. Attach the details: since when, how bad, getting better or worse, where it hurts, what triggers it, and vital signs such as blood pressure.
5. Check for red flags with simple rules, including rules for age and pregnancy.
6. Write the note from a template.

Rules were chosen because every decision can be explained and fixed, and they need no training data. They also make a good baseline to compare a learned model against later.

Hindi and Marathi words are mapped to the same vocabulary as English, so the highlights stay on the patient's original text. Words can be added in `nlp/indic.py`.

## Files

```
app.py            the web server
nlp/              the language engine (extractor.py, lexicon.py, indic.py)
intake.py         saves Check in forms
stats.py          counts for the Insights page
report.py         builds the PDF report
dataset.py        loads the example texts
templates/, static/   the website
tests/            unit tests
evaluation/       hand-marked texts and the scoring script
```

## How well does it work

The program was scored on 121 short texts that were marked by hand. It finds about 99% of the symptoms and gets the status (present or denied) right about 99% of the time.

That number is too good to trust fully, because most of those texts were used while the rules were being built. The fairest number comes from 18 longer, messier texts that were written first and not tuned on (two general bugs were fixed after its first run): about 94% for finding a symptom with the right status. All the texts were written and marked by the people who built the program, so real patient text will score lower.

Things it still gets wrong:

- A change of person between sentences (`My daughter has a fever. No rash.`).
- Words that are not in the list yet (`vision goes blurry`).
- Some details that could belong to two symptoms.

## Limits

- It does not diagnose or suggest treatment, and the red flags are simple rules, not medical triage. The doctor decides.
- A symptom that is not found does not mean the patient did not say it. That is why the marked text is shown.
- The Hindi and Marathi word list is small.
- The PDF cannot print Devanagari letters, so for those texts it lists the symptoms it found in English.
- Check in has no login, and the saved forms (`data/intake.json`) are not encrypted. Anyone who can open the site can read them. Use made-up data only.
- If a text mentions self-harm, it shows the Tele-MANAS helpline (14416 or 1-800-891-4416 in India).
