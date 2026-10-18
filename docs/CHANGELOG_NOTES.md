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
