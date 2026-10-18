"""Producer demand segments (KMeans) and descriptive producer analytics."""

import numpy as np
import pandas as pd
import pytest

from models.producer_models import demand_clustering, demand_segments
from models.producer_models.demand_segments import FEATURE_NAMES, aggregate_pairs, name_clusters


def orders(n=400, seed=0):
    rng = np.random.default_rng(seed)
    product = rng.choice(np.array(["Widget", "Gadget", "Gizmo"]), n)
    city = rng.choice(np.array(["Paris", "Lagos", "Lima", "Pune"]), n)
    qty = rng.integers(1, 6, n)
    price = np.where(product == "Widget", 300.0, 40.0)
    sales = price * qty
    margin = np.where(product == "Gizmo", -0.5, 0.2)
    return pd.DataFrame({
        "Product_Name": product, "Order_City": city, "Order_Item_Quantity": qty, "Sales": sales,
        "Order_Profit_Per_Order": sales * margin,
        "Order_Region": np.where(city == "Paris", "Western Europe", np.where(city == "Lagos", "West Africa", "South America")),
        "Category_Name": np.where(product == "Widget", "Tools", "Toys"),
        "Market": "Europe", "Late_delivery_risk": rng.integers(0, 2, n),
    })


def test_aggregate_pairs_one_row_per_product_city():
    df = orders()
    pairs = aggregate_pairs(df)
    assert len(pairs) == df.groupby(["Product_Name", "Order_City"]).ngroups
    assert set(FEATURE_NAMES) <= set(pairs.columns)
    assert pairs["profit_margin"].between(-1, 1).all()
    row = pairs[(pairs.Product_Name == "Widget") & (pairs.Order_City == "Paris")].iloc[0]
    assert row["total_sales"] == pytest.approx(df[(df.Product_Name == "Widget") & (df.Order_City == "Paris")]["Sales"].sum())


def test_cluster_names_come_from_centroids():
    centroids = np.array([[1.2, 1.1, 0.1], [-0.4, -0.3, -2.0], [-0.5, -0.6, 0.4]])
    names = name_clusters(centroids, {0: 0.12, 1: -0.5, 2: 0.23})
    assert names == {0: "Above-average demand · profitable",
                     1: "Below-average demand · loss-making",
                     2: "Below-average demand · profitable"}
    dup = name_clusters(np.array([[1.0, 0, 0], [2.0, 0, 0]]), {0: 0.1, 1: 0.1})
    assert len(set(dup.values())) == 2


@pytest.fixture
def kmeans_bundle(monkeypatch):
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    pairs = aggregate_pairs(orders())
    scaler = StandardScaler().fit(pairs[FEATURE_NAMES])
    km = KMeans(n_clusters=2, n_init=5, random_state=0).fit(scaler.transform(pairs[FEATURE_NAMES]))
    names = name_clusters(km.cluster_centers_, {0: 0.1, 1: 0.1})
    bundle = {"scaler": scaler, "kmeans": km, "k": 2, "silhouette": 0.5, "names": names,
              "profiles": [{"name": n} for n in names.values()], "n_pairs": len(pairs), "trained_at": "test"}
    monkeypatch.setattr(demand_segments, "_BUNDLE", bundle)
    return bundle


def test_assign_segment(kmeans_bundle):
    out = demand_segments.assign_segment(orders(), "widget", "PARIS")
    assert out["segment"] in kmeans_bundle["names"].values()
    assert "KMeans" in out["method"]
    assert demand_segments.assign_segment(orders(), "Widget", "Atlantis")["segment"] is None


def test_high_demand_low_profit_only_lists_below_median_profit_regions():
    rows = demand_clustering._high_demand_low_profit(orders())
    assert rows
    assert all(r["avg_profit_per_order"] < r["median_region_avg_profit"] for r in rows)
    quantities = [r["total_quantity"] for r in rows]
    assert quantities == sorted(quantities, reverse=True)


def test_producer_overview_endpoint(kmeans_bundle, monkeypatch):
    from backend.app import app
    from backend.routes import prediction_routes

    monkeypatch.setattr(prediction_routes, "_get_dataset", lambda: orders())
    data = app.test_client().get("/api/predict/producer-overview").get_json()
    assert data["heatmap"]["rows"]
    assert data["demand_segments"]["segments"]
    assert "Rule-based" in data["rule_based_score_method"]
    demand = app.test_client().post("/api/predict/demand", json={"product": "Widget", "city": "Paris"}).get_json()
    assert demand["demand_segment"]["segment"] in kmeans_bundle["names"].values()
