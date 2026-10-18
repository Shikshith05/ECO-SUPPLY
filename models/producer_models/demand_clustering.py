"""
epoch/models/producer_models/demand_clustering.py
--------------------------------------------------
Producer-side demand insights.

Two kinds of output, labelled as such in every response:
  * Demand SEGMENT of a product-city pair: a trained KMeans model on
    standardised sales / quantity / profit-margin aggregates
    (see demand_segments.py and scripts/train_demand_clusters.py).
  * Descriptive analytics: region x category heatmap, high-demand /
    low-profit regions, and a rule-based composite score per region
    (weighted min-max of sales, quantity, profit and on-time rate; weights in
    config.yaml under model.demand_score_weights). The rule-based score is a
    ranking aid, not a model.
"""

import pandas as pd

from backend.utils.feature_engineering import build_producer_features
from models.producer_models import demand_segments

SCORE_METHOD = ("Rule-based composite score: weighted min-max of sales, quantity, profit and on-time rate "
                "(weights in config.yaml, model.demand_score_weights); tiers are thirds of the regions compared.")


def _score_tier(score: float, low_thresh: float, high_thresh: float) -> str:
    """Which third of the compared regions a rule-based score falls in."""
    if score >= high_thresh:
        return "Top third"
    if score >= low_thresh:
        return "Middle third"
    return "Bottom third"


def _region_score_rows(feat_df: pd.DataFrame, limit: int) -> list:
    region_agg = feat_df.groupby("Order_Region", as_index=False).agg(
        rule_based_score=("demand_score", "mean"),
        total_sales=("Sales", "sum") if "Sales" in feat_df.columns else ("demand_score", "count"),
        order_count=("demand_score", "count"),
    ).sort_values("rule_based_score", ascending=False)
    scores = region_agg["rule_based_score"]
    low_t = float(scores.quantile(1 / 3)) if len(scores) >= 3 else float(scores.min())
    high_t = float(scores.quantile(2 / 3)) if len(scores) >= 3 else float(scores.max())
    rows = []
    for _, row in region_agg.head(limit).iterrows():
        rows.append({
            "region": row["Order_Region"],
            "rule_based_score": round(float(row["rule_based_score"]), 3),
            "score_tier": _score_tier(row["rule_based_score"], low_t, high_t),
            "total_sales": round(float(row["total_sales"]), 2),
            "order_count": int(row["order_count"]),
        })
    return rows


def _get_top_regions_for_product(df: pd.DataFrame, product_col: str, product: str) -> list:
    """Top 5 regions by rule-based score for the given product (scores normalised across that product's rows)."""
    prod_df = df[df[product_col].astype(str).str.lower() == product.lower()]
    if prod_df.empty or "Order_Region" not in prod_df.columns:
        return []
    return _region_score_rows(build_producer_features(prod_df.copy()), limit=5)


def _heatmap(frame: pd.DataFrame) -> dict:
    """rows = regions, columns = categories, values = order quantity sum (top 10 x top 10)."""
    empty = {"rows": [], "columns": [], "values": []}
    if frame.empty or not {"Order_Region", "Category_Name", "Order_Item_Quantity"} <= set(frame.columns):
        return empty
    pivot = frame.pivot_table(values="Order_Item_Quantity", index="Order_Region", columns="Category_Name",
                              aggfunc="sum", fill_value=0).sort_index()
    if pivot.empty:
        return empty
    pivot = pivot[pivot.sum(axis=0).sort_values(ascending=False).head(10).index.tolist()]
    pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).head(10).index.tolist()]
    return {
        "rows": [str(r) for r in pivot.index.tolist()],
        "columns": [str(c) for c in pivot.columns.tolist()],
        "values": [[float(v) for v in row] for row in pivot.values.tolist()],
    }


