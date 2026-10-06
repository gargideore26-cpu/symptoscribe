"""Unit tests for the NLP engine and the web API.

Run from the project folder:   python -m unittest discover -s tests -v
"""
import datetime as dt
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nlp import analyze  # noqa: E402

REF = dt.date(2026, 10, 5)  # a Monday


def run(text):
    return analyze(text, REF)


def get(result, name, status="present", subject="patient"):
    for s in result["symptoms"]:
        if s["name"] == name and s["status"] == status and s["subject"] == subject:
            return s
    return None


class SymptomFinding(unittest.TestCase):
    def test_basic_lexicon(self):
        r = run("I have a fever and a cough.")
        self.assertIsNotNone(get(r, "fever"))
        self.assertIsNotNone(get(r, "cough"))

    def test_multiword_phrase_wins_over_single_word(self):
        r = run("I have a sore throat.")
        self.assertIsNotNone(get(r, "sore throat"))
        self.assertIsNone(get(r, "cold"))

    def test_plural_and_spelling(self):
        r = run("Headace and fevar since sunday")
        self.assertIsNotNone(get(r, "headache"))
        self.assertIsNotNone(get(r, "fever"))

    def test_fuzzy_does_not_change_first_letter(self):
        r = run("I have some redness near the wound")
        self.assertIsNone(get(r, "fatigue"))

    def test_hinglish(self):
        r = run("Mujhe bukhar hai aur sar dard hai")
        self.assertIsNotNone(get(r, "fever"))
        self.assertIsNotNone(get(r, "headache"))

    def test_generic_pain_pattern(self):
        r = run("I have pain in my chest")
        self.assertIsNotNone(get(r, "chest pain"))
        r = run("There is a sharp pain in my left arm")
        self.assertIsNotNone(get(r, "left arm pain"))

    def test_cold_water_is_not_a_cold(self):
        r = run("I drink cold water every day")
        self.assertEqual(r["symptoms"], [])

    def test_no_symptoms(self):
        r = run("Hello doctor, I have an appointment at 5 pm.")
        self.assertEqual(r["symptoms"], [])
        self.assertIn("No symptoms", r["summary"])

    def test_tired_of_is_not_fatigue(self):
        self.assertIsNone(get(run("I am tired of waiting"), "fatigue"))


class Negation(unittest.TestCase):
    def test_simple_no(self):
        r = run("No fever. I have a cough.")
        self.assertIsNotNone(get(r, "fever", "absent"))
        self.assertIsNotNone(get(r, "cough"))

    def test_list_scope(self):
        r = run("No fever, cough or cold.")
        for name in ("fever", "cough", "cold"):
            self.assertIsNotNone(get(r, name, "absent"), name)

    def test_but_ends_scope(self):
        r = run("I don't have fever but I have a severe headache")
        self.assertIsNotNone(get(r, "fever", "absent"))
        self.assertIsNotNone(get(r, "headache"))

    def test_distant_not_does_not_leak(self):
        r = run("I did not eat anything and now my stomach hurts a lot")
        self.assertIsNotNone(get(r, "stomach pain"))

    def test_not_feeling_well_and_fever(self):
        r = run("I am not feeling well and have fever")
        self.assertIsNotNone(get(r, "fever"))

    def test_hindi_post_negation(self):
        r = run("khansi nahi hai")
        self.assertIsNotNone(get(r, "cough", "absent"))

    def test_pseudo_negation(self):
        r = run("My stomach pain is not getting better, no relief after medicine")
        self.assertIsNotNone(get(r, "stomach pain"))

    def test_resolved(self):
        r = run("The fever is gone")
        self.assertIsNotNone(get(r, "fever", "resolved"))

    def test_uncertain(self):
        r = run("Maybe I have a mild fever, not sure.")
        self.assertIsNotNone(get(r, "fever", "uncertain"))


class Subject(unittest.TestCase):
    def test_family_member(self):
        r = run("My mother has a fever and I have a headache.")
        self.assertIsNotNone(get(r, "fever", subject="mother"))
        self.assertIsNotNone(get(r, "headache"))

    def test_family_with_adjectives(self):
        r = run("My 6 year old son has fever")
        self.assertIsNotNone(get(r, "fever", subject="son"))

    def test_she_means_someone_else(self):
        r = run("She has cough since 2 days")
        self.assertIsNotNone(get(r, "cough", subject="someone else"))

    def test_history(self):
        r = run("I used to have migraines in college.")
        self.assertIsNotNone(get(r, "headache", "history"))

    def test_conditions_of_relatives_are_not_the_patients(self):
        r = run("My mother has diabetes and fever.")
        self.assertNotIn("diabetes", r["patient"]["conditions"])


