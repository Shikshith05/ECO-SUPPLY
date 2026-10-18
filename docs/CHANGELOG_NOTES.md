# What changed and why

Short notes per task on the `fix/honest-ml-and-routing` branch, written to be
explainable in an interview. Numbers quoted here come from files under
`results/` or from the "before" baseline run recorded in Task 0.

## Task 0 — Baseline (before any change)

- `pytest` from the repo root failed at import (`ModuleNotFoundError: routes`);
  it only passed with `PYTHONPATH=backend`, and took 231 s because the
  graph-status test downloaded the Bangalore OSM graph over the network.
- Old "GA" vs greedy nearest-neighbour, straight-line km, 30 random Bangalore
  stop sets per size (mean): 10 stops 87.6 vs 76.7; 20 stops 195.2 vs 110.6;
  40 stops 441.1 vs 172.4. The "GA" was worse than greedy on 84 of 90 instances.
- "CO2 saved vs baseline" was always ~8 % of the reported CO2, because the
  baseline was defined as `result * 1.08`.
- Multi-vehicle was one tour cut into equal chunks with no depot, so on these
  instances 2 vehicles reported less distance than 1 (10 stops: 52.8 vs 63.0 km).

## Task 1 — Setup and reliability

**One virtual environment.** There were two (`.venv` from VS Code on Python
3.13, `venv` from `setup_env.py` on 3.11). The pinned pandas 2.2.2 / numpy
1.26.4 / scikit-learn 1.5.0 have no 3.13 wheels, so the only env that could
work was the 3.11 one. `setup_env.py` now builds `.venv` with Python 3.11
(using the `py -3.11` launcher on Windows if needed), refuses to reuse a
`.venv` built with another version unless `--recreate` is passed, installs
requirements, and copies `config.yaml.example` to `config.yaml`.
`start_app.py` and `.gitignore` point at `.venv`.

**Fresh clones no longer crash.** `config/config.yaml` is gitignored because
it can hold API keys, but nothing created it, so `app.py` crashed on a clean
clone. Config loading now lives in `backend/config.py`: it uses `config.yaml`
if present, otherwise the example. Placeholder keys such as
`YOUR_NEWSAPI_KEY_HERE` used to count as real keys, so every weather/news call
tried the network, failed, and still labelled the response "live". They now
count as "no key".

**Plain `pytest` works.** The app mixed three import roots (`routes.*`,
`utils.*`, `backend.utils.*`), so a module could be imported twice under
different names and tests needed `PYTHONPATH=backend`. All imports are now
package-absolute from the repo root (`backend.*`, `models.*`); `pytest.ini`
sets `pythonpath = .`; `backend/app.py` adds the repo root to `sys.path` when
run as a script.

**Tests are offline.** `tests/conftest.py` blocks every non-localhost socket
connection and replaces the OSM graph loader with an "unavailable" stub. The
suite went from 231 s to about 3 s. A detail worth knowing: the route module
did `from ... import load_bangalore_graph`, so patching only the service
module would not have been enough.

**The `df.get(col, 0)` bug pattern.** `pd.to_numeric(df.get("col", 0))`
returns a numpy scalar when the column is missing, and the next `.fillna()` or
`.clip()` crashes. A related form, `df.get(col, pd.Series([0]*len(df)))`, gives
a default with a RangeIndex that does not line up with a filtered DataFrame's
index, so values silently become NaN. Every occurrence now goes through one
helper, `numeric_column(df, col, default)`, which always returns a float
Series aligned to `df.index`. Unit tests cover missing columns, non-numeric
values and non-default indexes.

## Task 2 — A real capacitated vehicle routing solver (CVRP)

**Problem model.** One depot (node 0), N stops with integer demand, K
vehicles with the same capacity Q. Every route is depot → stops → depot, each
stop is visited exactly once, a route's load never exceeds Q, and at most K
routes are used. The old code cut one tour into equal chunks with no depot and
no return trip, which is why "2 vehicles" could beat "1 vehicle". With return
trips that is impossible: by the triangle inequality, splitting a tour never
shortens it. There is a test for this.

