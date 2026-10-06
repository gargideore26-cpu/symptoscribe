"""Knowledge resources for SymptoScribe.

Everything the extractor "knows" lives in this file so it can be edited or
extended without touching the algorithms.  Entries cover common English
phrasings, colloquial variants and a few Hinglish (romanised Hindi) terms.
"""

# ---------------------------------------------------------------- symptoms
# canonical symptom -> surface forms (lower case)
SYMPTOMS = {
    "fever": ["fever", "fevers", "feverish", "high temperature", "temperature", "bukhar", "bukhaar", "running a temperature"],
    "headache": ["headache", "head ache", "head pain", "head is paining", "head hurts", "sar dard", "sir dard", "sar me dard", "migraine"],
    "cough": ["cough", "coughing", "khansi", "khasi"],
    "sore throat": ["sore throat", "throat pain", "throat ache", "throat is paining", "throat hurts", "throat infection", "gale me dard", "scratchy throat", "gale me kharash"],
    "cold": ["cold", "runny nose", "running nose", "blocked nose", "stuffy nose", "nasal congestion", "sneezing", "sardi", "zukam", "zukham", "naak behna"],
    "stomach pain": ["stomach pain", "stomach ache", "stomachache", "stomach cramps", "abdominal pain", "belly pain", "tummy pain", "tummy ache", "pet dard", "pet me dard", "stomach hurts", "stomach is paining", "stomach burning", "burning in my stomach", "stomach has been burning", "stomach is burning"],
    "nausea": ["nausea", "nauseous", "nauseated", "feeling sick", "feel sick", "queasy", "ulti jaisa"],
    "vomiting": ["vomiting", "vomit", "vomited", "throwing up", "threw up", "puking", "ulti"],
    "diarrhea": ["diarrhea", "diarrhoea", "loose motions", "loose motion", "loose stools", "watery stools", "dast"],
    "constipation": ["constipation", "constipated", "hard stools", "not passing stool"],
    "acidity": ["acidity", "acid reflux", "heartburn", "gas problem", "gastric", "indigestion", "bloating", "bloated"],
    "chest pain": ["chest pain", "chest tightness", "tightness in chest", "pain in chest", "chest hurts", "seene me dard", "chest is paining", "pressure in chest", "chest pressure", "chhati me dard"],
    "shortness of breath": ["shortness of breath", "breathless", "out of breath", "short of breadth", "short of breath", "breathlessness", "difficulty breathing", "trouble breathing", "can't breathe", "cannot breathe", "breathing difficulty", "breathing problem", "saans lene me takleef", "saans phulna", "wheezing", "shwas ghenyas tras"],
    "fatigue": ["fatigue", "tiredness", "tired", "weakness", "weak", "exhausted", "exhaustion", "no energy", "lethargy", "lethargic", "kamzori", "thakaan", "thakan"],
    "body ache": ["body ache", "body aches", "body pain", "body pains", "muscle pain", "muscle aches", "muscle ache", "body is paining", "badan dard", "badan me dard", "myalgia"],
    "joint pain": ["joint pain", "joint pains", "joints pain", "knee pain", "arthralgia", "jodon me dard", "joints hurt", "joints are paining"],
    "back pain": ["back pain", "backache", "back ache", "lower back pain", "kamar dard", "back hurts"],
    "dizziness": ["dizziness", "dizzy", "giddiness", "giddy", "lightheaded", "light headed", "light-headed", "vertigo", "chakkar", "room spinning"],
    "chills": ["chills", "shivering", "shivers", "rigors", "thand lagna"],
    "sweating": ["sweating", "night sweats", "excessive sweating", "sweaty", "paseena"],
    "rash": ["rash", "skin rash", "red spots", "red patches", "hives", "skin allergy"],
    "itching": ["itching", "itchy", "itchiness", "khujli", "khujlee"],
    "swelling": ["swelling", "swollen", "swollen feet", "swollen legs", "puffiness", "sujan"],
    "loss of appetite": ["loss of appetite", "no appetite", "not feeling hungry", "don't feel like eating", "do not feel like eating", "poor appetite", "bhookh nahi", "bhookh nahin", "not eating"],
    "loss of taste or smell": ["loss of taste", "loss of smell", "can't smell", "cannot smell", "can't taste", "cannot taste", "no sense of smell", "no sense of taste", "anosmia"],
    "ear pain": ["ear pain", "earache", "ear ache", "ear is paining", "kaan dard", "kaan me dard"],
    "toothache": ["toothache", "tooth ache", "tooth pain", "dant dard"],
    "eye pain": ["eye pain", "eye ache", "eyes hurt", "eye is paining", "aankh dard", "red eyes", "watery eyes"],
    "blurred vision": ["blurred vision", "blurry vision", "blurred eyesight", "vision is blurry", "double vision"],
    "burning urination": ["burning urination", "burning while urinating", "burning during urination", "burning sensation while passing urine", "painful urination", "pain while urinating", "burning in urine", "burning sensation while urinating", "burning sensation during urination", "burning micturition", "pain during urination", "burning urine", "burning when i urinate", "burning when urinating", "peshab me jalan", "laghvila burning"],
    "frequent urination": ["frequent urination", "urinating frequently", "passing urine frequently", "urinating a lot", "peeing a lot", "baar baar peshab"],
    "weight loss": ["weight loss", "losing weight", "lost weight", "weight is dropping", "wajan kam", "wajan kami"],
    "palpitations": ["palpitations", "palpitation", "racing heart", "heart racing", "heart pounding", "fast heartbeat", "irregular heartbeat", "heart beating fast", "dil ki dhadkan"],
    "insomnia": ["insomnia", "not able to sleep", "couldn't sleep", "could not sleep", "sleepless nights", "unable to fall asleep", "can't sleep", "cannot sleep", "unable to sleep", "trouble sleeping", "difficulty sleeping", "sleeplessness", "neend nahi", "sleep problem", "jhop yet nahi", "jhop nahi"],
    "anxiety": ["anxiety", "anxious", "panic attack", "panic attacks", "nervousness", "nervous", "restless", "restlessness"],
    "low mood": ["low mood", "feeling low", "feeling down", "depressed", "depression", "sadness", "feeling sad", "hopeless"],
    "numbness": ["numbness", "numb", "tingling", "pins and needles"],
    "seizure": ["seizure", "seizures", "convulsion", "convulsions", "fits"],
    "fainting": ["fainting", "fainted", "passed out", "blackout", "blacked out", "loss of consciousness", "unconscious"],
    "bleeding": ["bleeding", "blood in stool", "blood in urine", "blood in sputum", "coughing blood", "coughing up blood", "vomiting blood", "nosebleed", "nose bleeding"],
}

