"""Builds the downloadable PDF report from an analysis result."""
from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fpdf.fonts import FontFace

CRIMSON = (217, 31, 61)
INK = (27, 18, 23)
MUTED = (106, 95, 102)
LINE = (230, 223, 226)

LEVELS = {
    "routine": "Routine review",
    "attention": "Needs the doctor's attention",
    "urgent": "See a doctor soon",
    "emergency": "Seek urgent care",
}
STATUS = {"present": "Present", "absent": "Denied", "resolved": "Resolved",
          "uncertain": "Possible", "history": "Past episode"}

_REPLACE = {"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-",
            "…": "...", "•": "-", " ": " ", "≈": "~"}


def _t(value) -> str:
    """Core PDF fonts only cover Latin-1; map common punctuation and drop the rest."""
    s = str(value if value is not None else "")
    for k, v in _REPLACE.items():
        s = s.replace(k, v)
    return s.encode("latin-1", "replace").decode("latin-1")


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _details(s: dict) -> str:
    bits = []
    if s.get("trend"):
        bits.append(s["trend"]["label"])
    if s.get("onset"):
        bits.append(s["onset"]["label"] + " onset")
    if s.get("frequency"):
        bits.append(s["frequency"]["text"])
    if s.get("temperature"):
        bits.append(f"{s['temperature']['value']} deg {s['temperature']['unit']}")
    bits += [q["label"] for q in s.get("quality", [])]
    if s.get("location") and s["location"]["text"] not in s["name"]:
        bits.append(s["location"]["text"])
    if s.get("radiates_to"):
        bits.append("radiates to " + s["radiates_to"]["text"])
    bits += [t["label"] for t in s.get("triggers", [])]
    return ", ".join(bits) or "-"


def _needs_unicode(text: str) -> bool:
    return any(ord(c) > 255 for c in text)


def _dur(s: dict) -> str:
    d = s.get("duration")
    if not d:
        return "-"
    return d["text"] if not _needs_unicode(d["text"]) else (d.get("approx") or "-")


def clean_details(raw) -> dict:
    """Typed-in report fields: short plain strings only. Nothing is stored anywhere."""
    out = {}
    if isinstance(raw, dict):
        for k in ("name", "age", "date", "doctor"):
            v = raw.get(k)
            if isinstance(v, str) and v.strip():
                out[k] = v.strip()[:80]
    return out


def _pretty_date(v: str) -> str:
    try:
        return datetime.strptime(v, "%Y-%m-%d").strftime("%d %b %Y")
    except ValueError:
        return v


