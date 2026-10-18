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
from backend.services import road_network

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

def _should_warm_up_graph() -> bool:
    """
    Load the cached road graph in a background thread so the first routing
    request does not pay the load time. Tests disable this (EPOCH_GRAPH_WARMUP=0).
    Flask's debug reloader imports this module in a watcher process AND in the
    serving child; only the child (WERKZEUG_RUN_MAIN=true) needs the graph.
    """
    if os.environ.get("EPOCH_GRAPH_WARMUP", "1") == "0":
        return False
    is_reloader_watcher = (__name__ == "__main__" and config.get("app", {}).get("debug", True)
                           and os.environ.get("WERKZEUG_RUN_MAIN") != "true")
    return not is_reloader_watcher


if _should_warm_up_graph():
    road_network.warm_up_async()
    from models.consumer_models import delay_model
    delay_model.warm_up_async()

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
    from models.consumer_models.delay_model import MODEL_PATH as DELAY_MODEL_PATH
    from models.producer_models.demand_segments import MODEL_PATH as DEMAND_MODEL_PATH

    graph = road_network.status()
    return {
        "status": "ok",
        "version": config.get("app", {}).get("version", "1.0.0"),
        # Which trained artifacts exist locally (all are gitignored and built by scripts/).
        "artifacts": {
            "delay_model": os.path.exists(DELAY_MODEL_PATH),
            "demand_segments": os.path.exists(DEMAND_MODEL_PATH),
            "road_graph": bool(graph["graph_file_present"] or graph["cache_file_present"]),
        },
    }

# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = config.get("app", {}).get("port", 5000)
    debug = config.get("app", {}).get("debug", True)
    print(f"\n  epoch backend running at http://localhost:{port}\n")
    app.run(debug=debug, port=port)