# canonical symptom -> body system (used to group the doctor summary)
SYSTEM = {
    "fever": "General", "fatigue": "General", "chills": "General", "sweating": "General",
    "weight loss": "General", "loss of appetite": "General", "body ache": "General",
    "headache": "Neurological", "dizziness": "Neurological", "numbness": "Neurological",
    "seizure": "Neurological", "fainting": "Neurological",
    "insomnia": "Mental health", "anxiety": "Mental health", "low mood": "Mental health",
    "cough": "Respiratory", "sore throat": "Respiratory", "cold": "Respiratory",
    "shortness of breath": "Respiratory", "loss of taste or smell": "Respiratory",
    "chest pain": "Cardiovascular", "palpitations": "Cardiovascular", "swelling": "Cardiovascular",
    "stomach pain": "Gastrointestinal", "nausea": "Gastrointestinal", "vomiting": "Gastrointestinal",
    "diarrhea": "Gastrointestinal", "constipation": "Gastrointestinal", "acidity": "Gastrointestinal",
    "joint pain": "Musculoskeletal", "back pain": "Musculoskeletal",
    "rash": "Skin", "itching": "Skin",
    "ear pain": "ENT / Eye / Dental", "toothache": "ENT / Eye / Dental",
    "eye pain": "ENT / Eye / Dental", "blurred vision": "ENT / Eye / Dental",
    "burning urination": "Urinary", "frequent urination": "Urinary",
    "bleeding": "Bleeding",
}

# body location -> canonical symptom when it appears next to a pain word
# ("pain in my chest" -> chest pain).  Anything else becomes "<location> pain".
LOCATION_TO_SYMPTOM = {
    "chest": "chest pain", "centre of chest": "chest pain", "center of chest": "chest pain", "middle of chest": "chest pain",
    "stomach": "stomach pain", "abdomen": "stomach pain", "upper abdomen": "stomach pain", "lower abdomen": "stomach pain",
    "belly": "stomach pain", "tummy": "stomach pain",
    "head": "headache", "forehead": "headache", "temples": "headache", "back of head": "headache",
    "one side of head": "headache", "behind the eyes": "headache", "behind eyes": "headache",
    "throat": "sore throat", "ear": "ear pain", "eye": "eye pain", "eyes": "eye pain",
    "back": "back pain", "lower back": "back pain", "upper back": "back pain",
    "knee": "joint pain", "knees": "joint pain", "left knee": "joint pain", "right knee": "joint pain",
    "ankle": "joint pain", "ankles": "joint pain", "wrist": "joint pain", "elbow": "joint pain",
    "whole body": "body ache", "teeth": "toothache", "tooth": "toothache", "gum": "toothache", "gums": "toothache",
}