class Duration(unittest.TestCase):
    def days(self, text, name):
        s = get(run(text), name)
        self.assertIsNotNone(s, text)
        return s["duration"]["days"] if s["duration"] else None

    def test_numbers(self):
        self.assertEqual(self.days("fever for 3 days", "fever"), 3)
        self.assertEqual(self.days("fever for the past 2 weeks", "fever"), 14)

    def test_words_and_fuzzy_quantities(self):
        self.assertEqual(self.days("cough for two weeks", "cough"), 14)
        self.assertEqual(self.days("cough for a couple of weeks", "cough"), 14)
        self.assertEqual(self.days("cough for a week", "cough"), 7)

    def test_range_uses_upper_bound(self):
        self.assertEqual(self.days("fever for 2-3 days", "fever"), 3)

    def test_relative(self):
        self.assertEqual(self.days("fever since yesterday", "fever"), 1)
        self.assertEqual(self.days("headache since last night", "headache"), 1)
        self.assertEqual(self.days("cough since morning", "cough"), 0.5)

    def test_weekday(self):
        self.assertEqual(self.days("fever since Sunday", "fever"), 1)
        self.assertEqual(self.days("fever since last Friday", "fever"), 3)

    def test_hinglish(self):
        self.assertEqual(self.days("bukhar 2 din se", "fever"), 2)
        self.assertEqual(self.days("khansi teen din se", "cough"), 3)

    def test_age_is_not_a_duration(self):
        r = run("I am a 45 year old male with chest pain")
        self.assertIsNone(get(r, "chest pain")["duration"])
        self.assertEqual(r["patient"]["age"], 45)
        self.assertEqual(r["patient"]["gender"], "male")

    def test_frequency_is_not_a_duration(self):
        s = get(run("vomiting 3 times a day"), "vomiting")
        self.assertIsNone(s["duration"])
        self.assertIsNotNone(s["frequency"])


class Linking(unittest.TestCase):
    def test_trailing_duration_covers_list(self):
        r = run("fever, cough and cold for 4 days")
        for name in ("fever", "cough", "cold"):
            self.assertEqual(get(r, name)["duration"]["days"], 4, name)

    def test_two_durations_stay_separate(self):
        r = run("fever for 3 days and headache since yesterday")
        self.assertEqual(get(r, "fever")["duration"]["days"], 3)
        self.assertEqual(get(r, "headache")["duration"]["days"], 1)

    def test_negated_symptom_gets_no_details(self):
        r = run("no fever, cough since 2 days")
        self.assertIsNone(get(r, "fever", "absent")["duration"])
        self.assertEqual(get(r, "cough")["duration"]["days"], 2)

    def test_severity_attaches_to_nearest(self):
        r = run("severe headache and mild fever")
        self.assertEqual(get(r, "headache")["severity"]["label"], "severe")
        self.assertEqual(get(r, "fever")["severity"]["label"], "mild")

    def test_predicate_severity(self):
        r = run("my headache is severe and my fever is mild")
        self.assertEqual(get(r, "headache")["severity"]["label"], "severe")
        self.assertEqual(get(r, "fever")["severity"]["label"], "mild")

    def test_carry_over_with_pronoun(self):
        r = run("I have a cough. It started 3 days ago.")
        self.assertEqual(get(r, "cough")["duration"]["days"], 3)

    def test_new_sentence_about_the_patient_does_not_carry_over(self):
        r = run("I can't sleep. I want to die sometimes.")
        self.assertIsNone(get(r, "insomnia")["trend"])

    def test_pain_scale(self):
        s = get(run("headache 9/10"), "headache")
        self.assertEqual(s["severity"]["label"], "severe")
        s = get(run("headache 5 out of 10"), "headache")
        self.assertEqual(s["severity"]["label"], "moderate")

    def test_temperature(self):
        s = get(run("I have fever of 103 F"), "fever")
        self.assertEqual(s["severity"]["label"], "severe")
        self.assertEqual(s["temperature"]["unit"], "F")
        s = get(run("temperature is 38.5 C"), "fever")
        self.assertEqual(s["severity"]["label"], "moderate")

    def test_triggers_and_effect(self):
        s = get(run("stomach pain gets worse after eating"), "stomach pain")
        self.assertEqual(s["triggers"][0]["effect"], "worsens")
        self.assertEqual(s["triggers"][0]["object"], "eating")

    def test_negated_trend(self):
        s = get(run("My cough is not improving"), "cough")
        self.assertEqual(s["trend"]["label"], "not improving")

    def test_location_binds_to_preceding_symptom(self):
        r = run("I have a rash on my arms that is itchy")
        self.assertEqual(get(r, "rash")["location"]["text"], "arms")

    def test_bare_pain_resolves_to_earlier_pain(self):
        r = run("My knee hurts when I walk. Pain is dull and constant.")
        self.assertEqual(get(r, "joint pain")["trend"]["label"], "constant")
        self.assertIsNone(get(r, "pain"))


