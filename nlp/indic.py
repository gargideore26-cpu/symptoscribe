"""Hindi and Marathi (Devanagari) support.

Instead of a second engine, Devanagari words are mapped one-to-one onto the tokens the
English / Hinglish lexicon already understands (``बुखार`` -> ``bukhar``, ``नहीं`` -> ``nahi``).
The mapping happens in ``norm_token`` only, so the original text, the character offsets and the
highlights stay exactly as the patient typed them.

Add words here to widen coverage; no algorithm changes are needed.
"""
import re

# ------------------------------------------------------------------ script helpers
DEVANAGARI_DIGITS = {ord(d): str(i) for i, d in enumerate("०१२३४५६७८९")}
_DEV_RE = re.compile(r"[ऀ-ॿ]")
_STRIP = {0x093C: None, 0x200C: None, 0x200D: None}   # nukta, ZWNJ, ZWJ
_CANDRABINDU = {0x0901: 0x0902}                        # chandrabindu -> anusvara


def has_devanagari(s: str) -> bool:
    return bool(_DEV_RE.search(s))


def deva_key(s: str) -> str:
    """Spelling-insensitive key: drops nukta / joiners and unifies chandrabindu with anusvara."""
    return s.translate({**_STRIP, **_CANDRABINDU})


def _build(raw: dict) -> dict:
    out = {}
    for words, target in raw.items():
        for w in words.split():
            out[deva_key(w)] = target
    return out


# ------------------------------------------------------------------ word map
# "word word word": target   (every word on the left maps to the same target token)
_HINDI = {
    # symptoms (single-token forms the lexicon already has)
    "बुखार ज्वर": "bukhar",
    "सिरदर्द सरदर्द": "headache",
    "खांसी खासी": "khansi",
    "सर्दी": "sardi",
    "ज़ुकाम जुकाम": "zukam",
    "उल्टी उलटी उल्टियां उल्टियाँ": "ulti",
    "मतली": "nausea",
    "दस्त": "dast",
    "कब्ज कब्ज़": "constipation",
    "एसिडिटी अम्लता": "acidity",
    "कमजोरी": "kamzori",
    "थकान थकावट": "thakaan",
    "चक्कर चकराना चकराता चकराती": "chakkar",
    "पसीना": "paseena",
    "खुजली": "khujli",
    "सूजन": "sujan",
    "चकत्ते दाने": "rash",
    "घबराहट": "anxiety",
    "उदासी": "sadness",
    "बेहोशी": "fainting",
    "दौरा दौरे": "seizure",
    "ब्लीडिंग": "bleeding",
    "धड़कन": "dhadkan",
    # words that build the Hinglish phrases ("pet me dard", "seene me dard", ...)
    "दर्द": "dard",
    "पीड़ा": "dard",
    "सिर सर": "sar",
    "पेट": "pet",
    "सीने": "seene",
    "छाती": "chhati",
    "गले": "gale",
    "कमर": "kamar",
    "पीठ": "kamar",
    "बदन शरीर": "badan",
    "कान": "kaan",
    "दांत": "dant",
    "आंख आंखों": "aankh",
    "जोड़ों जोड़": "jodon",
    "दिल": "dil",
    "की": "ki",
    "में मे": "me",
    "सांस": "saans",
    "फूलना फूलती फूल": "phulna",
    "लेने": "lene",
    "तकलीफ": "takleef",
    "भूख": "bhookh",
    "नींद": "neend",
    "ठंड": "thand",
    "लगना लगती लग": "lagna",
    "खराश": "kharash",
    "पेशाब": "peshab",
    "जलन": "jalan",
    "वजन": "wajan",
    "कम": "kam",
    "नाक": "naak",
    "बहना": "behna",
    # negation and glue
    "नहीं नही नहि": "nahi",
    "है हैं": "hai",
    "और": "aur",
    "भी": "bhi",
    "मुझे": "mujhe",
    "मैं": "main",
    "मेरा": "mera",
    "मेरी मेरे": "meri",
    "लेकिन": "lekin",
    "मगर": "magar",
    "शायद": "shayad",
    # time
    "दिन": "din",
    "दिनों": "dino",
    "से": "se",
    "हफ्ते हफ्ता": "hafte",
    "हफ्तों": "hafton",
    "महीने महीना": "mahine",
    "महीनों": "mahino",
    "साल": "saal",
    "सालों": "saalon",
    "घंटे घंटा": "ghante",
    "आज": "aaj",
    "कल": "kal",
    "परसों": "parso",
    # numbers
    "एक": "ek", "दो": "do", "तीन": "teen", "चार": "char", "पांच": "paanch",
    "छह छः छे": "chhe", "सात": "saat", "आठ": "aath", "नौ": "nau", "दस": "das",
    # severity / course
    "बहुत": "bahut",
    "ज्यादा": "zyada",
    "तेज": "tez",
    "हल्का": "halka", "हल्की": "halki",
    "थोड़ा": "thoda", "थोड़ी": "thodi",
    "बढ़": "badh",
    "रहा": "raha", "रही": "rahi", "रहे": "raha",
    "हो": "ho",
    "बार": "baar",
    "चकरा": "chakkar",
    "बेटे बेटा": "son", "बेटी": "daughter", "मां माँ": "mother", "पिता पापा": "father",
    "पत्नी": "wife", "पति": "husband", "भाई": "brother", "बहन": "sister", "बच्चे बच्चा बच्ची": "child",
    "को": "ko",
}