# ---------------------------------------------------------------- negation
NEG_TRIGGERS = [
    "no", "not", "never", "without", "denies", "denied", "free of", "free from",
    "negative for", "absence of", "don't have", "do not have", "doesn't have",
    "does not have", "didn't have", "did not have", "haven't had", "have not had",
    "hasn't had", "has not had", "no longer", "none", "ruled out", "not suffering from",
]
# Hindi/Hinglish negation comes AFTER the symptom ("bukhar nahi hai")
POST_NEG_TOKENS = ["nahi", "nahin", "nhi", "absent", "negative"]
POST_NEG_PHRASES = [["not", "present"], ["not", "there"], ["ruled", "out"], ["no", "more"], ["not", "anymore"], ["not", "any", "more"], ["not", "at", "all"]]
RESOLVED_TOKENS = ["gone", "resolved", "cured", "vanished", "disappeared"]
# Tokens that end a negation / uncertainty scope.
SCOPE_TERMINATORS = ["but", "however", "although", "though", "except", "yet", "still", "whereas", "only", "just", "lekin", "par", "magar",
                     "i", "i'm", "i've", "i'd", "he", "she", "they", "we", "it", "it's", "there", "mujhe", "main"]
# Tokens that may sit between a trigger and a symptom without breaking the scope.
SCOPE_GLUE = ["have", "has", "had", "been", "being", "having", "feel", "feeling", "felt", "experiencing", "experienced", "got", "getting", "any",
              "a", "an", "the", "of", "sign", "signs", "history", "symptom", "symptoms", "complaint", "complaints", "other", "such", "even",
              "or", "nor", "and", "also", "my", "much", "kind", "type", "sort", "than", "to", "with", "suffering", "from"]
PSEUDO_NEG = [["no", "change"], ["not", "sure"], ["no", "increase"], ["not", "only"], ["no", "worse"], ["not", "getting", "better"], ["not", "improving"],
              ["not", "better"], ["no", "relief"], ["not", "relieved"], ["no", "improvement"], ["not", "getting", "worse"], ["no", "difference"]]
UNCERTAIN_TRIGGERS = [["maybe"], ["perhaps"], ["probably"], ["possibly"], ["might"], ["suspect"], ["suspecting"], ["unsure"],
                      ["i", "think"], ["not", "sure"], ["feels", "like"], ["seems", "like"], ["could", "be"], ["may", "be"], ["may", "have"], ["shayad"]]

# ---------------------------------------------------------------- severity etc.
# severity label -> phrases (numeric "7/10" scales are handled in code)
SEVERITY = {
    "severe": ["severe", "severely", "intense", "intolerable", "unbearable", "excruciating", "terrible", "horrible", "very bad", "really bad", "extreme", "extremely", "worst", "bahut zyada", "bohot zyada", "bahut tez", "agonizing", "agonising", "crippling", "very severe"],
    "moderate": ["moderate", "moderately", "considerable", "noticeable", "bothersome", "annoying", "troubling", "high", "bad", "painful", "a lot", "tez", "zyada"],
    "mild": ["mild", "mildly", "slight", "slightly", "a bit", "a little", "little bit", "minor", "light", "low grade", "low-grade", "thoda", "thodi", "halka", "halki"],
}
SEVERITY_SCORE = {"mild": 1, "moderate": 2, "severe": 3}
INTENSIFIERS = ["very", "really", "extremely", "super", "bahut", "bohot", "so", "too", "highly", "incredibly"]
NEGATORS_FOR_SEVERITY = ["not", "no", "isn't", "wasn't", "never", "aren't", "hardly"]

