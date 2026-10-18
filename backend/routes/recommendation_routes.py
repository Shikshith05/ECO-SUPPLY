"""
epoch/backend/routes/recommendation_routes.py
----------------------------------------------
Endpoints:
  POST /api/recommend/shipping      → CSV of orders → late-delivery probability per shipping mode (what-if)
  GET  /api/recommend/weather       → Weather context for supply decisions
  GET  /api/recommend/news          → News signals affecting supply chain
"""

import os
import tempfile
from flask import Blueprint, request, jsonify

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.utils.preprocessing import load_and_clean_csv

recommendation_bp = Blueprint("recommendation", __name__)


# ── Consumer: Shipping Recommendation ────────────────────────────────────────
@recommendation_bp.route("/shipping", methods=["POST"])
def recommend_shipping():
    """
    Accepts a CSV of orders (DataCo columns) and returns, per order, the
    late-delivery model's probability under each shipping mode.
    Model: shipping_recommendation.py (what-if over the trained delay model).

    The upload is parsed from a temporary file that is deleted afterwards: it
    is never written under data/ (where it could be mistaken for the dataset)
    and the client-supplied filename is never used as a path.
    """
    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    f = request.files["file"]
    if not f.filename or not f.filename.lower().endswith(".csv"):
        return jsonify({"error": "Only CSV files are accepted"}), 400

    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    try:
        f.save(tmp)
        tmp.close()
        from models.consumer_models.shipping_recommendation import run_shipping_recommendation
        df = load_and_clean_csv(tmp.name)
        return jsonify(run_shipping_recommendation(df))
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 503
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        tmp.close()
        os.unlink(tmp.name)


# ── Weather Context ────────────────────────────────────────────────────────────
@recommendation_bp.route("/weather", methods=["GET"])
def get_weather():
    """
    Returns weather signals for major supply chain hubs.
    Query param: ?region=USCA  (optional filter)
    """
    region = request.args.get("region", None)
    try:
        from backend.services.weather_service import fetch_weather
        data = fetch_weather(region=region)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── News Signals ───────────────────────────────────────────────────────────────
@recommendation_bp.route("/news", methods=["GET"])
def get_news():
    """
    Returns supply-chain-relevant news signals.
    Query param: ?market=Europe  (optional filter)
    """
    market = request.args.get("market", None)
    try:
        from backend.services.news_service import fetch_news
        data = fetch_news(market=market)
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500
