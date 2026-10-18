"""Leakage guard, time split and consumer endpoint of the late-delivery model."""

import importlib.util
import os

import numpy as np
import pandas as pd
import pytest

from models.consumer_models import delay_model
from models.consumer_models.delay_model import (BANNED_COLUMNS, CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES,
                                                assert_no_leakage, build_feature_frame, build_lookups,
                                                make_xgb_pipeline)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ── leakage ───────────────────────────────────────────────────────────────────

def test_no_banned_column_in_feature_list():
    assert not set(FEATURES) & BANNED_COLUMNS
    assert_no_leakage(FEATURES)


@pytest.mark.parametrize("leak", sorted(BANNED_COLUMNS) + ["days_for_shipping_real_lag1", "late_delivery_risk_mean"])
def test_leak_guard_rejects_banned_and_derived_columns(leak):
    with pytest.raises(ValueError):
        assert_no_leakage(FEATURES + [leak])


def test_required_post_delivery_columns_are_banned():
    for col in ("Days_for_shipping_real", "Delivery_Status", "Late_delivery_risk", "Order_Status"):
        assert col in BANNED_COLUMNS


def test_feature_frame_contains_only_declared_features():
    df = synthetic_orders(50)
    X = build_feature_frame(df)
    assert list(X.columns) == FEATURES
    for col in BANNED_COLUMNS & set(df.columns):
        assert col not in X.columns


def test_saved_model_uses_leak_free_features():
    """If a trained model exists locally, its stored feature list must also be clean."""
    if not os.path.exists(delay_model.MODEL_PATH):
        pytest.skip("model not trained in this checkout")
    import joblib

    meta = joblib.load(delay_model.MODEL_PATH)["metadata"]
    assert_no_leakage(meta["features"])


# ── time split ────────────────────────────────────────────────────────────────

