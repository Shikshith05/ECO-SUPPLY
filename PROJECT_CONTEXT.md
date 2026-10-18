# epoch — Project Context

Handoff document: what the system does, how data flows, where each number
comes from, and the rules the code follows. Results live in `results/`; the
README copies its tables from there.

---

## 1. What this project is

A Flask app with three portals on top of the public **DataCo "Smart Supply
Chain for Big Data Analysis"** dataset (180,519 order-item rows, 2015-01 to
2018-01) plus a Bangalore road network:

| Portal | Question it answers | Method |
|---|---|---|
| Producer | Where is demand, and where is it unprofitable? | Descriptive analytics + KMeans demand segments (k by silhouette) |
| Consumer | Will this new order ship later than promised, and why? | XGBoost on order-time features only, time-based evaluation, TreeSHAP reasons |
| Fleet Optimizer | How should K capacity-limited vehicles serve these stops from a depot? | CVRP: greedy, genetic algorithm (giant tour + Prins split), OR-Tools; OSM road distances |

Ground rules: no hard-coded or "estimated" metrics; every reported number is
produced by a script into `results/`; estimates (fuel/CO2) are labelled as
estimates; nothing that is a rule is called a model.

---

## 2. Repository layout

```
backend/
  app.py                    Flask app, blueprints, /api/health (reports trained artifacts), graph warm-up
  config.py                 loads config.yaml deep-merged over config.yaml.example
  routes/
    prediction_routes.py    /api/predict/*   (producer + consumer)
    recommendation_routes.py /api/recommend/* (CSV shipping what-if, weather, news)
    routing_routes.py       /api/route/*     (fleet optimizer)
  services/
    road_network.py         OSM graph cache (GraphML -> .npz), KD-tree snapping, multi-source Dijkstra
    route_optimizer.py      request parsing, distance matrix + fallback, solver dispatch, comparisons, estimates
    weather_service.py      OpenWeatherMap; static sample data labelled source='mock' without a key
    news_service.py         NewsAPI; same convention
  utils/
    preprocessing.py        CSV loading, column-name normalisation, numeric_column()
    feature_engineering.py  descriptive producer features + rule-based composite score
models/
  routing_models/
    cvrp.py                 instance/solution types, validation, Prins split, 2-opt, relocate
    greedy.py               capacity-aware nearest neighbour; order-as-received baseline
    genetic_algorithm.py    GA (giant tour, split decoding, tournament, OX, swap/inversion, LS, elitism)
    ortools_solver.py       OR-Tools routing with capacity dimension, GLS
  consumer_models/
    delay_model.py          feature lists, BANNED_COLUMNS + assert_no_leakage, pipeline factory, inference, SHAP
    consumer_insights.py    new-order response: prediction, mode what-if, labelled history
    shipping_recommendation.py  CSV what-if over shipping modes
  producer_models/
    demand_segments.py      product x city aggregation, KMeans inference, centroid-based names
    demand_clustering.py    producer endpoints: segment + descriptive analytics
scripts/
  download_osm_graph.py     one-time graph download + detour-factor measurement
  train_delay_model.py      trains/evaluates the delay model -> saved_models/, results/
  train_demand_clusters.py  trains KMeans -> saved_models/, results/
  benchmark_routing.py      GA tuning + routing benchmark -> results/
frontend/                   index.html, producer.html, consumer.html, fleet.html, styles.css, app.js
tests/                      pytest suite (offline: network blocked, graph loader faked)
results/                    generated metrics (committed)
saved_models/, data/        generated / downloaded artifacts (gitignored)
docs/CHANGELOG_NOTES.md     what changed and why, per task
```

---

## 3. Data