_MARATHI = {
    # symptoms
    "ताप": "fever",
    "डोकेदुखी": "headache",
    "खोकला": "cough",
    "पोटदुखी": "stomachache",
    "पाठदुखी कंबरदुखी": "backache",
    "सांधेदुखी": "arthralgia",
    "अंगदुखी": "myalgia",
    "कानदुखी": "earache",
    "दातदुखी": "toothache",
    "उलट्या": "vomiting",
    "मळमळ": "nausea",
    "जुलाब": "diarrhea",
    "बद्धकोष्ठता": "constipation",
    "आम्लपित्त अॅसिडिटी": "acidity",
    "थकवा": "fatigue",
    "अशक्तपणा": "weakness",
    "घाम": "sweating",
    "खाज": "itching",
    "सूज": "swelling",
    "पुरळ": "rash",
    "धाप": "breathlessness",
    "धडधड": "palpitations",
    "रक्तस्त्राव": "bleeding",
    "बेशुद्ध": "unconscious",
    "झटके फिट": "seizure",
    "चिंता": "anxiety",
    "उदास": "depressed",
    # body parts and verbs for "<part> hurts"
    "डोके": "head",
    "पोटात पोट": "stomach",
    "छातीत छाती": "chest",
    "घसा घशात": "throat",
    "पाठ": "back",
    "डोळे": "eyes",
    "दुखत दुखते दुखतात": "hurts",
    "दुखणे": "pain",
    "जळजळ": "burning",
    "वजन": "wajan",
    "कमी": "kami",
    "श्वास": "shwas",
    "घेण्यास": "ghenyas",
    "त्रास": "tras",
    "भूक": "bhookh",
    "झोप": "jhop",
    "येत": "yet",
    "लघवीला": "laghvila",
    # negation and glue
    "नाही नाहीये नाहीत": "nahi",
    "आहे आहेत": "hai",
    "आणि": "aur",
    "पण": "lekin",
    "मला": "mujhe",
    "माझे माझ्या माझी": "mera",
    # time
    "दिवस दिवसांपासून दिवसापासून दिवसांत": "din",
    "आठवडा आठवड्यापासून आठवड्यांपासून": "hafta",
    "महिना महिन्यापासून महिन्यांपासून": "mahina",
    "तास तासांपासून": "ghante",
    "वर्ष वर्षांपासून": "saal",
    "कालपासून काल": "yesterday",
    "पासून": "se",
    "आजपासून": "today",
    "आज": "today",
    # numbers
    "दोन": "do", "पाच": "paanch", "सहा": "chhe", "नऊ": "nau", "दहा": "das",
    # severity / course
    "खूप": "bahut",
    "जास्त": "zyada",
    "तीव्र": "intense",
    "असह्य": "unbearable",
    "सौम्य": "mild",
    "थोडा थोडे": "thoda",
    "थोडी": "thodi",
    "वाढत वाढले वाढतो वाढते": "increasing",
    "एका": "ek",
    "मुलाला मुलगा मुलाचा": "son", "मुलीला मुलगी": "daughter", "आई": "mother", "बाबा": "father",
}

# Marathi first, so a word shared by both languages ("एक", "तीन", "सात" ...) keeps the Hindi token,
# which is the same either way.
NORMALISE = {**_build(_MARATHI), **_build(_HINDI)}

# ------------------------------------------------------------------ language guess
_MARATHI_MARKERS = {deva_key(w) for w in "आहे आहेत नाही नाहीये मला माझे माझ्या पासून आणि होत येत दुखत खूप".split()}
_HINDI_MARKERS = {deva_key(w) for w in "है हैं नहीं मुझे मैं से रहा रही और भी बहुत में".split()}
_HINGLISH_MARKERS = set("""hai hain nahi nahin nhi mujhe main mera meri mere aur bhi bukhar khansi din dino se thoda thodi bahut zyada dard sar pet kal aaj parso
ho raha rahi rahe hota hoti kuch sath saath par lekin magar ulti dast kamzori thakan thakaan chakkar sardi zukam paseena khujli sujan kaan kamar badan
seene gale me mein ka ki ke ko ye yeh woh bete beta beti maa pita bhai behen patni pati""".split())
_WORD_RE = re.compile(r"[\u0900-\u097F]+|[A-Za-z']+")


def detect_language(text: str) -> dict:
    """Small script / marker-word guess shown to the user as a label (not used by the engine).

    Text that mixes scripts or languages in one sentence is reported as "Mixed", with the parts listed."""
    words = [deva_key(w) if has_devanagari(w) else w.lower() for w in _WORD_RE.findall(text)]
    dev = [w for w in words if has_devanagari(w)]
    latin = [w for w in words if not has_devanagari(w)]
    hinglish = [w for w in latin if w in _HINGLISH_MARKERS]
    english = [w for w in latin if len(w) >= 3 and w not in _HINGLISH_MARKERS]
    if dev:
        mr = sum(1 for w in dev if w in _MARATHI_MARKERS or w.endswith(deva_key("पासून")))
        hi = sum(1 for w in dev if w in _HINDI_MARKERS)
        base, code = ("Marathi", "mr") if mr > hi else ("Hindi", "hi")
        parts = [base]
        if english:
            parts.append("English")
        elif len(hinglish) >= 2:
            parts.append("Hinglish")
        if len(parts) > 1:
            return {"code": "mixed", "name": "Mixed", "script": "Devanagari + Latin", "parts": parts,
                    "label": "Mixed · " + " + ".join(parts)}
        return {"code": code, "name": base, "script": "Devanagari", "parts": parts, "label": f"{base} · देवनागरी"}
    if len(hinglish) >= 2:
        return {"code": "hi-Latn", "name": "Hinglish", "script": "Latin", "parts": ["Hinglish"], "label": "Hinglish"}
    return {"code": "en", "name": "English", "script": "Latin", "parts": ["English"], "label": "English"}