def load_train_script():
    spec = importlib.util.spec_from_file_location("train_delay_model", os.path.join(ROOT, "scripts", "train_delay_model.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_time_split_trains_on_earlier_orders():
    df = synthetic_orders(1000)
    train, val, test = load_train_script().time_split(df)
    assert len(train) + len(val) + len(test) == len(df)
    assert train["Order_Date"].max() < val["Order_Date"].min()
    assert val["Order_Date"].max() < test["Order_Date"].min()


# ── synthetic model + endpoint ────────────────────────────────────────────────

def synthetic_orders(n, seed=0):
    rng = np.random.default_rng(seed)
    modes = np.array(["Standard Class", "Second Class", "First Class", "Same Day"])
    sched = {"Standard Class": 4, "Second Class": 2, "First Class": 1, "Same Day": 0}
    mode = rng.choice(modes, n)
    countries = np.array(["India", "France", "Mexico"])
    country = rng.choice(countries, n)
    product = rng.choice(np.array(["Widget", "Gadget"]), n)
    df = pd.DataFrame({
        "Order_Date": pd.Timestamp("2016-01-01") + pd.to_timedelta(rng.integers(0, 700 * 24, n), unit="h"),
        "Shipping_Mode": mode,
        "Type": rng.choice(np.array(["DEBIT", "CASH"]), n),
        "Customer_Segment": rng.choice(np.array(["Consumer", "Corporate"]), n),
        "Department_Name": np.where(product == "Widget", "Tools", "Toys"),
        "Category_Name": np.where(product == "Widget", "Hand tools", "Games"),
        "Product_Name": product,
        "Market": np.select([country == "India", country == "France"], ["Pacific Asia", "Europe"], "LATAM"),
        "Order_Region": np.select([country == "India", country == "France"], ["South Asia", "Western Europe"], "Central America"),
        "Order_Country": country,
        "Days_for_shipment_scheduled": [sched[m] for m in mode],
        "Product_Price": np.where(product == "Widget", 20.0, 35.0),
        "Order_Item_Quantity": rng.integers(1, 5, n),
        "Order_Item_Discount_Rate": rng.uniform(0, 0.2, n),
    })
    df["Sales"] = df["Product_Price"] * df["Order_Item_Quantity"]
    df["Late_delivery_risk"] = (rng.uniform(size=n) < np.where(df["Shipping_Mode"] == "First Class", 0.9, 0.4)).astype(int)
    df["Days_for_shipping_real"] = df["Days_for_shipment_scheduled"] + df["Late_delivery_risk"]
    df["Delivery_Status"] = np.where(df["Late_delivery_risk"] == 1, "Late delivery", "Shipping on time")
    df["Order_Status"] = "COMPLETE"
    return df


@pytest.fixture
def synthetic_bundle(monkeypatch):
    df = synthetic_orders(600)
    X = build_feature_frame(df)
    y = df["Late_delivery_risk"].to_numpy()
    pipe = make_xgb_pipeline(X[:450], y[:450], X[450:], y[450:], n_estimators=40, n_jobs=1)
    bundle = {
        "pipeline": pipe,
        "lookups": build_lookups(df),
        "metadata": {"model_name": "xgboost", "trained_at": "test", "threshold": 0.5, "features": FEATURES,
                     "test_metrics": {"roc_auc": 0.6, "pr_auc": 0.6},
                     "split": {"test": {"from": "2017-01-01 00:00:00", "to": "2017-12-31 00:00:00"}},
                     "quality_note": "synthetic"},
    }
    monkeypatch.setattr(delay_model, "_BUNDLE", bundle)
    from backend.routes import prediction_routes

    prediction_routes._destination_options.cache_clear()
    prediction_routes._shipping_mode_options.cache_clear()
    yield df
    prediction_routes._destination_options.cache_clear()
    prediction_routes._shipping_mode_options.cache_clear()


def test_predict_new_order_with_reasons(synthetic_bundle):
    out = delay_model.predict_new_order("Widget", "India", "First Class")
    assert 0.0 <= out["probability_late"] <= 1.0
    assert out["top_reasons"] and all(r["feature"] in FEATURES for r in out["top_reasons"])
    assert set(out["probability_by_shipping_mode"]) == {"Standard Class", "Second Class", "First Class", "Same Day"}
    # SHAP additivity: bias + contributions = model log-odds
    X = delay_model.new_order_row(delay_model.load_bundle(), "Widget", "India", "First Class")
    contrib = delay_model.shap_contributions(delay_model.load_bundle()["pipeline"], X)[0]
    p = 1 / (1 + np.exp(-contrib.sum()))
    assert p == pytest.approx(delay_model.load_bundle()["pipeline"].predict_proba(X)[0, 1], abs=1e-4)


def test_unknown_inputs_are_rejected(synthetic_bundle):
    with pytest.raises(ValueError):
        delay_model.predict_new_order("Nope", "India", "First Class")
    with pytest.raises(ValueError):
        delay_model.predict_new_order("Widget", "Atlantis", "First Class")


def test_consumer_endpoint(synthetic_bundle, monkeypatch):
    from backend.app import app
    from backend.routes import prediction_routes

    monkeypatch.setattr(prediction_routes, "_get_dataset", lambda: synthetic_bundle)
    client = app.test_client()
    r = client.post("/api/predict/consumer", json={"product": "Widget", "destination": "France",
                                                     "shipping_mode": "Standard Class",
                                                     "order_datetime": "2026-10-18T14:30"})
    assert r.status_code == 200, r.get_json()
    data = r.get_json()
    assert "probability_late" in data["prediction"]
    assert data["history"]["label"].startswith("Historical")
    assert data["external_signals"]["available"] is False      # no API keys -> no fake signals
    assert client.post("/api/predict/consumer", json={"product": "Widget", "pincode": "725"}).status_code == 400
    assert client.post("/api/predict/consumer", json={"product": "Widget"}).status_code == 400
    modes = client.get("/api/predict/options/shipping-modes").get_json()["shipping_modes"]
    assert [m["mode"] for m in modes][0] == "Same Day"


def test_shipping_csv_endpoint_uses_model_and_does_not_persist_upload(synthetic_bundle, tmp_path):
    import io

    from backend.app import app

    csv_bytes = synthetic_bundle.head(20).assign(Order_Id=range(20)).to_csv(index=False).encode()
    raw_dir = os.path.join(ROOT, "data", "raw")
    before = set(os.listdir(raw_dir)) if os.path.isdir(raw_dir) else set()
    r = app.test_client().post("/api/recommend/shipping",
                               data={"file": (io.BytesIO(csv_bytes), "../../evil.csv")},
                               content_type="multipart/form-data")
    assert r.status_code == 200, r.get_json()
    data = r.get_json()
    assert data["summary"]["orders_scored"] == 20
    assert set(data["orders"][0]["probability_late_by_mode"]) == {"Standard Class", "Second Class", "First Class", "Same Day"}
    after = set(os.listdir(raw_dir)) if os.path.isdir(raw_dir) else set()
    assert after == before
    assert not os.path.exists(os.path.join(ROOT, "..", "evil.csv"))


def test_country_names_are_english_and_round_trip():
    from models.consumer_models.country_names import SPANISH_TO_ENGLISH, resolve, to_dataset_name, to_english

    assert to_english("Estados Unidos") == "United States"
    assert to_english("Alemania") == "Germany"
    assert to_dataset_name("germany") == "Alemania"
    assert to_dataset_name("Alemania") == "Alemania"
    assert len(set(SPANISH_TO_ENGLISH.values())) == len(SPANISH_TO_ENGLISH)   # no two countries share a label
    assert resolve("Germany", {"Alemania": {}}) == "Alemania"
    assert resolve("India", {"India": {}}) == "India"


def test_consumer_endpoint_accepts_english_country(synthetic_bundle, monkeypatch):
    from backend.app import app
    from backend.routes import prediction_routes

    df = synthetic_bundle.replace({"Order_Country": {"France": "Francia"}})
    bundle = dict(delay_model._BUNDLE, lookups=build_lookups(df))
    monkeypatch.setattr(delay_model, "_BUNDLE", bundle)
    monkeypatch.setattr(prediction_routes, "_get_dataset", lambda: df)
    client = app.test_client()
    r = client.post("/api/predict/consumer", json={"product": "Widget", "destination": "France",
                                                     "shipping_mode": "Second Class"})
    assert r.status_code == 200, r.get_json()
    data = r.get_json()
    assert data["destination"] == "France" and data["destination_dataset_value"] == "Francia"
    assert "country level" in data["granularity"]
    opts = client.get("/api/predict/options/destinations").get_json()
    assert {"label": "France", "value": "Francia"} in opts["options"]
