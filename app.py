"""SymptoScribe web app (Flask).

Run:  python app.py        then open http://127.0.0.1:5000
"""
import os
import socket
import time
from functools import lru_cache

from flask import Flask, Response, jsonify, render_template, request

from nlp import analyze
import dataset
import intake
import hashlib
import stats
from report import build_report_pdf, clean_details

MAX_CHARS = 5000
_last_recorded = {}

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
            return jsonify(dataset.examples())
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
        result = analyze(text)
        if payload.get("record") is True:
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if digest != _last_recorded.get("d"):   # pressing Analyze again on the same text counts once
                _last_recorded["d"] = digest
                stats.add([stats.event(result)])
        return jsonify(result)

    @app.get("/api/stats")
    def stats_summary():
        return jsonify(stats.summary())

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

    # ---- patient pre-visit intake
    def _intake_row(r):
        out = {"token": r["token"], "label": r["label"], "created": r["created"], "submitted": r["submitted"], "name": r["name"], "text": r["text"]}
        if r["submitted"]:
            a = analyze(r["text"])
            out.update(level=a["attention_level"], top_flag=a["red_flags"][0]["title"] if a["red_flags"] else "",
                       symptoms=[s["name"] for s in a["symptoms"] if s["subject"] == "patient" and s["status"] in ("present", "uncertain")][:6])
        return out

    @app.get("/p/<token>")
    def patient_page(token):
        rec = intake.get(token)
        return render_template("patient.html", valid=rec is not None, done=bool(rec and rec["submitted"]),
                               label=rec["label"] if rec else ""), (200 if rec else 404)

    @app.get("/api/intake")
    def intake_list():
        ip = ""
        try:
            if os.environ.get("HOST", "127.0.0.1") not in ("0.0.0.0", "::"):
                raise OSError   # only reachable from this computer, so a Wi-Fi address would not work
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("10.255.255.255", 1))
                ip = s.getsockname()[0]
        except OSError:
            pass
        return jsonify({"items": [_intake_row(r) for r in intake.list_all()], "lan_ip": ip})

    @app.post("/api/intake")
    def intake_create():
        payload = request.get_json(silent=True) or {}
        label = payload.get("label") if isinstance(payload, dict) and isinstance(payload.get("label"), str) else ""
        rec = intake.create(label)
        return jsonify({"token": rec["token"], "path": f"/p/{rec['token']}"}), 201

    @app.post("/api/intake/<token>/submit")
    def intake_submit(token):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not isinstance(payload.get("text"), str) or not payload["text"].strip():
            return jsonify({"error": "Please write how you feel first."}), 400
        if len(payload["text"].strip()) > 3000:
            return jsonify({"error": "Please keep it under 3000 characters."}), 413
        name = payload.get("name") if isinstance(payload.get("name"), str) else ""
        res = intake.submit(token, name, payload["text"])
        if res == "missing":
            return jsonify({"error": "This link is not valid."}), 404
        if res == "done":
            return jsonify({"error": "This form was already sent."}), 409
        return jsonify({"ok": True})

    @app.delete("/api/intake/<token>")
    def intake_delete(token):
        return (jsonify({"ok": True}), 200) if intake.delete(token) else (jsonify({"error": "Not found."}), 404)

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
    app.run(host=os.environ.get("HOST", "127.0.0.1"), port=port, debug=os.environ.get("FLASK_DEBUG") == "1")
