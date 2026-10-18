"""
Train the producer demand-segment model (KMeans, k chosen by silhouette).

    .venv\\Scripts\\python scripts/train_demand_clusters.py [--csv data/raw/DataCoSupplyChainDataset.csv]

Outputs
  saved_models/demand_kmeans.joblib         (gitignored) scaler + KMeans + names + profiles
  results/demand_clustering_metrics.json    silhouette per k, chosen k, cluster profiles
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.utils.preprocessing import load_and_clean_csv  # noqa: E402
from models.producer_models.demand_segments import FEATURE_NAMES, MODEL_PATH, aggregate_pairs, name_clusters  # noqa: E402

SEED = 42
K_RANGE = range(2, 9)
SILHOUETTE_SAMPLE = 10_000   # silhouette is O(n^2); score on a fixed random sample


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join(ROOT, "data", "raw", "DataCoSupplyChainDataset.csv"))
    args = ap.parse_args()

    import joblib
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    from sklearn.preprocessing import StandardScaler

    df = load_and_clean_csv(args.csv)
    pairs = aggregate_pairs(df)
    scaler = StandardScaler().fit(pairs[FEATURE_NAMES])
    X = scaler.transform(pairs[FEATURE_NAMES])
    print(f"{len(pairs)} product x city pairs")

    scores, models = {}, {}
    for k in K_RANGE:
        km = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(X)
        scores[k] = float(silhouette_score(X, km.labels_, sample_size=min(SILHOUETTE_SAMPLE, len(X)),
                                           random_state=SEED))
        models[k] = km
        print(f"k={k}: silhouette {scores[k]:.4f}, inertia {km.inertia_:.0f}")
    best_k = max(scores, key=scores.get)
    km = models[best_k]
    pairs["cluster"] = km.labels_

    prof = pairs.groupby("cluster").agg(
        pairs=("cluster", "size"), mean_total_sales=("total_sales", "mean"),
        median_total_sales=("total_sales", "median"), mean_total_quantity=("total_quantity", "mean"),
        mean_profit_margin=("profit_margin", "mean"), mean_orders=("orders", "mean"))
    names = name_clusters(km.cluster_centers_, prof["mean_profit_margin"].to_dict())
    profiles = []
    for c, row in prof.sort_values("mean_total_sales", ascending=False).iterrows():
        examples = (pairs[pairs["cluster"] == c].sort_values("total_sales", ascending=False)
                    .head(3)[["Product_Name", "Order_City"]].values.tolist())
        profiles.append({
            "cluster_id": int(c), "name": names[int(c)], "pairs": int(row["pairs"]),
            "share_of_pairs": round(float(row["pairs"]) / len(pairs), 4),
            "mean_total_sales": round(float(row["mean_total_sales"]), 2),
            "median_total_sales": round(float(row["median_total_sales"]), 2),
            "mean_total_quantity": round(float(row["mean_total_quantity"]), 2),
            "mean_profit_margin": round(float(row["mean_profit_margin"]), 4),
            "mean_orders": round(float(row["mean_orders"]), 2),
            "centroid_z": {f: round(float(v), 3) for f, v in zip(FEATURE_NAMES, km.cluster_centers_[int(c)])},
            "example_pairs": examples,
        })

    trained_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    bundle = {"scaler": scaler, "kmeans": km, "k": best_k, "silhouette": scores[best_k], "names": names,
              "profiles": profiles, "n_pairs": int(len(pairs)), "features": FEATURE_NAMES, "trained_at": trained_at}
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(bundle, MODEL_PATH)

    report = {
        "generated_at": trained_at, "dataset": os.path.basename(args.csv),
        "unit": "one row per (Product_Name, Order_City) pair",
        "features": FEATURE_NAMES, "scaling": "StandardScaler (z-scores)",
        "n_pairs": int(len(pairs)), "silhouette_by_k": {str(k): round(v, 4) for k, v in scores.items()},
        "silhouette_sample_size": min(SILHOUETTE_SAMPLE, len(X)),
        "chosen_k": best_k, "chosen_silhouette": round(scores[best_k], 4),
        "inertia_by_k": {str(k): round(float(m.inertia_), 1) for k, m in models.items()},
        "segments": profiles,
    }
    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    with open(os.path.join(ROOT, "results", "demand_clustering_metrics.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"chosen k={best_k} (silhouette {scores[best_k]:.4f}); saved {MODEL_PATH}")
    print(json.dumps(profiles, indent=1))


if __name__ == "__main__":
    main()
