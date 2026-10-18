"""
epoch/backend/routes/prediction_routes.py
------------------------------------------
Endpoints:
  GET  /api/predict/options/products   → unique product names from dataset
  GET  /api/predict/options/cities     → unique destination cities
  GET  /api/predict/options/pincodes   → unique customer zipcodes
  POST /api/predict/demand             → Producer: product + city → demand insights
  GET  /api/predict/options/destinations   → destination countries known to the delay model
  GET  /api/predict/options/shipping-modes → shipping modes with promised days
  POST /api/predict/consumer           → Consumer: new order (product, destination, mode) → late-delivery model
"""

import os
from datetime import datetime
from functools import lru_cache

from flask import Blueprint, request, jsonify

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

prediction_bp = Blueprint("prediction", __name__)


WAR_KEYWORDS = {
    "war", "conflict", "attack", "military", "sanction", "sanctions",
    "missile", "airstrike", "red sea", "shipping lane", "blockade",
}


def _external_signals(market: str) -> dict:
    """
    Weather / news context for the destination market, attached ONLY when the
    services return live data (API keys configured). Without keys the services
    return static sample data, which must never be shown as a real disruption.
    These signals are context for the user; they are not model inputs.
    """
    from backend.services.news_service import fetch_news
    from backend.services.weather_service import fetch_weather

    out = {"available": False, "weather": None, "news": None}
    try:
        weather = fetch_weather(region=market)
        news = fetch_news(market=market)
    except Exception as exc:
        out["reason"] = f"External services failed: {exc}"
        return out
    if weather.get("source") != "live" and news.get("source") != "live":
        out["reason"] = "No weather/news API keys configured, so no live external signals are shown."
        return out

    out["available"] = True
    if weather.get("source") == "live":
        risky = [w for w in (weather.get("weather") or {}).get(market, [])
                 if str(w.get("disruption_risk", "")).lower() in {"high", "medium"}]
        if risky:
            out["weather"] = "Live weather alerts in hubs: " + ", ".join(
                f"{w.get('city')} ({w.get('disruption_risk')})" for w in risky[:3]) + "."
    if news.get("source") == "live":
        hits = [a for a in news.get("articles") or []
                if any(k in str(a.get("title", "")).lower() for k in WAR_KEYWORDS)]
        if hits:
            out["news"] = f"Conflict-related headline: '{str(hits[0].get('title', '')).strip()}'"
    return out

# ── Dataset cache (loaded once on first request) ──────────────────────────────
_dataset_cache = None

def _get_dataset():
    global _dataset_cache
    if _dataset_cache is not None:
        return _dataset_cache

    from backend.utils.preprocessing import load_and_clean_csv

    def _iter_csv_paths(base_folder: str):
        folder_path = os.path.join(ROOT, base_folder)
        if not os.path.isdir(folder_path):
            return []
        csv_paths = []
        for dirpath, _, filenames in os.walk(folder_path):
            for fname in sorted(filenames):
                if fname.lower().endswith(".csv"):
                    csv_paths.append(os.path.join(dirpath, fname))
        return sorted(csv_paths)

    expected_cols = [
        "Product_Name",
        "Order_Region",
        "Order_Item_Quantity",
        "Order_Profit_Per_Order",
        "Sales",
        "Category_Name",
        "Market",
        "Order_City",
    ]

    candidates = []
    for folder in ["data/processed", "data/raw"]:
        for csv_path in _iter_csv_paths(folder):
            try:
                df = load_and_clean_csv(csv_path)
            except Exception:
                continue

            col_score = sum(1 for c in expected_cols if c in df.columns)
            name_score = 1 if "supplychain" in os.path.basename(csv_path).lower() else 0
            total_score = (col_score * 10) + name_score
            candidates.append((total_score, len(df), csv_path, df))

    if candidates:
        candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
        best_score, _, _, best_df = candidates[0]
        if best_score > 0:
            _dataset_cache = best_df
            return best_df

    raise FileNotFoundError(
        "No compatible CSV found in data/processed/ or data/raw/. "
        "Place the supply chain dataset CSV there (subfolders are supported) and restart."
    )


# ── Dropdown options ──────────────────────────────────────────────────────────