# progression of the symptom
TREND = {
    "worsening": ["worse", "worsening", "worsened", "getting worse", "increasing", "increased", "aggravating", "deteriorating", "badh raha", "badh rahi", "zyada ho raha", "zyada ho rahi"],
    "improving": ["better", "improving", "improved", "getting better", "reducing", "decreasing", "subsiding", "settling", "kam ho raha", "kam ho rahi", "easing"],
    "constant": ["constant", "constantly", "persistent", "persisting", "unchanged", "not going away", "won't go away", "continuous", "continuously", "all the time", "all day", "non stop", "non-stop"],
    "intermittent": ["on and off", "comes and goes", "intermittent", "occasional", "occasionally", "now and then", "sometimes", "off and on", "episodic", "in episodes"],
}
WORSEN_WORDS = ["worse", "worsens", "worsen", "worsening", "aggravated", "aggravates", "increases", "triggered", "triggers", "starts", "comes", "brought", "caused", "more"]
RELIEVE_WORDS = ["better", "relief", "relieved", "relieves", "improves", "improved", "eases", "less", "reduces", "subsides", "settles"]

# how the sensation feels
QUALITY = ["sharp", "stabbing", "dull", "throbbing", "burning", "cramping", "cramps", "crampy", "squeezing", "pressing", "shooting",
           "pulsating", "gnawing", "colicky", "aching", "tight", "heavy", "pricking"]

ONSET = {"sudden": ["suddenly", "sudden", "abruptly", "all of a sudden", "out of nowhere", "overnight"],
         "gradual": ["gradually", "slowly", "gradual", "over time", "slowly slowly"]}

# ---------------------------------------------------------------- triggers
TRIGGER_CUES = ["after", "before", "when", "while", "during", "on", "with", "whenever", "if", "upon", "at", "in",
                "triggered", "aggravated", "caused", "relieved", "worsened", "brought", "induced"]
TRIGGER_FILLERS = ["the", "my", "a", "an", "i", "you", "we", "take", "takes", "taking", "have", "get", "feel", "every", "any", "by", "on", "of", "each", "taking", "doing", "am", "is", "start", "starts", "trying"]
TRIGGER_OBJECTS = [
    "eating", "eat", "meals", "meal", "food", "fasting", "walking", "walk", "climbing stairs", "climb stairs", "climbing", "stairs", "exercise", "exercising",
    "running", "run", "lying down", "lie down", "lying flat", "bending", "bend", "sleeping", "waking up", "coughing", "cough", "swallowing", "swallow",
    "urinating", "passing urine", "passing stool", "standing up", "standing", "stand", "sitting", "stress", "cold water", "spicy food", "oily food",
    "milk", "tea", "coffee", "empty stomach", "movement", "moving", "touching", "breathing", "deep breath", "deep breathing", "taking deep breath",
    "lifting", "night", "morning", "evening", "afternoon", "bathing", "sun exposure", "dust", "smoke", "cold weather", "rain", "medicine", "tablet",
    "medication", "talking", "laughing", "sneezing", "turning", "rest", "resting", "sleep", "heavy meals", "drinking", "drinking water", "smoking",
    "alcohol", "pressing", "pressure", "touch", "heat", "cold air", "travel", "travelling", "driving", "lunch", "dinner", "breakfast", "antacid", "painkiller", "painkillers", "medicines", "tablets", "water",
]

# ---------------------------------------------------------------- body locations
LOCATIONS = [
    "upper abdomen", "lower abdomen", "right side", "left side", "upper right", "lower right", "upper left", "lower left",
    "left arm", "right arm", "left leg", "right leg", "left shoulder", "right shoulder", "left knee", "right knee",
    "behind the eyes", "behind eyes", "back of head", "forehead", "temples", "one side of head", "both sides",
    "lower back", "upper back", "neck", "jaw", "left jaw", "centre of chest", "center of chest", "middle of chest",
    "chest", "abdomen", "stomach", "throat", "ear", "eyes", "eye", "feet", "foot", "legs", "arms", "hands", "face", "whole body",
    "head", "back", "knees", "knee", "ankles", "ankle", "wrist", "elbow", "arm", "leg", "hand", "shoulder", "hip", "hips", "thigh",
    "calf", "heel", "finger", "fingers", "toe", "toes", "tongue", "lips", "gums", "nose", "scalp", "skin", "cheek", "tummy", "belly",
    "navel", "groin", "ribs", "armpit", "pelvis", "palms", "soles", "joints", "joint", "teeth", "tooth", "gum",
]
RADIATION_WORDS = ["shoots", "shoot", "runs", "radiated", "radiating", "radiates", "radiate", "spreading", "spreads", "spread", "going", "goes", "shooting", "travelling", "traveling", "travels", "extending", "moving", "moves", "referred"]

