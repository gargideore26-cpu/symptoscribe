"""SymptoScribe web app (Flask).

Run:  python app.py        then open http://127.0.0.1:5000
"""
import os
from functools import lru_cache

from flask import Flask, Response, jsonify, render_template, request

from nlp import analyze
import dataset
from report import build_report_pdf, clean_details

MAX_CHARS = 5000

# The dataset is English only, so one case each for Hinglish, Hindi and Marathi shows the language support.
HINDI_EXAMPLE = {"label": "हिन्दी", "text": "मुझे 3 दिन से तेज बुखार है, बदन दर्द और कमजोरी है। उल्टी नहीं है।"}
MARATHI_EXAMPLE = {"label": "मराठी", "text": "मला २ दिवसांपासून ताप आहे आणि डोकेदुखी आहे, खोकला नाही."}
HINGLISH_EXAMPLE = {
    "label": "Hinglish",
    "text": "Mujhe 2 din se bukhar hai aur sar dard bhi hai, khansi nahi hai. Kal se pet me dard bhi ho raha hai.",
}

def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 64 * 1024

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/api/examples")
    def examples():
        try:
            return jsonify(dataset.examples() + [HINGLISH_EXAMPLE, HINDI_EXAMPLE, MARATHI_EXAMPLE])
        except dataset.DatasetMissing as e:
            return jsonify({"error": str(e)}), 503

    @app.get("/api/dataset/random")
    def dataset_random():
        try:
            return jsonify(dataset.random_case(request.args.get("exclude", -1, type=int)))
        except dataset.DatasetMissing as e:
            return jsonify({"error": str(e)}), 503

    @app.get("/api/dataset")
    def dataset_report():
        try:
            return jsonify(dataset.coverage())
        except dataset.DatasetMissing as e:
            return jsonify({"error": str(e)}), 503

    @app.post("/api/analyze")
    def analyze_text():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("text"), str):
            return jsonify({"error": "Send JSON like {\"text\": \"I have a fever since yesterday\"}."}), 400
        text = payload["text"].strip()
        if not text:
            return jsonify({"error": "Please write a few words about the symptoms first."}), 400
        if len(text) > MAX_CHARS:
            return jsonify({"error": f"Please keep the text under {MAX_CHARS} characters."}), 413
        return jsonify(analyze(text))

    @app.post("/api/report")
    def report():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("text"), str) or not payload["text"].strip():
            return jsonify({"error": "Send JSON like {\"text\": \"...\"}."}), 400
        text = payload["text"].strip()
        if len(text) > MAX_CHARS:
            return jsonify({"error": f"Please keep the text under {MAX_CHARS} characters."}), 413
        pdf = build_report_pdf(analyze(text), clean_details(payload.get("details")))
        return Response(pdf, mimetype="application/pdf",
                        headers={"Content-Disposition": "attachment; filename=symptoscribe-report.pdf"})

    @app.get("/api/evaluation")
    def evaluation():
        return jsonify(_evaluation())

    @app.errorhandler(413)
    def too_large(_e):
        return jsonify({"error": "That request is too large."}), 413

    return app


@lru_cache(maxsize=1)
def _evaluation() -> dict:
    from evaluation.evaluate import run_evaluation
    return run_evaluation()


app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
