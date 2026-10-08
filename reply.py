"""Draft a short reply to the patient in English, Hindi or Marathi.

Template based: it lists what the engine found, gives advice by attention level, and asks for what the
checklist says is still missing. It never names a disease and the doctor edits it before sending.
The Hindi and Marathi wording should be read by a native speaker before real use.
"""

SYMPTOM_NAMES = {
    "hi": {
        "acidity": "एसिडिटी", "anxiety": "घबराहट", "back pain": "पीठ दर्द", "bleeding": "खून बहना",
        "blurred vision": "धुंधला दिखना", "body ache": "बदन दर्द", "burning urination": "पेशाब में जलन",
        "chest pain": "सीने में दर्द", "chills": "ठंड लगना", "cold": "सर्दी-जुकाम", "constipation": "कब्ज",
        "cough": "खांसी", "diarrhea": "दस्त", "dizziness": "चक्कर", "ear pain": "कान में दर्द",
        "eye pain": "आंख में दर्द", "fainting": "बेहोशी", "fatigue": "थकान", "fever": "बुखार",
        "frequent urination": "बार-बार पेशाब", "headache": "सिरदर्द", "insomnia": "नींद न आना", "itching": "खुजली",
        "joint pain": "जोड़ों का दर्द", "loss of appetite": "भूख न लगना", "loss of taste or smell": "स्वाद या गंध न आना",
        "low mood": "उदासी", "nausea": "मतली", "numbness": "सुन्नपन", "palpitations": "दिल की धड़कन तेज होना",
        "rash": "चकत्ते", "seizure": "दौरा", "shortness of breath": "सांस फूलना", "sore throat": "गले में खराश",
        "stomach pain": "पेट दर्द", "sweating": "पसीना", "swelling": "सूजन", "toothache": "दांत दर्द",
        "vomiting": "उल्टी", "weight loss": "वजन कम होना",
    },
    "mr": {
        "acidity": "अॅसिडिटी", "anxiety": "चिंता", "back pain": "पाठदुखी", "bleeding": "रक्तस्त्राव",
        "blurred vision": "दृष्टी धूसर होणे", "body ache": "अंगदुखी", "burning urination": "लघवीला जळजळ",
        "chest pain": "छातीत दुखणे", "chills": "थंडी वाजणे", "cold": "सर्दी", "constipation": "बद्धकोष्ठता",
        "cough": "खोकला", "diarrhea": "जुलाब", "dizziness": "चक्कर", "ear pain": "कानदुखी",
        "eye pain": "डोळे दुखणे", "fainting": "बेशुद्ध पडणे", "fatigue": "थकवा", "fever": "ताप",
        "frequent urination": "वारंवार लघवी", "headache": "डोकेदुखी", "insomnia": "झोप न येणे", "itching": "खाज",
        "joint pain": "सांधेदुखी", "loss of appetite": "भूक न लागणे", "loss of taste or smell": "चव किंवा वास न येणे",
        "low mood": "उदासी", "nausea": "मळमळ", "numbness": "बधिरता", "palpitations": "धडधड",
        "rash": "पुरळ", "seizure": "झटके", "shortness of breath": "धाप लागणे", "sore throat": "घसा दुखणे",
        "stomach pain": "पोटदुखी", "sweating": "घाम येणे", "swelling": "सूज", "toothache": "दातदुखी",
        "vomiting": "उलट्या", "weight loss": "वजन कमी होणे",
    },
}