# ---------------------------------------------------------------- red flags
RED_FLAGS = [
    {"id": "RF1", "title": "Chest pain reported", "any_symptoms": ["chest pain"], "modifiers": [], "level": "emergency",
     "advice": "Chest pain needs same-day medical evaluation; seek emergency help if it is crushing, spreads to the arm or jaw, or comes with sweating or breathlessness."},
    {"id": "RF2", "title": "Breathing difficulty", "any_symptoms": ["shortness of breath"], "modifiers": [], "level": "emergency",
     "advice": "Difficulty breathing should be assessed urgently."},
    {"id": "RF3", "title": "Fainting or seizure", "any_symptoms": ["fainting", "seizure"], "modifiers": [], "level": "emergency",
     "advice": "Fainting or seizures need urgent medical assessment."},
    {"id": "RF4", "title": "Bleeding reported", "any_symptoms": ["bleeding"], "modifiers": [], "level": "urgent",
     "advice": "Unexplained bleeding should be examined promptly."},
    {"id": "RF5", "title": "Fever lasting 3 or more days", "any_symptoms": ["fever"], "modifiers": [], "level": "urgent", "min_days": 3,
     "advice": "Fever for several days needs evaluation; the doctor may consider infection screening."},
    {"id": "RF6", "title": "Persistent vomiting or diarrhoea (dehydration risk)", "any_symptoms": ["vomiting", "diarrhea"], "modifiers": [], "level": "urgent", "min_days": 2,
     "advice": "Prolonged vomiting or loose motions risk dehydration."},
    {"id": "RF7", "title": "Sudden or neck-stiffness headache", "any_symptoms": ["headache"], "modifiers": ["sudden", "suddenly", "worst headache", "worst of my life", "thunderclap", "stiff neck", "neck stiffness"], "level": "emergency",
     "advice": "Sudden severe headache, or headache with a stiff neck, needs urgent evaluation."},
    {"id": "RF8", "title": "Severe symptom reported", "any_symptoms": [], "modifiers": [], "level": "attention", "severe_any": True,
     "advice": "At least one symptom is described as severe."},
    {"id": "RF9", "title": "Self-harm language", "any_symptoms": [], "modifiers": ["suicide", "suicidal", "end my life", "kill myself", "want to die", "no reason to live", "self harm", "self-harm", "hurt myself"], "level": "emergency", "modifier_only": True,
     "advice": "Statements about self-harm need immediate human support. In India you can call Tele-MANAS at 14416 or 1-800-891-4416."},
]
LEVEL_RANK = {"routine": 0, "attention": 1, "urgent": 2, "emergency": 3}

# ---------------------------------------------------------------- who / when
FAMILY_NOUNS = ["mother", "father", "wife", "husband", "son", "daughter", "brother", "sister", "friend", "child", "baby", "grandmother",
                "grandfather", "mom", "dad", "mummy", "papa", "kid", "uncle", "aunt", "colleague", "neighbour", "neighbor", "toddler", "boy", "girl",
                "bete", "beta", "beti", "maa", "pita", "bhai", "behen", "bahen", "patni", "pati", "bachcha", "bachche", "bachchi", "dadi", "dada", "nani", "nana"]
POSSESSIVES = ["my", "his", "her", "our", "mera", "meri", "mere", "hamare", "hamari"]
FIRST_PERSON = ["i", "i'm", "i've", "i'd", "i'll", "me", "mujhe", "main", "mera", "meri", "myself"]
CLAUSE_PRONOUNS = ["i", "i'm", "i've", "i'd", "he", "she", "they", "we", "it", "it's", "there", "my", "his", "her", "mujhe", "main", "mera", "meri"]
HISTORY_STRONG = ["history of", "in the past", "previously", "used to have", "used to get", "last year", "childhood", "had it before", "earlier in life"]
HISTORY_WEAK = ["years ago", "year ago", "months ago", "month ago"]
CURRENT_CUES = ["started", "began", "begun", "since", "still", "ongoing", "persist", "continues", "continuing", "till now", "till date", "even now", "now"]

