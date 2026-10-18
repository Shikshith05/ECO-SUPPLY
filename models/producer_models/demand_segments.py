"""
Producer demand segments: KMeans on product x destination-city aggregates.

One row per (Product_Name, Order_City) pair, with three features:
  * log1p(total sales)     : revenue volume (log, because sales are heavily skewed)
  * log1p(total quantity)  : unit volume
  * profit margin          : total profit / total sales, clipped to [-1, 1]
Features are standardised (z-scores) so no single unit dominates the Euclidean
distance, then KMeans is fitted for k = 2..8 and the k with the highest
silhouette score is kept. Trained by scripts/train_demand_clusters.py.

Cluster names are derived from the centroids, not hand-assigned: "above" or
"below-average demand" from the sign of the standardised log-sales
coordinate, and "profitable" or "loss-making" from the sign of the cluster's
mean profit margin.
"""

from __future__ import annotations

import os
from typing import Dict, List

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_PATH = os.path.join(ROOT, "saved_models", "demand_kmeans.joblib")
FEATURE_NAMES = ["log_total_sales", "log_total_quantity", "profit_margin"]

_BUNDLE = None


def aggregate_pairs(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate orders to one row per (product, destination city)."""
    g = (df.groupby(["Product_Name", "Order_City"], as_index=False)
           .agg(total_sales=("Sales", "sum"), total_quantity=("Order_Item_Quantity", "sum"),
                total_profit=("Order_Profit_Per_Order", "sum"), orders=("Sales", "size")))
    g["log_total_sales"] = np.log1p(g["total_sales"].clip(lower=0))
    g["log_total_quantity"] = np.log1p(g["total_quantity"].clip(lower=0))
    g["profit_margin"] = (g["total_profit"] / g["total_sales"].replace(0, np.nan)).fillna(0).clip(-1, 1)
    return g


def name_clusters(centroids_z: np.ndarray, mean_margin: Dict[int, float]) -> Dict[int, str]:
    """
    Describe each cluster by its centroid: the standardised log-sales coordinate
    (> 0 means above the average pair) and the sign of its mean profit margin.
    If two clusters would get the same name, they are numbered by sales rank.
    """
    names = {}
    for c, z in enumerate(centroids_z):
        demand = "Above-average demand" if z[0] > 0 else "Below-average demand"
        margin = "loss-making" if mean_margin[c] < 0 else "profitable"
        names[c] = f"{demand} · {margin}"
    counts = {}
    for n in names.values():
        counts[n] = counts.get(n, 0) + 1
    for n, cnt in counts.items():
        if cnt > 1:
            dup = sorted((c for c in names if names[c] == n), key=lambda c: -centroids_z[c][0])
            for rank, c in enumerate(dup, start=1):
                names[c] = f"{n} ({rank})"
    return names


def load_bundle(path: str = MODEL_PATH):
    global _BUNDLE
    if _BUNDLE is None:
        if not os.path.exists(path):
            raise FileNotFoundError(
                "Demand segment model not trained yet: run `.venv\\Scripts\\python scripts/train_demand_clusters.py`."
            )
        import joblib

        _BUNDLE = joblib.load(path)
    return _BUNDLE


def assign_segment(df: pd.DataFrame, product: str, city: str) -> dict:
    """Segment of one product-city pair, computed from its aggregates in df."""
    bundle = load_bundle()
    rows = df[(df["Product_Name"].astype(str).str.lower() == product.lower())
              & (df["Order_City"].astype(str).str.lower() == city.lower())]
    if rows.empty:
        return {"segment": None, "reason": "No historical orders for this product and city."}
    pair = aggregate_pairs(rows).iloc[0]
    x = bundle["scaler"].transform(pd.DataFrame([pair[FEATURE_NAMES].astype(float)], columns=FEATURE_NAMES))
    cluster = int(bundle["kmeans"].predict(x)[0])
    return {
        "segment": bundle["names"][cluster],
        "cluster_id": cluster,
        "features": {"total_sales": round(float(pair["total_sales"]), 2),
                     "total_quantity": int(pair["total_quantity"]),
                     "profit_margin": round(float(pair["profit_margin"]), 4),
                     "orders": int(pair["orders"])},
        "method": f"KMeans, k={bundle['k']} chosen by silhouette ({bundle['silhouette']:.3f})",
    }


def segment_overview() -> dict:
    bundle = load_bundle()
    return {
        "method": f"KMeans on standardised product x city aggregates; k={bundle['k']} chosen by silhouette "
                  f"({bundle['silhouette']:.3f}) over k=2..8",
        "pairs": bundle["n_pairs"],
        "segments": bundle["profiles"],
        "trained_at": bundle["trained_at"],
    }