def _high_demand_low_profit(frame: pd.DataFrame, limit: int = 10) -> list:
    """
    Regions whose average profit per order is BELOW the median region's, ranked
    by total quantity. (The previous version sorted by quantity first and profit
    second, which in practice was just a quantity ranking.)
    """
    needed = {"Order_Region", "Order_Item_Quantity", "Order_Profit_Per_Order"}
    if frame.empty or not needed <= set(frame.columns):
        return []
    sales_col = "Sales" if "Sales" in frame.columns else "Order_Item_Quantity"
    grouped = frame.groupby("Order_Region", as_index=False).agg(
        total_quantity=("Order_Item_Quantity", "sum"),
        avg_profit_per_order=("Order_Profit_Per_Order", "mean"),
        total_sales=(sales_col, "sum"),
        order_count=("Order_Item_Quantity", "count"),
    )
    if grouped.empty:
        return []
    median_profit = float(grouped["avg_profit_per_order"].median())
    low_profit = grouped[grouped["avg_profit_per_order"] < median_profit]
    low_profit = low_profit.sort_values("total_quantity", ascending=False).head(limit)
    return [{
        "rank": rank,
        "region": str(row["Order_Region"]),
        "total_quantity": int(row["total_quantity"]),
        "avg_profit_per_order": round(float(row["avg_profit_per_order"]), 2),
        "total_sales": round(float(row["total_sales"]), 2),
        "order_count": int(row["order_count"]),
        "median_region_avg_profit": round(median_profit, 2),
    } for rank, (_, row) in enumerate(low_profit.iterrows(), start=1)]


# ── Main entry points ─────────────────────────────────────────────────────────

def predict_for_product_city(df: pd.DataFrame, product: str, city: str) -> dict:
    """Demand segment (KMeans) + descriptive context for one product and destination city."""
    product_col = next((c for c in ["Product_Name", "Category_Name"] if c in df.columns), None)
    if not product_col:
        raise ValueError("No product name column found in dataset.")
    city_col = next((c for c in ["Order_City", "Customer_City"] if c in df.columns), None)
    if not city_col:
        raise ValueError("No city column found in dataset.")

    prod_df = df[df[product_col].astype(str).str.lower() == product.lower()]
    subset = prod_df[prod_df[city_col].astype(str).str.lower() == city.lower()]
    found = not subset.empty
    if prod_df.empty:
        return {"found": False, "product": product, "city": city, "segment": None, "order_count": 0,
                "message": "No data found for this product."}

    segment = demand_segments.assign_segment(df, product, city) if found else {
        "segment": None, "reason": "No historical orders for this product and city."}
    context = subset if found else prod_df
    total_sales = float(context["Sales"].sum()) if "Sales" in context.columns else 0.0
    avg_profit = float(context["Order_Profit_Per_Order"].mean()) if "Order_Profit_Per_Order" in context.columns else 0.0
    late_rate = float(context["Late_delivery_risk"].mean()) if "Late_delivery_risk" in context.columns else None

    def mode_of(col):
        return str(context[col].mode().iloc[0]) if col in context.columns and not context[col].dropna().empty else "Unknown"

    return {
        "found": found,
        "product": product,
        "city": city,
        "demand_segment": segment,
        "market": mode_of("Market"),
        "region": mode_of("Order_Region"),
        "historical": {
            "label": "Descriptive statistics of past orders" + ("" if found else " (product-level: no orders to this city)"),
            "total_sales": round(total_sales, 2),
            "avg_profit_per_order": round(avg_profit, 2),
            "late_shipment_rate": round(late_rate, 3) if late_rate is not None else None,
            "order_count": int(len(context)),
        },
        "top_regions_rule_based": _get_top_regions_for_product(df, product_col, product),
        "rule_based_score_method": SCORE_METHOD,
        "heatmap": _heatmap(prod_df),
        "high_demand_low_profit_top10": _high_demand_low_profit(prod_df),
        "data_source": "city-matched" if found else "product-only",
        "message": None if found else f"No exact city match: showing product-level data for '{product}'.",
    }


def predict_overview(df: pd.DataFrame) -> dict:
    """Producer overview for the full dataset (no product/city inputs)."""
    try:
        segments = demand_segments.segment_overview()
    except FileNotFoundError as exc:
        segments = {"warning": str(exc), "segments": []}
    top_regions = _region_score_rows(build_producer_features(df.copy()), limit=10) if "Order_Region" in df.columns else []
    return {
        "heatmap": _heatmap(df),
        "high_demand_low_profit_top10": _high_demand_low_profit(df),
        "top_regions_rule_based": top_regions,
        "rule_based_score_method": SCORE_METHOD,
        "demand_segments": segments,
    }