@prediction_bp.route("/options/products", methods=["GET"])
def get_products():
    try:
        df = _get_dataset()
        col = next((c for c in ["Product_Name","Category_Name"] if c in df.columns), None)
        products = sorted(df[col].dropna().unique().tolist()) if col else []
        return jsonify({"products": products})
    except FileNotFoundError as e:
        return jsonify({"products": [], "warning": str(e)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@prediction_bp.route("/options/cities", methods=["GET"])
def get_cities():
    try:
        df = _get_dataset()
        col = next((c for c in ["Order_City","Customer_City"] if c in df.columns), None)
        cities = sorted(df[col].dropna().unique().tolist()) if col else []
        return jsonify({"cities": cities})
    except FileNotFoundError as e:
        return jsonify({"cities": [], "warning": str(e)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@prediction_bp.route("/options/pincodes", methods=["GET"])
def get_pincodes():
    try:
        df = _get_dataset()
        col = "Customer_Zipcode" if "Customer_Zipcode" in df.columns else None
        if not col:
            return jsonify({"pincodes": []})
        raw = df[col].dropna().unique()
        pincodes = sorted(set(
            str(int(float(p))) for p in raw
            if str(p).strip() not in ("", "nan")
        ))
        return jsonify({"pincodes": pincodes})
    except FileNotFoundError as e:
        return jsonify({"pincodes": [], "warning": str(e)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@lru_cache(maxsize=1)
def _destination_options() -> tuple:
    from models.consumer_models.country_names import to_english
    from models.consumer_models.delay_model import load_bundle

    countries = load_bundle()["lookups"]["countries"]
    return tuple(sorted(({"label": to_english(c), "value": c} for c in countries), key=lambda o: o["label"]))


@lru_cache(maxsize=1)
def _shipping_mode_options() -> tuple:
    from models.consumer_models.delay_model import load_bundle

    scheduled = load_bundle()["lookups"]["scheduled_days"]
    return tuple({"mode": m, "promised_days": d} for m, d in sorted(scheduled.items(), key=lambda kv: kv[1]))


@prediction_bp.route("/options/destinations", methods=["GET"])
def get_destinations():
    """
    Destination countries the delay model knows. `label` is English; `value` is
    DataCo's original (Spanish) Order_Country. The consumer API accepts either.
    """
    try:
        options = list(_destination_options())
        return jsonify({"destinations": [o["label"] for o in options], "options": options,
                        "granularity": "country"})
    except FileNotFoundError as e:
        return jsonify({"destinations": [], "warning": str(e)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@prediction_bp.route("/options/shipping-modes", methods=["GET"])
def get_shipping_modes():
    try:
        return jsonify({"shipping_modes": list(_shipping_mode_options())})
    except FileNotFoundError as e:
        return jsonify({"shipping_modes": [], "warning": str(e)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Producer: demand insight ──────────────────────────────────────────────────

@prediction_bp.route("/producer-overview", methods=["GET"])
def producer_overview():
    try:
        df = _get_dataset()
        from models.producer_models.demand_clustering import predict_overview
        return jsonify(predict_overview(df))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@prediction_bp.route("/demand", methods=["POST"])
def predict_demand():
    body    = request.get_json(silent=True) or {}
    product = body.get("product","").strip()
    city    = body.get("city","").strip()
    if not product or not city:
        return jsonify({"error": "Both 'product' and 'city' are required."}), 400
    try:
        df = _get_dataset()
        from models.producer_models.demand_clustering import predict_for_product_city
        return jsonify(predict_for_product_city(df, product, city))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Consumer: delivery insight ────────────────────────────────────────────────

@prediction_bp.route("/consumer", methods=["POST"])
def predict_consumer():
    """
    Late-delivery prediction for a hypothetical NEW order.
    Body: {"product": str, "destination": str (Order Country), "shipping_mode": str,
           "quantity": int (optional, default 1), "order_datetime": ISO string (optional, default now)}
    `destination` may be the English name or DataCo's original Spanish spelling.
    """
    body = request.get_json(silent=True) or {}
    product = str(body.get("product", "")).strip()
    destination = str(body.get("destination", "")).strip()
    shipping_mode = str(body.get("shipping_mode", "")).strip()
    if body.get("pincode") and not destination:
        return jsonify({"error": "Prediction by pincode was removed: it returned the historical late-rate "
                                 "average for that product and pincode, not a model prediction. Send "
                                 "'destination' (order country) and 'shipping_mode' instead."}), 400
    if not product or not destination or not shipping_mode:
        return jsonify({"error": "'product', 'destination' and 'shipping_mode' are required."}), 400
    try:
        quantity = int(body.get("quantity", 1) or 1)
        if quantity < 1:
            raise ValueError
    except (TypeError, ValueError):
        return jsonify({"error": "'quantity' must be a positive integer."}), 400
    order_dt = None
    if body.get("order_datetime"):
        try:
            order_dt = datetime.fromisoformat(str(body["order_datetime"]))
        except ValueError:
            return jsonify({"error": "'order_datetime' must be ISO format, e.g. 2026-10-18T14:30"}), 400
    try:
        df = _get_dataset()
        from models.consumer_models.consumer_insights import predict_new_order
        result = predict_new_order(df, product, destination, shipping_mode,
                                   quantity=quantity, order_datetime=order_dt,
                                   customer_segment=body.get("customer_segment"),
                                   payment_type=body.get("payment_type"))
        result["external_signals"] = _external_signals(result["context"]["market"])
        return jsonify(result)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500
