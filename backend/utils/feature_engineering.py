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
    Composite demand score (0–1) per row based on Sales, Quantity, Profit.
    Used by demand_clustering.py as input features before clustering.
    Replace with model's own feature set once training is complete.
    """
    sales_norm  = normalise_0_1(numeric_column(df, "Sales"))
    qty_norm    = normalise_0_1(numeric_column(df, "Order_Item_Quantity"))
    profit_norm = normalise_0_1(numeric_column(df, "Order_Profit_Per_Order"))
    risk_inv    = 1 - normalise_0_1(numeric_column(df, "Late_delivery_risk"))

    score = (
        sales_norm  * 0.40 +
        qty_norm    * 0.30 +
        profit_norm * 0.20 +
        risk_inv    * 0.10
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


def add_route_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add shared route-planning features for new Fleet Optimizer models."""
    distance_km = numeric_column(df, "distance_km", 0.0)
    load_kg = numeric_column(df, "vehicle_load_kg", 40.0)
    speed_kph = numeric_column(df, "road_segment_speed_kph", 35.0)

    df["road_segment_speed_kph"] = speed_kph
    df["estimated_travel_time_min"] = (distance_km / speed_kph.replace(0, np.nan) * 60).fillna(0)
    df["fuel_burn_rate_l_per_km"] = 0.08 + 0.003 * (load_kg / 40.0)
    df["estimated_fuel_liters"] = distance_km * df["fuel_burn_rate_l_per_km"]
    return df


def build_producer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Full feature pipeline for the producer-side demand clustering model."""
    df = add_shipping_delay_feature(df)
    df = add_profit_margin_feature(df)
    df = add_discount_impact_feature(df)
    df = add_temporal_features(df)
    df = add_route_features(df)
    df["demand_score"] = add_demand_score(df)
    return df


def build_consumer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Full feature pipeline for the three consumer-side models."""
    df = add_shipping_delay_feature(df)
    df = add_profit_margin_feature(df)
    df = add_discount_impact_feature(df)
    df = add_temporal_features(df)
    df = add_route_features(df)
    return df
