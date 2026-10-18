"""
Leakage-free late-delivery model (consumer portal).

Target   : Late_delivery_risk (1 = the order shipped later than scheduled).
Features : ONLY information available when the order is placed. Anything
           recorded during or after fulfilment is banned, see BANNED_COLUMNS.

The pipeline is trained by `scripts/train_delay_model.py` and saved with
joblib to saved_models/delay_model.joblib together with the lookups needed to
build a feature row for a hypothetical NEW order (product -> category/price,
destination country -> region/market, shipping mode -> scheduled days).
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(ROOT, "saved_models", "delay_model.joblib")

TARGET = "Late_delivery_risk"

# Known only after the order ships or is delivered (or is the label itself).
# The model must never see these columns or anything computed from them.
BANNED_COLUMNS = frozenset({
    "Late_delivery_risk",        # the label
    "Delivery_Status",           # "Late delivery" / "Shipping on time": the label in words
    "Days_for_shipping_real",    # actual shipping days: label = real > scheduled
    "Order_Status",              # COMPLETE / CANCELED / SUSPECTED_FRAUD: set during fulfilment
    "Shipping_Date",             # shipping date - order date = real shipping days
    "shipping_delay_gap",        # real - scheduled (engineered in feature_engineering.py)
})

CATEGORICAL_FEATURES = [
    "Shipping_Mode",
    "Type",                      # payment type chosen at checkout
    "Customer_Segment",
    "Department_Name",
    "Category_Name",
    "Product_Name",
    "Market",
    "Order_Region",
    "Order_Country",
]

NUMERIC_FEATURES = [
    "Days_for_shipment_scheduled",   # promised shipping days, fixed by the shipping mode
    "Product_Price",
    "Order_Item_Quantity",
    "Order_Item_Discount_Rate",
    "Sales",                          # price x quantity, before discount
    "order_month",
    "order_dayofweek",
    "order_day",
    "order_hour",
]

FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


def assert_no_leakage(features: Iterable[str]) -> None:
    """Raise if any feature is banned or is named after a banned column."""
    lowered = {b.lower() for b in BANNED_COLUMNS}
    bad = [f for f in features if f in BANNED_COLUMNS or any(b in f.lower() for b in lowered)]
    if bad:
        raise ValueError(f"Leaky features in the delay model: {bad}")


assert_no_leakage(FEATURES)


def add_order_time_parts(df: pd.DataFrame) -> pd.DataFrame:
    dt = pd.to_datetime(df["Order_Date"], errors="coerce")
    df = df.copy()
    df["order_month"] = dt.dt.month
    df["order_dayofweek"] = dt.dt.dayofweek
    df["order_day"] = dt.dt.day
    df["order_hour"] = dt.dt.hour
    return df


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Select the model's input columns (in a fixed order) from a cleaned dataset."""
    df = add_order_time_parts(df)
    missing = [c for c in FEATURES if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset is missing delay-model columns: {missing}")
    X = df[FEATURES].copy()
    for c in CATEGORICAL_FEATURES:
        X[c] = X[c].astype(str).str.strip()
    for c in NUMERIC_FEATURES:
        X[c] = pd.to_numeric(X[c], errors="coerce")
    return X


def build_lookups(df: pd.DataFrame) -> dict:
    """Facts needed to describe a new order from (product, destination, mode)."""
    def mode_of(series):
        s = series.dropna()
        return s.mode().iloc[0] if not s.empty else None

    products = (df.groupby("Product_Name")
                  .agg(Category_Name=("Category_Name", mode_of),
                       Department_Name=("Department_Name", mode_of),
                       Product_Price=("Product_Price", "median"))
                  .reset_index())
    countries = (df.groupby("Order_Country")
                   .agg(Order_Region=("Order_Region", mode_of), Market=("Market", mode_of))
                   .reset_index())
    sched = df.groupby("Shipping_Mode")["Days_for_shipment_scheduled"].agg(mode_of)
    return {
        "products": {r.Product_Name: {"Category_Name": r.Category_Name, "Department_Name": r.Department_Name,
                                      "Product_Price": float(r.Product_Price)} for r in products.itertuples()},
        "countries": {r.Order_Country: {"Order_Region": r.Order_Region, "Market": r.Market}
                      for r in countries.itertuples()},
        "scheduled_days": {str(k): float(v) for k, v in sched.items()},
        "defaults": {"Type": str(mode_of(df["Type"])), "Customer_Segment": str(mode_of(df["Customer_Segment"]))},
    }


# ── Training helper (shared by scripts/train_delay_model.py and tests) ──────────

def make_xgb_pipeline(X_tr: pd.DataFrame, y_tr, X_va: pd.DataFrame, y_va, *, n_estimators: int = 2000,
                      early_stopping_rounds: int = 50, n_jobs: int = 4, seed: int = 42):
    """
    Ordinal-encode categoricals (unknown -> -1, so each input feature stays one
    column and SHAP values map 1:1 to features) and fit XGBoost with early
    stopping on the validation set. Returns a fitted sklearn Pipeline.
    """
    import xgboost as xgb
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OrdinalEncoder

    pre = ColumnTransformer([
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1,
                               encoded_missing_value=-1), CATEGORICAL_FEATURES),
        ("num", "passthrough", NUMERIC_FEATURES),
    ]).fit(X_tr)
    booster = xgb.XGBClassifier(
        n_estimators=n_estimators, learning_rate=0.05, max_depth=6, subsample=0.8, colsample_bytree=0.8,
        min_child_weight=5, reg_lambda=1.0, eval_metric="logloss", early_stopping_rounds=early_stopping_rounds,
        tree_method="hist", random_state=seed, n_jobs=n_jobs,
    )
    booster.fit(pre.transform(X_tr), y_tr, eval_set=[(pre.transform(X_va), y_va)], verbose=False)
    return Pipeline([("pre", pre), ("model", booster)])


