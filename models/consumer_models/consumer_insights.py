"""
epoch/models/consumer_models/consumer_insights.py
--------------------------------------------------
Consumer-side insight for a hypothetical NEW order.

Input  : product, destination country, shipping mode (+ optional quantity,
         order time, customer segment, payment type)
Output : - prediction: the trained late-delivery model's probability for this
           order, top SHAP reasons, and the same order under every shipping mode
         - history: what actually happened to past shipped orders of this
           product to this destination. These are descriptive statistics,
           clearly labelled, and never used as the prediction.

The model is trained by scripts/train_delay_model.py; see
models/consumer_models/delay_model.py for the leakage rules.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from models.consumer_models import delay_model
from models.consumer_models.country_names import resolve, to_english


def _historical_context(df: pd.DataFrame, product: str, destination: str, shipping_mode: str) -> dict:
    shipped = df
    if "Delivery_Status" in df.columns:
        shipped = df[df["Delivery_Status"].astype(str).str.strip() != "Shipping canceled"]
    same = shipped[(shipped["Product_Name"] == product) & (shipped["Order_Country"] == destination)]
    same_mode = same[same["Shipping_Mode"] == shipping_mode]

    def summary(rows: pd.DataFrame) -> dict:
        if rows.empty:
            return {"orders": 0, "late_rate": None, "avg_actual_shipping_days": None,
                    "avg_scheduled_shipping_days": None}
        return {
            "orders": int(len(rows)),
            "late_rate": round(float(rows["Late_delivery_risk"].mean()), 3),
            "avg_actual_shipping_days": round(float(rows["Days_for_shipping_real"].mean()), 2),
            "avg_scheduled_shipping_days": round(float(rows["Days_for_shipment_scheduled"].mean()), 2),
        }

    return {
        "label": "Historical outcomes of past shipped orders (descriptive, not a prediction)",
        "product_to_destination_all_modes": summary(same),
        "product_to_destination_same_mode": summary(same_mode),
    }


def _shipping_comparison(by_mode: dict, scheduled_days: dict) -> dict:
    rows = sorted(
        ({"shipping_mode": m, "promised_days": scheduled_days.get(m), "probability_late": p}
         for m, p in by_mode.items()),
        key=lambda r: r["probability_late"],
    )
    best = rows[0]
    return {
        "lowest_late_risk_mode": best["shipping_mode"],
        "modes": rows,
        "reason": (
            f"{best['shipping_mode']} has the lowest predicted probability ({best['probability_late']:.0%}) of "
            f"missing its promised {best['promised_days']:g}-day shipping time for this order. 'Late' is relative "
            "to each mode's own promise, so the least-risky mode is not necessarily the fastest."
        ),
        "caveat": ("What-if comparison: the same order is re-scored with each shipping mode. The model learned "
                   "associations from historical data; it is not a causal estimate."),
    }


def predict_new_order(df: pd.DataFrame, product: str, destination: str, shipping_mode: str,
                      quantity: int = 1, order_datetime: Optional[datetime] = None,
                      customer_segment: Optional[str] = None, payment_type: Optional[str] = None) -> dict:
    destination = resolve(destination, delay_model.load_bundle()["lookups"]["countries"])
    pred = delay_model.predict_new_order(
        product, destination, shipping_mode,
        quantity=quantity, order_datetime=order_datetime,
        customer_segment=customer_segment, payment_type=payment_type,
    )
    bundle = delay_model.load_bundle()
    lookups = bundle["lookups"]
    country = lookups["countries"][destination]
    return {
        "product": product,
        "destination": to_english(destination),
        "destination_dataset_value": destination,
        "granularity": ("Destination is modelled at country level (Order_Country, with its region and market); "
                        "the model has no city- or address-level information."),
        "shipping_mode": shipping_mode,
        "context": {"region": country["Order_Region"], "market": country["Market"], "country": to_english(destination)},
        "prediction": pred,
        "shipping": _shipping_comparison(pred["probability_by_shipping_mode"], lookups["scheduled_days"]),
        "history": _historical_context(df, product, destination, shipping_mode),
        "model_quality": _model_quality(bundle),
    }


def _model_quality(bundle: dict) -> dict:
    meta = bundle["metadata"]
    return {
        "test_roc_auc": meta["test_metrics"]["roc_auc"],
        "test_pr_auc": meta["test_metrics"]["pr_auc"],
        "test_period": f"{meta['split']['test']['from'][:10]} to {meta['split']['test']['to'][:10]}",
        "note": meta.get("quality_note"),
    }