**API (backward compatible).** `stops` keeps its old shape. New optional
fields: `depot` (default: the first stop, matching how the old greedy
started), per-stop `demand` (default 1), `capacity` (default
ceil(total demand / K), the smallest even split), `time_limit_s` and `seed`.
`/api/route/estimate` runs greedy, `/api/route/optimize` runs the GA, and
`?solver=ortools` runs OR-Tools. Bad input returns HTTP 400 with a reason.
The old α/β/γ/δ weights are accepted but ignored, and the response says why:
fuel and CO2 are proportional to distance, and the "delay risk" term came from
a made-up formula. Minimising distance is therefore the honest objective.

**Distances.** `scripts/download_osm_graph.py` downloads the OSMnx Bangalore
drive graph once and saves it as GraphML. It keeps the largest strongly
connected component (155,442 nodes, 392,843 directed edges), so every pair of
nodes is reachable. `backend/services/road_network.py` turns that into a
compact `.npz` cache (node coordinates plus a CSR matrix of edge lengths) and
loads it in a background thread at app start. Nothing downloads inside a
request anymore. Per request, each stop snaps to its nearest node with a
KD-tree; one multi-source Dijkstra (`scipy.sparse.csgraph`, written in C)
gives road distances between all snapped nodes, and the snap distance is added
at both ends. One-way streets make the matrix asymmetric, so every solver and
2-opt are written to handle that. Route polylines come from Dijkstra's
predecessor arrays.

**Fallback.** If the graph file is missing or a stop is more than 2 km from
the nearest graph node (outside coverage), distances are straight-line ×
1.2283. That factor is not a guess: it is the median road / straight-line
ratio over 2,000 random node pairs of this graph, from
`results/osm_detour_factor.json`. The response always states
`distance_mode` (`road_network` or `haversine_x_detour`) and the reason.

**Solvers** (`models/routing_models/`, all exposing
`solve(instance, seed=, time_limit=)`):
- `greedy.py`: capacity-aware nearest neighbour; also the "order as received"
  baseline.
- `genetic_algorithm.py`: a real GA in the style of Prins (2004). The
  chromosome is a giant tour (a permutation of the stops). It is decoded by
  Prins' **split**, a shortest path over a DAG that cuts the permutation
  optimally into capacity-feasible trips, with a fleet-limited version that
  uses at most K trips. Selection is a binary tournament, crossover is OX,
  mutation is swap or inversion, and every child gets 2-opt on each route,
  written back into the chromosome. Elitism keeps the best individuals, and
  clones are rejected by cost. The GA stops on a time limit, a generation cap
  or a stall count, and the seed is configurable.
- `ortools_solver.py`: OR-Tools routing (PATH_CHEAPEST_ARC, then Guided Local
  Search) with a capacity dimension, as the strong reference.

**Why giant tour + split + OX + 2-opt?** Permutation encodings make crossover
easy, and OX always yields a valid permutation. Split moves the capacity
constraint into the decoder, so the GA never needs repair operators or penalty
tuning. Pure GAs converge slowly on routing problems; adding a local search
step (a "memetic" GA) is the standard fix, and 2-opt is the cheapest
effective move.

**Honest caveat:** the population is seeded with the greedy tour. Split is
optimal for a fixed order and elitism keeps the best individual, so the GA can
never return worse than greedy. That makes the "GA ≤ greedy" test true by
design. The benchmark (Task 4) therefore also reports a GA run without the
greedy seed, to measure the search itself.

**Tests.** Every solver on random instances: each stop exactly once, routes
start and end at the depot, capacity and fleet respected. Split is checked
against brute force over every cut of a fixed order. 2-opt is checked on an
asymmetric matrix. A 3×3 synthetic road grid with a one-way row exercises road
mode offline. Plus the 2-vs-1-vehicle sanity check, input validation (400s),
and API smoke tests. `deap` was removed from requirements because nothing used
it.