# ── Inference ─────────────────────────────────────────────────────────────────

_BUNDLE = None


def warm_up_async() -> None:
    """Load the model bundle in a background thread at startup (joblib load takes ~2 s)."""
    if os.path.exists(MODEL_PATH):
        import threading

        threading.Thread(target=lambda: load_bundle(), name="delay-model-warmup", daemon=True).start()


def load_bundle(path: str = MODEL_PATH):
    global _BUNDLE
    if _BUNDLE is None:
        if not os.path.exists(path):
            raise FileNotFoundError(
                "Delay model not trained yet: run `.venv\\Scripts\\python scripts/train_delay_model.py`."
            )
        import joblib

        _BUNDLE = joblib.load(path)
    return _BUNDLE


def new_order_row(bundle: dict, product: str, destination_country: str, shipping_mode: str,
                  quantity: int = 1, discount_rate: float = 0.0, order_datetime: Optional[datetime] = None,
                  customer_segment: Optional[str] = None, payment_type: Optional[str] = None) -> pd.DataFrame:
    from models.consumer_models.country_names import resolve

    lk = bundle["lookups"]
    destination_country = resolve(destination_country, lk["countries"])
    if product not in lk["products"]:
        raise ValueError(f"Unknown product {product!r}.")
    if destination_country not in lk["countries"]:
        raise ValueError(f"Unknown destination country {destination_country!r}.")
    if shipping_mode not in lk["scheduled_days"]:
        raise ValueError(f"Unknown shipping mode {shipping_mode!r}; choose from {sorted(lk['scheduled_days'])}.")
    when = order_datetime or datetime.now()
    p = lk["products"][product]
    c = lk["countries"][destination_country]
    row = {
        "Shipping_Mode": shipping_mode,
        "Type": payment_type or lk["defaults"]["Type"],
        "Customer_Segment": customer_segment or lk["defaults"]["Customer_Segment"],
        "Department_Name": p["Department_Name"],
        "Category_Name": p["Category_Name"],
        "Product_Name": product,
        "Market": c["Market"],
        "Order_Region": c["Order_Region"],
        "Order_Country": destination_country,
        "Days_for_shipment_scheduled": lk["scheduled_days"][shipping_mode],
        "Product_Price": p["Product_Price"],
        "Order_Item_Quantity": quantity,
        "Order_Item_Discount_Rate": discount_rate,
        "Sales": p["Product_Price"] * quantity,
        "order_month": when.month,
        "order_dayofweek": when.weekday(),
        "order_day": when.day,
        "order_hour": when.hour,
    }
    return pd.DataFrame([row], columns=FEATURES)


def shap_contributions(pipeline, X: pd.DataFrame) -> np.ndarray:
    """
    Exact TreeSHAP values from XGBoost's built-in `pred_contribs` (log-odds
    units). Returns an array (n_rows, n_features + 1); the last column is the
    bias (expected value). Each input feature maps to exactly one encoded
    column (ordinal encoding), so contributions line up with FEATURES.
    """
    import xgboost as xgb

    pre, model = pipeline.named_steps["pre"], pipeline.named_steps["model"]
    Xt = pre.transform(X)
    # predict_proba stops at the early-stopping best iteration; the explanation
    # must use exactly the same trees or SHAP values won't add up to the score.
    best = getattr(model, "best_iteration", None)
    iteration_range = (0, best + 1) if best is not None else (0, 0)
    return model.get_booster().predict(xgb.DMatrix(Xt), pred_contribs=True, iteration_range=iteration_range)


def encoded_feature_order(pipeline) -> List[str]:
    names = pipeline.named_steps["pre"].get_feature_names_out()
    return [n.split("__", 1)[-1] for n in names]


def predict_new_order(product: str, destination_country: str, shipping_mode: str, top_k: int = 5, **kwargs) -> dict:
    bundle = load_bundle()
    pipe = bundle["pipeline"]
    X = new_order_row(bundle, product, destination_country, shipping_mode, **kwargs)
    proba = float(pipe.predict_proba(X)[0, 1])
    contribs = shap_contributions(pipe, X)[0]
    names = encoded_feature_order(pipe)
    reasons = sorted(
        ({"feature": n, "value": _jsonable(X.iloc[0][n]), "shap_log_odds": round(float(v), 4),
          "direction": "raises risk" if v > 0 else "lowers risk"}
         for n, v in zip(names, contribs[:-1])),
        key=lambda r: abs(r["shap_log_odds"]), reverse=True,
    )[:top_k]

    # What-if: same order, every shipping mode.
    by_mode = {}
    for mode in sorted(bundle["lookups"]["scheduled_days"]):
        Xm = new_order_row(bundle, product, destination_country, mode, **kwargs)
        by_mode[mode] = round(float(pipe.predict_proba(Xm)[0, 1]), 4)

    threshold = float(bundle["metadata"]["threshold"])
    return {
        "probability_late": round(proba, 4),
        "is_late_predicted": proba >= threshold,
        "decision_threshold": threshold,
        "top_reasons": reasons,
        "base_log_odds": round(float(contribs[-1]), 4),
        "probability_by_shipping_mode": by_mode,
        "inputs_used": {k: _jsonable(v) for k, v in X.iloc[0].to_dict().items()},
        "model": {"name": bundle["metadata"]["model_name"], "trained_at": bundle["metadata"]["trained_at"],
                  "test_roc_auc": bundle["metadata"]["test_metrics"]["roc_auc"],
                  "test_pr_auc": bundle["metadata"]["test_metrics"]["pr_auc"]},
    }


def _jsonable(v):
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return float(v)
    return v