def build_report_pdf(r: dict, details: dict = None) -> bytes:
    pdf = FPDF(format="A4")
    pdf.set_margins(18, 18, 18)
    pdf.set_auto_page_break(True, margin=18)
    pdf.add_page()
    w = pdf.epw

    def heading(text):
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*CRIMSON)
        pdf.cell(w, 6, _t(text.upper()), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*INK)

    # Title block
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(*INK)
    pdf.cell(w, 10, "SymptoScribe report", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(*MUTED)
    pdf.cell(w, 5, "Generated " + datetime.now().strftime("%d %b %Y, %H:%M"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.ln(2)
    pdf.set_draw_color(*CRIMSON)
    pdf.set_line_width(0.8)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + w, pdf.get_y())
    pdf.ln(5)

    details = clean_details(details)
    if details:
        shown = [("Patient", details.get("name")), ("Age", details.get("age")),
                 ("Date", _pretty_date(details["date"]) if details.get("date") else None), ("Doctor", details.get("doctor"))]
        shown = [(k, v) for k, v in shown if v]
        col = w / 2
        pdf.set_fill_color(250, 247, 248)
        for i in range(0, len(shown), 2):
            y0 = pdf.get_y()
            for j, (k, v) in enumerate(shown[i:i + 2]):
                pdf.set_xy(pdf.l_margin + j * col, y0)
                pdf.set_font("Helvetica", "B", 8.5)
                pdf.set_text_color(*MUTED)
                pdf.cell(18, 6, _t(k.upper()), fill=False)
                pdf.set_font("Helvetica", "", 11)
                pdf.set_text_color(*INK)
                pdf.cell(col - 18, 6, _t(v))
            pdf.set_y(y0 + 7)
        pdf.ln(2)

    level = r.get("attention_level", "routine")
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*CRIMSON)
    pdf.cell(w, 6, _t(LEVELS.get(level, LEVELS["routine"])), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    heading("Patient's Symptoms")
    pdf.set_font("Helvetica", "I", 10.5)
    pdf.set_text_color(70, 62, 66)
    pdf.set_fill_color(250, 247, 248)
    original = r.get("text", "")
    if _needs_unicode(original):
        lang = (r.get("language") or {}).get("name", "another language")
        names = ", ".join(_cap(x["name"]) for x in r.get("symptoms", []) if x["subject"] == "patient" and x["status"] in ("present", "uncertain"))
        original = f"Description entered in {lang} (Devanagari script). Symptoms recognised: {names or 'none'}."
    pdf.multi_cell(w, 5.5, _t(original), fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    heading("Note for the doctor")
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(*INK)
    pdf.multi_cell(w, 6.5, _t(r.get("summary", "")), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    vitals = r.get("vitals") or []
    if vitals:
        heading("Vital signs")
        for v in vitals:
            pdf.set_font("Helvetica", "B", 10.5)
            pdf.set_text_color(*INK)
            txt = f"{v['label']}: {v['value']} {v['unit']}".replace("°", " deg ")
            pdf.cell(70, 6, _t(txt))
            pdf.set_font("Helvetica", "B" if v["status"] != "normal" else "", 10.5)
            pdf.set_text_color(*(CRIMSON if v["status"] != "normal" else MUTED))
            pdf.cell(0, 6, _t(("Normal" if v["status"] == "normal" else v["status"].capitalize()) + (f" - {v['note']}" if v.get("note") else "")),
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_text_color(*INK)

    flags = r.get("red_flags") or []
    if flags:
        heading("Red flags")
        for f in flags:
            pdf.set_font("Helvetica", "B", 10.5)
            pdf.multi_cell(w, 5.5, _t("- " + f["title"] + "  (" + LEVELS.get(f["level"], "") + ")"), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(*MUTED)
            pdf.set_x(pdf.l_margin + 4)
            why = f"  ({f['why']})" if f.get("why") else ""
            pdf.multi_cell(w - 4, 5, _t(f.get("advice", "") + why), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_text_color(*INK)

    heading("Structured symptoms")
    symptoms = r.get("symptoms") or []
    if not symptoms:
        pdf.set_font("Helvetica", "", 10.5)
        pdf.cell(w, 6, "No symptoms were found in this text.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    else:
        pdf.set_draw_color(*LINE)
        pdf.set_line_width(0.2)
        pdf.set_font("Helvetica", "", 9.5)
        head_style = FontFace(emphasis="BOLD", size_pt=8.5, color=MUTED)
        name_style = FontFace(emphasis="BOLD", color=INK)
        body_style = FontFace(color=INK)
        with pdf.table(col_widths=(26, 13, 17, 13, 31), text_align="LEFT", line_height=5.2,
                       borders_layout="HORIZONTAL_LINES", padding=1.6,
                       first_row_as_headings=False) as table:
            head = table.row()
            for h in ("Symptom", "Status", "Since / for", "Severity", "Details"):
                head.cell(h, style=head_style)
            for s in symptoms:
                row = table.row()
                name = _cap(s["name"]) + (f" ({s['subject']})" if s.get("subject") != "patient" else "")
                row.cell(_t(name), style=name_style)
                row.cell(_t(STATUS.get(s["status"], s["status"])), style=body_style)
                row.cell(_t(_dur(s)), style=body_style)
                row.cell(_t(_cap(s["severity"]["label"]) if s.get("severity") else "-"), style=body_style)
                row.cell(_t(_details(s)), style=body_style)

    fups = r.get("follow_up_questions") or []
    if fups:
        heading("Questions the doctor may want to ask")
        pdf.set_font("Helvetica", "", 10.5)
        pdf.set_text_color(*INK)
        for q in fups:
            pdf.multi_cell(w, 5.8, _t("- " + q), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    return bytes(pdf.output())
