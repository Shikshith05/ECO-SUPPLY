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