# numbers / time units
NUM_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "twenty": 20, "thirty": 30,
    "couple": 2, "few": 3, "several": 4, "half": 0.5,
    "ek": 1, "do": 2, "teen": 3, "char": 4, "paanch": 5, "panch": 5, "chhe": 6, "saat": 7, "aath": 8, "nau": 9, "das": 10,
}
UNIT_DAYS = {
    "minute": 1 / 1440, "minutes": 1 / 1440, "min": 1 / 1440, "mins": 1 / 1440,
    "hour": 1 / 24, "hours": 1 / 24, "hr": 1 / 24, "hrs": 1 / 24, "ghante": 1 / 24, "ghanta": 1 / 24,
    "day": 1, "days": 1, "din": 1, "dino": 1,
    "week": 7, "weeks": 7, "hafte": 7, "hafta": 7, "haftey": 7, "hafton": 7,
    "month": 30, "months": 30, "mahine": 30, "mahina": 30, "mahino": 30,
    "year": 365, "years": 365, "saal": 365, "saalon": 365,
    "night": None, "nights": None,   # placeholder so "3 nights" can be read as days
}
UNIT_DAYS["night"] = 1
UNIT_DAYS["nights"] = 1
WEEKDAYS = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
# relative onset phrases -> days before today (0 = within today)
RELATIVE_DAYS = {"today": 0, "this morning": 0, "this afternoon": 0, "this evening": 0, "tonight": 0, "yesterday": 1, "last night": 1,
                 "day before yesterday": 2, "aaj": 0, "kal": 1, "parso": 2, "since morning": 0, "since afternoon": 0, "since evening": 0}

# common misspellings -> canonical token
SPELLING = {
    "feaver": "fever", "fevar": "fever", "fiver": "fever", "hedache": "headache", "headach": "headache", "hedaches": "headaches",
    "coff": "cough", "cogh": "cough", "stomache": "stomach", "stomac": "stomach", "stommach": "stomach", "vomitting": "vomiting",
    "vommiting": "vomiting", "diarreah": "diarrhea", "dizzyness": "dizziness", "nausia": "nausea",
    "breathlesness": "breathlessness", "breating": "breathing", "weekness": "weakness", "tierd": "tired",
    "tiered": "tired", "pian": "pain", "chets": "chest", "thraot": "throat", "throt": "throat",
    "sneezeing": "sneezing", "swolen": "swollen", "dayz": "days", "dys": "days",
    "wk": "week", "wks": "weeks", "yrs": "years", "yr": "year", "mnth": "month", "mnths": "months", "hv": "have", "cant": "can't",
    "dont": "don't", "doesnt": "doesn't", "didnt": "didn't", "havent": "haven't", "wont": "won't", "isnt": "isn't", "wasnt": "wasn't",
    "arent": "aren't", "im": "i'm", "ive": "i've", "temprature": "temperature", "temperture": "temperature",
    "sundy": "sunday", "mondey": "monday", "tuesdy": "tuesday", "wensday": "wednesday", "thrusday": "thursday", "firday": "friday", "saterday": "saturday",
    "yesturday": "yesterday", "yesterdy": "yesterday", "weeek": "week",
}

# ---------------------------------------------------------------- context
MEDICATIONS = ["paracetamol", "crocin", "dolo", "dolo 650", "calpol", "ibuprofen", "brufen", "combiflam", "aspirin", "disprin", "antacid", "digene", "eno",
               "pantoprazole", "pan 40", "omeprazole", "cetirizine", "azithromycin", "amoxicillin", "ors", "vicks", "cough syrup", "benadryl",
               "nimesulide", "diclofenac", "volini", "ointment", "kadha", "home remedy", "home remedies", "antibiotic", "antibiotics", "painkiller", "painkillers", "inhaler"]
CONDITIONS = {
    "diabetes": ["diabetes", "diabetic", "sugar patient"],
    "hypertension": ["hypertension", "high blood pressure", "bp patient", "high bp"],
    "asthma": ["asthma", "asthmatic"],
    "thyroid disorder": ["thyroid"],
    "heart disease": ["heart disease", "heart patient", "cardiac patient"],
    "kidney disease": ["kidney disease", "kidney problem", "ckd"],
    "pregnancy": ["pregnant", "pregnancy"],
    "COPD": ["copd"],
    "tuberculosis": ["tuberculosis", "tb patient"],
    "cancer": ["cancer"],
}
TEMP_WORDS = ["temperature", "temp", "fever", "thermometer", "reading", "showing", "shows"]
TEMP_UNITS = ["f", "c", "°", "degree", "degrees", "fahrenheit", "celsius", "deg", "°f", "°c"]