## Task 3 — Honest metrics

**The fake 8 %.** The old service set `baseline = result * 1.08` and reported
the difference as "CO2 saved", so every request claimed about 8 % savings
whatever the routes looked like. That is gone. Savings are now measured
against two real baselines, computed in the same request on the **same
distance matrix**:
- **greedy nearest neighbour**, the obvious heuristic a dispatcher would use;
- **order as received**, stops loaded in input order, a new vehicle whenever
  capacity runs out. This is what happens with no optimisation at all.

The response's `comparison` block reports both baselines' km and vehicle
counts, plus the km and % saved against each. Greedy compared with itself
shows 0. The savings can be small or zero on easy instances, and the API says
so instead of inventing a number. Example request (5 stops, 2 vehicles, road
distances): the GA saved 0.19 % vs greedy and 28.8 % vs order-as-received.

**Fuel and CO2 are labelled estimates.** `fuel_litres = km × 0.08 L/km` and
`co2_kg = litres × 2.31 kg/L`. 2.31 kg CO2 per litre is the standard
combustion factor for petrol; 0.08 L/km is an assumed small petrol van. Both
live in `config.yaml` (routing section) and the response carries an
`estimate_basis` string saying they are estimates, not measurements. Fuel cost
is shown only if `fuel_price_per_litre` is configured, because any default
price would be made up. Because both estimates are linear in distance, "% CO2
saved" always equals "% distance saved"; the CO2 number adds no independent
information, and I would say so if asked.

**Removed things that pretended to be ML.** `RouteDelayModel` and
`RouteFuelModel` were hand-written formulas wrapped in classes that would load
a `.pkl` that never existed. Both files are deleted. So is
`add_route_features()` in `feature_engineering.py`, a made-up fuel-burn
formula applied to columns that do not exist in the dataset (always 0). The
α/β/γ/δ weighted cost is no longer used (see Task 2).

## Task 5 — Leakage-free late-delivery model (consumer portal)

**What was wrong.** The old consumer "model" fed `Late_delivery_risk` (the
label), `Delivery_Status` ("Late delivery" is the label in words),
`Days_for_shipping_real` and `Order_Status` into a model, all of which are
known only after the order ships. That is textbook target leakage. When no
`.pkl` existed, the "prediction" was simply the historical late rate for the
product + pincode. The "confidence" number was `|p − 0.5| × 200`, which is not
a confidence measure at all.