TEXT = {
    "en": {
        "hello": "Hello,",
        "none": "Thank you for your message. The doctor will read it and get back to you.",
        "noted": "Thank you for telling us how you feel. We have noted: {list}.",
        "denied": "You said you do not have: {list}.",
        "routine": "If the symptoms last more than 3 days or get worse, please come back to see the doctor.",
        "attention": "Please come to the clinic so the doctor can examine you.",
        "urgent": "Please see a doctor soon, ideally today.",
        "emergency": "Please go to the nearest hospital or call emergency services right now.",
        "ask": "To help the doctor, please also tell us: {list}.",
        "bye": "Take care,\nYour doctor",
        "and": " and ", "days": lambda n: f"{n} day" + ("" if n == 1 else "s"),
        "items": {
            "duration": "how long you have had each symptom",
            "severity": "how severe each symptom is (mild, moderate or severe)",
            "temperature": "your temperature reading",
            "age": "your age",
            "allergies": "any allergies",
            "medicines": "the medicines you are taking",
            "conditions": "any other health conditions",
            "pregnancy": "whether you could be pregnant",
            "vitals": "your blood pressure, pulse and temperature, if you can measure them",
        },
    },
    "hi": {
        "hello": "नमस्कार,",
        "none": "आपके संदेश के लिए धन्यवाद। डॉक्टर इसे पढ़कर आपसे संपर्क करेंगे।",
        "noted": "आपने अपनी तकलीफ बताई, धन्यवाद। हमने नोट किया है: {list}।",
        "denied": "आपने बताया कि आपको ये नहीं हैं: {list}।",
        "routine": "अगर लक्षण 3 दिन से ज्यादा रहें या बढ़ें, तो कृपया डॉक्टर को दिखाने आएं।",
        "attention": "कृपया क्लिनिक आएं ताकि डॉक्टर आपकी जांच कर सकें।",
        "urgent": "कृपया जल्द से जल्द, हो सके तो आज ही, डॉक्टर को दिखाएं।",
        "emergency": "कृपया तुरंत नजदीकी अस्पताल जाएं या आपातकालीन सेवा को फोन करें।",
        "ask": "डॉक्टर की मदद के लिए कृपया यह भी बताएं: {list}।",
        "bye": "ध्यान रखें,\nआपके डॉक्टर",
        "and": " और ", "days": lambda n: f"{n} दिन से",
        "items": {
            "duration": "हर लक्षण कितने दिन से है",
            "severity": "हर लक्षण कितना तेज है (हल्का, मध्यम या तेज)",
            "temperature": "आपका तापमान कितना है",
            "age": "आपकी उम्र",
            "allergies": "कोई एलर्जी",
            "medicines": "आप कौन सी दवाइयां ले रहे हैं",
            "conditions": "कोई और बीमारी",
            "pregnancy": "क्या आप गर्भवती हो सकती हैं",
            "vitals": "बीपी, नाड़ी और तापमान, अगर नाप सकें",
        },
    },
    "mr": {
        "hello": "नमस्कार,",
        "none": "तुमच्या संदेशासाठी धन्यवाद. डॉक्टर तो वाचून तुमच्याशी संपर्क साधतील.",
        "noted": "तुम्ही तुमचा त्रास सांगितला, धन्यवाद. आम्ही नोंद केली आहे: {list}.",
        "denied": "तुम्ही सांगितले की तुम्हाला हे नाही: {list}.",
        "routine": "लक्षणे ३ दिवसांपेक्षा जास्त राहिली किंवा वाढली, तर कृपया डॉक्टरांना भेटायला या.",
        "attention": "कृपया दवाखान्यात या, म्हणजे डॉक्टर तुमची तपासणी करू शकतील.",
        "urgent": "कृपया लवकरात लवकर, शक्यतो आजच, डॉक्टरांना भेटा.",
        "emergency": "कृपया ताबडतोब जवळच्या रुग्णालयात जा किंवा आपत्कालीन सेवेला फोन करा.",
        "ask": "डॉक्टरांना मदत व्हावी म्हणून कृपया हेही सांगा: {list}.",
        "bye": "काळजी घ्या,\nतुमचे डॉक्टर",
        "and": " आणि ", "days": lambda n: f"{n} दिवसांपासून",
        "items": {
            "duration": "प्रत्येक लक्षण किती दिवसांपासून आहे",
            "severity": "प्रत्येक लक्षण किती तीव्र आहे (सौम्य, मध्यम किंवा तीव्र)",
            "temperature": "तुमचे तापमान किती आहे",
            "age": "तुमचे वय",
            "allergies": "काही अॅलर्जी आहे का",
            "medicines": "तुम्ही कोणती औषधे घेत आहात",
            "conditions": "इतर कोणते आजार आहेत का",
            "pregnancy": "तुम्ही गर्भवती असण्याची शक्यता आहे का",
            "vitals": "बीपी, नाडी आणि तापमान, मोजता आल्यास",
        },
    },
}
LANGS = tuple(TEXT)


def _join(parts, t):
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + t["and"] + parts[-1]


def draft_reply(a: dict, lang: str = "en") -> str:
    lang = lang if lang in TEXT else "en"
    t = TEXT[lang]
    names = SYMPTOM_NAMES.get(lang, {})
    found, denied = [], []
    for s in a["symptoms"]:
        if s["subject"] != "patient":
            continue
        label = names.get(s["name"], s["name"])
        if s["status"] in ("present", "uncertain"):
            days = (s.get("duration") or {}).get("days")
            if days:
                n = int(days) if float(days).is_integer() else round(days, 1)
                label += f" ({t['days'](n)})"
            if label not in found:
                found.append(label)
        elif s["status"] in ("absent", "resolved") and label not in denied:
            denied.append(label)
    lines = [t["hello"], ""]
    if not found:
        lines.append(t["none"])
    else:
        lines.append(t["noted"].format(list=_join(found, t)))
        if denied:
            lines.append(t["denied"].format(list=_join(denied, t)))
        lines += ["", t[a["attention_level"]]]
        todo = [t["items"][c["id"]] for c in a.get("checklist", []) if not c["done"] and c["id"] in t["items"]][:4]
        if todo:
            lines += ["", t["ask"].format(list=_join(todo, t))]
    lines += ["", t["bye"]]
    return "\n".join(lines)