* `data/raw/DataCoSupplyChainDataset.csv` (latin-1). Gitignored. Column
  names are normalised by `preprocessing.load_and_clean_csv` (e.g. "Days for
  shipping (real)" → `Days_for_shipping_real`); PII columns are dropped.
* Each row is an order **item**; items of one order share the order date and
  the label.
* `Late_delivery_risk` = 1 when `Days_for_shipping_real > Days_for_shipment_scheduled`.
  The promised days are fixed per mode: Same Day 0, First Class 1, Second
  Class 2, Standard Class 4.
* Structure that matters for modelling (measured on the test split): First
  Class shipped orders are 100 % late; Same Day orders are late exactly when
  placed at or after 12:00; Second/Standard Class late rates (~80 % / ~39 %)
  do not depend on the available features.
* Canceled orders (`Delivery_Status == "Shipping canceled"`, = Order_Status
  CANCELED or SUSPECTED_FRAUD, 7,754 rows) have label 0 but never shipped;
  the delay model excludes them.
* Road network: OSMnx drive graph for "Bangalore, India", largest strongly
  connected component, 155,442 nodes / 392,843 directed edges, stored under
  `data/external/osm/` (gitignored).
* CVRPLIB Augerat set A instances are downloaded by the benchmark into
  `data/external/cvrplib/` (gitignored); best-known costs are read from the
  `.sol` files.

---

## 4. Consumer portal: late-delivery model

* **Leakage rule**: features must be known when the order is placed.
  `delay_model.BANNED_COLUMNS` = {Late_delivery_risk, Delivery_Status,
  Days_for_shipping_real, Order_Status, Shipping_Date, shipping_delay_gap};
  `assert_no_leakage()` runs at import, in training, and in tests (also on
  names derived from banned columns).
* **Features**: Shipping_Mode, Type (payment), Customer_Segment,
  Department/Category/Product name, Market, Order_Region, Order_Country,
  Days_for_shipment_scheduled, Product_Price, Order_Item_Quantity,
  Order_Item_Discount_Rate, Sales, order month/day-of-week/day/hour.
* **Evaluation**: chronological 70/10/20 split; F1 threshold chosen on
  validation; baselines = majority class, shipping-mode lookup, logistic
  regression; XGBoost with early stopping. Metrics, per-mode AUC and the
  calibration curve: `results/delay_model_metrics.json`,
  `results/delay_model_calibration.png`.
* **Inference** (`POST /api/predict/consumer`): builds one feature row for a
  hypothetical order from lookups saved with the model (product → category,
  department, median price; country → region, market; mode → promised days),
  returns probability, threshold, top-5 SHAP reasons (XGBoost
  `pred_contribs`, same trees as `predict_proba`), the same order under every
  shipping mode, descriptive history, and the model-quality note.
* External weather/news signals are attached only when the services return
  live data (real API keys).

## 5. Producer portal

* **Demand segments**: per (Product_Name, Order_City) pair, features
  log1p(total sales), log1p(total quantity), profit margin; StandardScaler;
  KMeans k = 2..8 chosen by silhouette (10k-pair sample). Names derived from
  centroids (sign of standardised log sales; sign of mean margin). Metrics:
  `results/demand_clustering_metrics.json`.
* **Descriptive analytics**: region × category quantity heatmap;
  "high demand · low profit" = regions with below-median average profit per
  order ranked by quantity; rule-based composite score (weights in
  `config.yaml`, labelled as rule-based).

## 6. Fleet Optimizer

* **Problem**: CVRP. Depot = node 0; integer demands; identical capacity;
  at most K routes; every route depot → … → depot.
* **Request**: `stops` (lat, lng, optional demand/order_id), optional
  `depot` (default first stop), `vehicle_count`, `capacity` (default
  ceil(total demand / K)), `time_limit_s`, `seed`. Legacy `weights` accepted
  and ignored (noted in the response).
* **Distances**: road network if the cached graph is present and every point
  snaps within `max_snap_km`; otherwise haversine × `haversine_detour_factor`
  (median road/straight-line ratio measured on the graph,
  `results/osm_detour_factor.json`). The response reports `distance_mode`
  and the reason. The graph is never downloaded during a request.
* **Solvers**: `/api/route/estimate` → greedy; `/api/route/optimize` → GA;
  `?solver=ortools` → OR-Tools. All share `solve(instance, seed, time_limit)`.
* **Comparisons**: every response includes greedy and order-as-received
  routes on the same matrix and the km / % saved against each.
* **Estimates**: fuel L = km × `fuel_litres_per_km`; CO2 kg = L ×
  `co2_kg_per_litre` (config), labelled as estimates; fuel cost only if a
  price is configured.
* **GA hyperparameters** come from `config.yaml routing.ga_params`, set from
  `results/ga_tuned_params.json` (tuned on seeds disjoint from evaluation).
* **Benchmark**: `results/routing_benchmark.csv`, `routing_benchmark.md`,
  `routing_benchmark_summary.json`.

---

## 7. API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | status + which trained artifacts exist |
| GET | `/api/predict/options/products` · `cities` · `pincodes` | dropdown values from the dataset |
| GET | `/api/predict/options/destinations` · `shipping-modes` | values known to the delay model |
| GET | `/api/predict/producer-overview` | heatmap, low-profit regions, rule-based region scores, KMeans segments |
| POST | `/api/predict/demand` | `{product, city}` → segment + descriptive context |
| POST | `/api/predict/consumer` | `{product, destination, shipping_mode, quantity?, order_datetime?}` → late-delivery prediction |
| POST | `/api/recommend/shipping` | CSV upload → per-order shipping-mode what-if |
| GET | `/api/recommend/weather` · `news` | external context (`source` = live or mock) |
| POST | `/api/route/estimate` | greedy CVRP |
| POST | `/api/route/optimize[?solver=ga\|ortools\|greedy]` | CVRP with the chosen solver |
| GET | `/api/route/graph/status` | road-graph cache status (never downloads) |

Invalid input returns HTTP 400 with a message; a missing trained model
returns 503 with the command that creates it.

---

## 8. Conventions

* Imports are package-absolute from the repo root (`backend.*`, `models.*`);
  `pytest.ini` sets `pythonpath = .`.
* Config defaults live only in `config/config.yaml.example`; `config.yaml`
  overrides them (deep merge).
* DataFrame columns that may be missing are read with
  `preprocessing.numeric_column(df, col, default)`, never
  `pd.to_numeric(df.get(col, 0))`.
* Tests never use the network (sockets blocked in `tests/conftest.py`) and
  never load the real road graph; road mode is tested with a synthetic grid.
* Trained artifacts are rebuilt by scripts; `results/` holds the only
  numbers allowed in docs.

## 9. Running

```bash
python setup_env.py                                   # .venv (Python 3.11) + requirements + config
.venv\Scripts\python scripts/download_osm_graph.py    # once, optional (fallback distances without it)
.venv\Scripts\python scripts/train_delay_model.py
.venv\Scripts\python scripts/train_demand_clusters.py
python start_app.py                                   # http://localhost:5000
.venv\Scripts\python -m pytest
.venv\Scripts\python scripts/benchmark_routing.py     # ~1.5-2 h
```
