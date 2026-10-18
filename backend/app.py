"""
epoch/backend/app.py
--------------------
Main Flask application entry point.
Registers all route blueprints and serves the frontend.

Run from the repo root with `python backend/app.py` (or `python start_app.py`).
All imports are package-absolute from the repo root (backend.*, models.*).
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    # When started as `python backend/app.py`, sys.path[0] is backend/, not the repo root.
    sys.path.insert(0, BASE_DIR)

from flask import Flask, send_from_directory
from flask_cors import CORS

from backend.config import load_config
from backend.routes.prediction_routes import prediction_bp
from backend.routes.recommendation_routes import recommendation_bp
from backend.routes.routing_routes import routing_bp

# ── Load config (falls back to config.yaml.example on a fresh clone) ─────────
config = load_config()

# ── App setup ─────────────────────────────────────────────────────────────────
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR)
CORS(app)

app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024   # 50 MB upload limit
app.config["UPLOAD_FOLDER"]      = os.path.join(BASE_DIR, "data", "raw")
app.config["APP_CONFIG"]         = config

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# ── Register blueprints ───────────────────────────────────────────────────────
app.register_blueprint(prediction_bp,      url_prefix="/api/predict")
app.register_blueprint(recommendation_bp,  url_prefix="/api/recommend")
app.register_blueprint(routing_bp,         url_prefix="/api/route")

# ── Serve frontend ────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/producer")
def producer():
    return send_from_directory(FRONTEND_DIR, "producer.html")

@app.route("/consumer")
def consumer():
    return send_from_directory(FRONTEND_DIR, "consumer.html")

@app.route("/fleet")
def fleet():
    return send_from_directory(FRONTEND_DIR, "fleet.html")

@app.route("/<path:filename>")
def static_files(filename):
    return send_from_directory(FRONTEND_DIR, filename)

# ── Health check ──────────────────────────────────────────────────────────────
@app.route("/api/health")
def health():
    return {"status": "ok", "version": config.get("app", {}).get("version", "1.0.0")}

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = config.get("app", {}).get("port", 5000)
    debug = config.get("app", {}).get("debug", True)
    print(f"\n  epoch backend running at http://localhost:{port}\n")
    app.run(debug=debug, port=port)
