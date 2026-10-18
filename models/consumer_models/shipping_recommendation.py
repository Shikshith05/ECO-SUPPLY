"""
epoch/models/consumer_models/shipping_recommendation.py
--------------------------------------------------------
Shipping-mode comparison for a CSV of orders (POST /api/recommend/shipping).

Each order is re-scored by the trained late-delivery model once per shipping
mode (Same Day, First Class, Second Class, Standard Class), and the mode with
the lowest predicted probability of missing its promised shipping time is
reported. Only order-time columns are used (see delay_model.FEATURES); the
uploaded file's own outcome columns (Late_delivery_risk, Delivery_Status, ...)
are ignored.

Caveat, also returned in the response: this is a what-if comparison based on
historical associations, not a causal estimate, and "late" is relative to
each mode's own promise, so the least-risky mode is often the slowest.
"""

import numpy as np
import pandas as pd

from models.consumer_models import delay_model


def run_shipping_recommendation(df: pd.DataFrame, max_rows: int = 500) -> dict:
    bundle = delay_model.load_bundle()
    pipe = bundle["pipeline"]
    scheduled = bundle["lookups"]["scheduled_days"]
    modes = sorted(scheduled)

    X = delay_model.build_feature_frame(df).head(max_rows)
    probs = np.column_stack([
        pipe.predict_proba(X.assign(Shipping_Mode=m, Days_for_shipment_scheduled=scheduled[m]))[:, 1]
        for m in modes
    ])
    best = probs.argmin(axis=1)

    orders = []
    order_ids = df["Order_Id"].head(max_rows).tolist() if "Order_Id" in df.columns else [None] * len(X)
    for i in range(len(X)):
        orders.append({
            "Order_Id": order_ids[i],
            "current_mode": X.iloc[i]["Shipping_Mode"],
            "lowest_late_risk_mode": modes[best[i]],
            "probability_late_by_mode": {m: round(float(probs[i, k]), 4) for k, m in enumerate(modes)},
        })
    counts = pd.Series([modes[b] for b in best]).value_counts().to_dict()
    return {
        "summary": {"orders_scored": len(X), "lowest_late_risk_mode_counts": counts,
                    "promised_days_by_mode": scheduled},
        "orders": orders,
        "caveat": ("What-if comparison from a correlational model; 'late' is relative to each mode's own "
                   "promised shipping days, so the least-risky mode is often the slowest."),
    }