class SafetyAndOutput(unittest.TestCase):
    def test_chest_pain_flag(self):
        r = run("I have chest pain")
        self.assertEqual(r["attention_level"], "emergency")

    def test_fever_three_days_flag(self):
        r = run("fever for 4 days")
        self.assertIn("RF5", [f["id"] for f in r["red_flags"]])
        r = run("fever for 1 day")
        self.assertNotIn("RF5", [f["id"] for f in r["red_flags"]])

    def test_negated_chest_pain_is_not_flagged(self):
        r = run("no chest pain, just a mild cough")
        self.assertEqual(r["red_flags"], [])
        self.assertEqual(r["attention_level"], "routine")

    def test_self_harm_language(self):
        r = run("I feel hopeless and want to die")
        self.assertEqual(r["attention_level"], "emergency")

    def test_follow_up_questions(self):
        r = run("I have a headache")
        self.assertTrue(any("How long" in q for q in r["follow_up_questions"]))

    def test_summary_mentions_denied_symptoms(self):
        r = run("I have a fever but no cough")
        self.assertIn("Denies cough", r["summary"])

    def test_highlight_offsets_match_text(self):
        text = "Fever 101 F since Sunday, no cough"
        r = run(text)
        for h in r["highlights"]:
            self.assertEqual(text[h["start"]:h["end"]], h["text"])

    def test_empty_and_odd_input_do_not_crash(self):
        for t in ["", "   ", "!!!", "\n\n", "a" * 4000, "fever " * 300, "बुखार है", "😷 fever 🤒 since yesterday"]:
            r = run(t)
            self.assertIn("summary", r)

    def test_emoji_offsets(self):
        text = "😷 fever since yesterday"
        r = run(text)
        for h in r["highlights"]:
            self.assertEqual(text[h["start"]:h["end"]], h["text"])

    def test_json_serialisable(self):
        import json
        json.dumps(run("My stomach has been burning since Sunday and gets worse after eating."))


class DevanagariSupport(unittest.TestCase):
    def names(self, text):
        return {(s["name"], s["status"]): s for s in analyze(text)["symptoms"]}

    def test_hindi_symptoms_negation_duration(self):
        r = self.names("मुझे 2 दिन से बुखार है और सिरदर्द भी है, खांसी नहीं है।")
        self.assertIn(("fever", "present"), r)
        self.assertEqual(r[("fever", "present")]["duration"]["days"], 2)
        self.assertIn(("cough", "absent"), r)

    def test_marathi_with_devanagari_digits(self):
        r = self.names("मला २ दिवसांपासून ताप आहे आणि डोकेदुखी आहे, खोकला नाही.")
        self.assertEqual(r[("fever", "present")]["duration"]["days"], 2)
        self.assertIn(("headache", "present"), r)
        self.assertIn(("cough", "absent"), r)

    def test_highlights_use_original_offsets(self):
        text = "मुझे बुखार है, खांसी नहीं है।"
        a = analyze(text)
        cps = list(a["text"])
        for h in a["highlights"]:
            self.assertEqual("".join(cps[h["start"]:h["end"]]), h["text"])

    def test_other_person_in_hindi(self):
        r = analyze("मेरे बेटे को बुखार है।")["symptoms"]
        self.assertNotEqual(r[0]["subject"], "patient")

    def test_language_detection(self):
        self.assertEqual(analyze("I have a fever")["language"]["code"], "en")
        self.assertEqual(analyze("मुझे बुखार है")["language"]["code"], "hi")
        self.assertEqual(analyze("मला ताप आहे")["language"]["code"], "mr")
        self.assertEqual(analyze("mujhe bukhar hai aur sar dard hai")["language"]["code"], "hi-Latn")