**Target and population.** Target is `Late_delivery_risk` (1 = shipped later
than the mode's promised days). The 7,754 canceled orders
(`Delivery_Status == "Shipping canceled"`, which are exactly the CANCELED and
SUSPECTED_FRAUD orders) are removed from train and test. They never shipped
but carry label 0, so keeping them teaches the model to predict
*cancellations* as "on time". I found this through feature importance:
payment `Type` was the #2 feature, because TRANSFER payments are linked to
fraud cancellations. After the fix its importance fell from 0.36 to 0.016
(mean |SHAP|). `Delivery_Status` is used only to define the population, never
as a feature.

**Features: order-time only.** Shipping mode, promised days, payment type,
customer segment, product / category / department, price, quantity, discount
rate, sales, market / region / country, and order month / day / weekday / hour.
`BANNED_COLUMNS` (label, Delivery_Status, Days_for_shipping_real,
Order_Status, Shipping_Date, shipping_delay_gap) is enforced by
`assert_no_leakage()` at import time and in the training script. Tests fail if
a banned column, or one named after a banned column, enters the feature list,
and also check the saved model's feature list.

**Protocol.** Time-based split on order date: oldest 70 % train
(2015-01-01 → 2017-01-07, 120,934 rows), next 10 % validation (17,277),
newest 20 % test (2017-04-22 → 2018-01-31, 34,554). Rows sharing a timestamp
stay together, so an order's items never straddle the boundary. The F1
threshold is chosen on validation and applied unchanged to test. XGBoost uses
early stopping on validation (best iteration 139).

**Results (test, `results/delay_model_metrics.json`).**

| Model | ROC-AUC | PR-AUC | F1 |
|---|---:|---:|---:|
| Majority class (always "late") | 0.500 | 0.573 | 0.728 |
| Shipping-mode lookup (train late rate per mode) | 0.744 | 0.785 | 0.691 |
| Logistic regression | 0.748 | 0.838 | 0.728 |
| XGBoost | **0.777** | **0.857** | **0.740** |

**The honest reading.** XGBoost beats a one-feature lookup by only 0.033 AUC,
and on F1 it barely beats predicting "late" for everything (0.740 vs 0.728,
because 57 % of shipped orders are late). Breaking the test set down by mode
shows where the signal is:
- First Class: 100 % of shipped orders were late. The label is constant, so
  there is nothing to learn.
- Same Day: late if and only if the order was placed at or after 12:00 (0 %
  late before noon, 100 % after). XGBoost finds this exactly (AUC 1.00 within
  the mode).
- Second Class (80 % late) and Standard Class (39 % late), 79 % of test
  orders: AUC 0.50 and 0.51. **No better than chance.**

DataCo is a synthetic dataset, and "late" is mostly a deterministic function
of mode and order time plus noise. The README says this plainly, and every
prediction response carries the same quality note, generated from the
metrics file.

**Explanations.** XGBoost's built-in TreeSHAP (`pred_contribs`) gives exact
SHAP values, so the heavy `shap` package isn't needed. Categoricals are
ordinal-encoded so each input feature maps to one SHAP value. A test checks
additivity (bias + contributions = the model's log-odds). That test caught a
real bug: with early stopping, `predict_proba` uses only the best iteration's
trees but `pred_contribs` used all of them, so the explanations didn't match
the probability shown.

**Endpoint.** `POST /api/predict/consumer` now scores a hypothetical NEW
order `{product, destination (order country), shipping_mode, quantity?,
order_datetime?}` and returns the probability, the decision threshold, the
top-5 SHAP reasons, and the same order re-scored under every shipping mode,
with a caveat that this is correlational and that "late" is relative to each
mode's own promise. Historical outcomes for that product → destination are
returned in a separate block labelled "descriptive, not a prediction". The old
pincode request returns 400 with an explanation. The CSV endpoint
`/api/recommend/shipping` uses the same model what-if instead of a rule that
read the label column.

**Also removed.** `delay_prediction.py` and `risk_scoring_model.py` were
unused stubs that scored orders from post-delivery columns.
`build_consumer_features()` is gone. Weather/news sample data is no longer
shown as "active disruptions" next to predictions: external signals appear
only when the services return live data.

**Security fix on the CSV endpoint.** Uploads used to be saved as
`data/raw/<client filename>`. That allowed path traversal (`../../x.csv`),
and an upload could become "the dataset" on the next restart, because the
loader picks the best CSV in `data/raw`. Uploads are now parsed from a
temporary file that is deleted afterwards. A test uploads `../../evil.csv`
and checks that nothing is written.

**Country names and granularity.** DataCo stores `Order_Country` in Spanish
("Estados Unidos", "Alemania"). The UI now shows English names from a
164-entry mapping, checked against every value in the dataset with no gaps
and no duplicate labels. The API accepts either spelling. Predictions are
**country-level**: the destination features are the country plus its region
and market, with no city or address information, and the response says so.

**Startup cost.** `/api/predict/options/shipping-modes` took ~2 s on its
first call. The endpoint itself was cheap; the delay was the one-time joblib
load of the model. The model now loads in a background thread at startup
(like the road graph), and the option lists are memoized.

## Task 6 — Producer demand: a real (small) model, and honest labels

**Model.** KMeans on one row per (product, destination city) pair: 39,839
pairs. Features are log1p(total sales), log1p(total quantity), and profit
margin (total profit / total sales, clipped to [−1, 1]). The logs are there
because sales are heavily right-skewed: without them a few big pairs dominate
the Euclidean distance. Features are standardised to z-scores, then KMeans is
fitted for k = 2…8 (n_init = 10, fixed seed) and k is chosen by silhouette,
scored on a fixed 10,000-pair sample because silhouette is O(n²).
`scripts/train_demand_clusters.py` saves the scaler, the model and the cluster
profiles; metrics go to `results/demand_clustering_metrics.json`.

**Result.** k = 3, silhouette 0.417 (k = 2: 0.372; k ≥ 4: ≤ 0.33). That
indicates moderate, not crisp, structure.
- Above-average demand · profitable: 30 % of pairs, mean sales $2,468,
  margin 12.3 %
- Below-average demand · loss-making: 10 %, mean sales $320, margin −54.3 %
- Below-average demand · profitable: 60 %, mean sales $257, margin 23.3 %

**Names come from the centroids, not from me.** "Above/below-average demand"
is the sign of the standardised log-sales coordinate, and
"profitable/loss-making" is the sign of the cluster's mean margin. My first
version ranked clusters by sales into Low/Medium/High, which labelled the
loss-making cluster "Medium demand" even though its sales were almost the
same as "Low". Margin was the real separator, so the naming changed.

**Rule-based parts are labelled as rules.** The composite "demand score" is a
weighted min-max sum, which is fine as a ranking aid but is not a model. It
is now called `rule_based_score`, its tiers are "top / middle / bottom third",
and its weights are actually read from `config.yaml` (before, the config
values were ignored and the code hard-coded the same numbers).

**Bug fix in "High Demand · Low Profit".** The old table sorted by quantity
first and profit second. Ties in total quantity basically never happen, so it
was just a quantity ranking. It now keeps only regions whose average profit
per order is below the median region's, then ranks them by quantity.

**UI and status.** The producer page has a new "Demand Segments (KMeans)"
table. The landing page no longer claims "heuristic mode, plug in .pkl
files": `/api/health` reports which trained artifacts exist (delay model,
demand segments, road graph), and the landing page shows that. No "STUB"
text is left in the code. README and PROJECT_CONTEXT are rewritten in Task 8.

## Task 7 — Fleet Optimizer UI

- Inputs: a depot (blank means the first stop is the depot), stops as
  `lat,lng[,demand[,label]]`, number of vehicles, capacity (blank means
  ceil(total demand / vehicles)), time limit, and solver (GA / OR-Tools /
  greedy). A "Random Bangalore stops" button gives quick demos. The α/β/γ/δ
  weight sliders are gone (Task 2 explains why they never changed the route).
- Output: KPI cards (distance, vehicles used, % saved vs greedy and vs order
  as received), a badge showing the distance mode (road network vs
  straight-line × detour factor) with the reason, a comparison table of the
  three plans on the same matrix (fuel and CO2 columns marked "est."), a
  per-vehicle table (depot → stops → depot, load / capacity, km), and the
  notes the API returns.
- Map: Leaflet 1.9.4 from unpkg, pinned, with Subresource Integrity hashes
  (I computed them from the downloaded files, and they match Leaflet's
  published values). Each vehicle gets a coloured polyline that follows the
  actual shortest road path from the Dijkstra predecessors, plus numbered stop
  markers and a depot marker. In fallback mode the lines are straight, and the
  page says so. If the CDN is unreachable, the page still shows the tables.
- Producer and consumer pages and the heat map still work. Each page's render
  function was run in Node against real API responses with a stubbed DOM: no
  runtime errors, no `undefined`/`NaN` in the output, and every element id
  the scripts use exists in the HTML.
