"""
epoch/backend/utils/feature_engineering.py
--------------------------------------------
Shared feature construction functions used across all models.
Each function accepts a clean DataFrame (from preprocessing.py)
and returns a DataFrame with additional engineered columns.
"""

import pandas as pd
import numpy as np

from backend.utils.preprocessing import normalise_0_1, numeric_column


def add_shipping_delay_feature(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute actual vs scheduled shipping gap.
    Positive = late, Negative = early, 0 = on time.

    Descriptive analytics only: this is known after delivery, so it must never
    feed a predictive model (it is in delay_model.BANNED_COLUMNS).
    """
    if "Days_for_shipping_real" in df.columns and "Days_for_shipment_scheduled" in df.columns:
        df["shipping_delay_gap"] = (
            df["Days_for_shipping_real"] - df["Days_for_shipment_scheduled"]
        )
    return df


def add_profit_margin_feature(df: pd.DataFrame) -> pd.DataFrame:
    """Profit margin = profit / sales (per order)."""
    if "Order_Profit_Per_Order" in df.columns and "Sales" in df.columns:
        df["profit_margin"] = df["Order_Profit_Per_Order"] / df["Sales"].replace(0, np.nan)
        df["profit_margin"] = df["profit_margin"].fillna(0)
    return df


def add_discount_impact_feature(df: pd.DataFrame) -> pd.DataFrame:
    """Flag high-discount orders (>15%) that may signal demand stimulation."""
    if "Order_Item_Discount_Rate" in df.columns:
        df["high_discount_flag"] = (df["Order_Item_Discount_Rate"] > 0.15).astype(int)
    return df


def add_demand_score(df: pd.DataFrame) -> pd.Series:
    """
    Rule-based composite score (0–1) per row: a weighted sum of min-max
    normalised sales, quantity, profit and on-time rate. Weights come from
    config.yaml (model.demand_score_weights). Used only as a descriptive
    ranking aid in the producer overview; it is not a trained model.
    """
    from backend.config import load_config

    w = (load_config().get("model") or {}).get("demand_score_weights") or {}
    sales_norm  = normalise_0_1(numeric_column(df, "Sales"))
    qty_norm    = normalise_0_1(numeric_column(df, "Order_Item_Quantity"))
    profit_norm = normalise_0_1(numeric_column(df, "Order_Profit_Per_Order"))
    risk_inv    = 1 - normalise_0_1(numeric_column(df, "Late_delivery_risk"))

    score = (
        sales_norm  * float(w["sales"]) +
        qty_norm    * float(w["quantity"]) +
        profit_norm * float(w["profit"]) +
        risk_inv    * float(w["risk_inv"])
    )
    return score.rename("demand_score")


def add_temporal_features(df: pd.DataFrame) -> pd.DataFrame:
    """Extract month, quarter, day-of-week from order date."""
    if "Order_Date" in df.columns:
        dt = pd.to_datetime(df["Order_Date"], errors="coerce")
        df["order_month"]   = dt.dt.month
        df["order_quarter"] = dt.dt.quarter
        df["order_dow"]     = dt.dt.dayofweek   # 0=Mon, 6=Sun
    return df


def build_producer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Full feature pipeline for the producer-side demand clustering model."""
    df = add_shipping_delay_feature(df)
    df = add_profit_margin_feature(df)
    df = add_discount_impact_feature(df)
    df = add_temporal_features(df)
    df["demand_score"] = add_demand_score(df)
    return df