class CompareVisits(unittest.TestCase):
    def test_new_resolved_and_changed(self):
        from compare import compare_visits
        d = compare_visits("I have fever and cough for 3 days, severe headache. No sore throat.",
                           "Fever is gone. Cough is still there but mild and getting better. New sore throat since yesterday. Headache is worse.")
        self.assertEqual([n["name"] for n in d["new"]], ["sore throat"])
        self.assertEqual([r["name"] for r in d["resolved"]], ["fever"])
        dirs = {c["name"]: c["direction"] for c in d["continuing"]}
        self.assertEqual(dirs, {"headache": "worse", "cough": "better"})

    def test_not_mentioned_now(self):
        from compare import compare_visits
        d = compare_visits("I have fever and cough.", "I have a cough.")
        self.assertEqual([g["name"] for g in d["not_mentioned"]], ["fever"])


class WebApi(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.client = create_app().test_client()

    def test_home_page(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"SymptoScribe", r.data)

    def test_analyze(self):
        r = self.client.post("/api/analyze", json={"text": "I have fever since yesterday, no cough."})
        self.assertEqual(r.status_code, 200)
        names = {s["name"]: s["status"] for s in r.get_json()["symptoms"]}
        self.assertEqual(names, {"fever": "present", "cough": "absent"})

    def test_validation(self):
        self.assertEqual(self.client.post("/api/analyze", json={"text": "   "}).status_code, 400)
        self.assertEqual(self.client.post("/api/analyze", json={"nope": 1}).status_code, 400)
        self.assertEqual(self.client.post("/api/analyze", data="not json").status_code, 400)
        self.assertEqual(self.client.post("/api/analyze", json={"text": "x" * 5001}).status_code, 413)

    def test_examples_all_analyse(self):
        for ex in self.client.get("/api/examples").get_json():
            r = self.client.post("/api/analyze", json={"text": ex["text"]})
            self.assertEqual(r.status_code, 200)
            self.assertTrue(r.get_json()["symptoms"], ex["label"])

    def test_compare_endpoint(self):
        r = self.client.post("/api/compare", json={"before": "I have fever.", "after": "I have a cough."})
        self.assertEqual(r.status_code, 200)
        self.assertIn("summary", r.get_json())
        self.assertEqual(self.client.post("/api/compare", json={"before": "x", "after": " "}).status_code, 400)

    def test_report_pdf_with_details(self):
        r = self.client.post("/api/report", json={"text": "मुझे बुखार है", "details": {"name": "Asha", "age": "34", "date": "2026-10-06", "doctor": "Dr Rao"}})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "application/pdf")
        self.assertTrue(r.data.startswith(b"%PDF"))

    def test_pipeline_endpoint(self):
        r = self.client.post("/api/pipeline", json={"text": "Headace and fevar since sunday, no cough."})
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual([c["norm"] for c in d["changes"]], ["fever"])
        self.assertEqual({s["name"]: s["status"] for s in d["symptoms"]}, {"headache": "present", "fever": "present", "cough": "absent"})
        self.assertTrue(d["details"])
        self.assertEqual(self.client.post("/api/pipeline", json={"text": " "}).status_code, 400)

    def test_dataset_endpoints(self):
        r = self.client.get("/api/dataset")
        self.assertEqual(r.status_code, 200)
        d = r.get_json()
        self.assertEqual(d["texts"], 1200)
        self.assertGreater(d["coverage"], 0.8)
        c = self.client.get("/api/dataset/random").get_json()
        self.assertTrue(c["text"])

    def test_evaluation_endpoint(self):
        r = self.client.get("/api/evaluation")
        self.assertEqual(r.status_code, 200)
        data = r.get_json()
        self.assertGreater(data["overall"]["assertion"]["f1"], 0.8)

    def test_static_files(self):
        for path in ("/static/app.js", "/static/style.css"):
            self.assertEqual(self.client.get(path).status_code, 200)


if __name__ == "__main__":
    unittest.main()
