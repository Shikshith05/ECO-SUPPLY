"""
Routing benchmark: order-as-received, greedy, GA (tuned), GA without greedy
seeding (ablation) and OR-Tools on

  1. random Bangalore CVRP instances (10/20/50/100 stops x 30 evaluation
     seeds, 1-5 vehicles), on road-network distances when the cached OSM
     graph is available (haversine x detour factor otherwise);
  2. CVRPLIB Augerat set A instances, scored against the best-known solution
     cost read from each instance's .sol file.

GA hyperparameters are tuned first on a SEPARATE seed set (1000+) and the
winning setting is used, frozen, for evaluation.

    .venv\\Scripts\\python scripts/benchmark_routing.py            # full run (~1.5 h)
    .venv\\Scripts\\python scripts/benchmark_routing.py --quick    # smoke run (~2 min, not for reporting)

Outputs (results/):
  ga_tuning.csv, ga_tuned_params.json
  routing_benchmark.csv            one row per (instance, solver, seed)
  routing_benchmark_summary.json   aggregated numbers
  routing_benchmark.md             markdown tables (copied into the README)
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import os
import re
import statistics
import sys
import time
import urllib.request
from dataclasses import asdict
from datetime import datetime, timezone

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from backend.services import road_network  # noqa: E402
from backend.services.road_network import haversine_matrix, routing_config  # noqa: E402
from models.routing_models import genetic_algorithm, greedy, ortools_solver  # noqa: E402
from models.routing_models.cvrp import CVRPInstance, validate_solution  # noqa: E402

RESULTS = os.path.join(ROOT, "results")
CVRPLIB_DIR = os.path.join(ROOT, "data", "external", "cvrplib")
CVRPLIB_BASE = "https://galgos.inf.puc-rio.br/cvrplib/index.php/en"
CVRPLIB_INSTANCES = ["A-n32-k5", "A-n33-k5", "A-n37-k6", "A-n39-k5", "A-n45-k7",
                     "A-n53-k7", "A-n60-k9", "A-n69-k9", "A-n80-k10"]

BBOX = {"lat": (12.85, 13.10), "lng": (77.45, 77.75)}
DEPOT = (12.9716, 77.5946)        # central Bangalore (MG Road area)
SIZES = [10, 20, 50, 100]
TIME_LIMITS = {10: 2.0, 20: 4.0, 50: 10.0, 100: 20.0}
EVAL_SEEDS = list(range(30))
TUNE_SEEDS = list(range(1000, 1010))
TUNE_SIZES = [20, 50]
TUNE_GRID = {
    "population_size": [20, 40],
    "mutation_rate": [0.1, 0.3],
    "relocate": [False, True],      # inter-route relocate in the local search, on top of 2-opt
}


# ── instances ────────────────────────────────────────────────────────────────

class Distances:
    def __init__(self):
        self.net = road_network.load_network()
        self.factor = float(routing_config()["haversine_detour_factor"])
        self.mode = "road_network" if self.net is not None else "haversine_x_detour"

    def matrix(self, points):
        if self.net is not None:
            return self.net.distance_matrix(points)[0]
        return haversine_matrix(points) * self.factor

    def on_network(self, lat, lng, max_snap_km=0.5) -> bool:
        if self.net is None:
            return True
        _, snap = self.net.nearest_nodes([(lat, lng)])
        return float(snap[0]) <= max_snap_km


def random_instance(n: int, seed: int, dist: Distances) -> CVRPInstance:
    rng = np.random.default_rng(seed)
    pts = []
    while len(pts) < n:   # rejection-sample points that lie on the cached road graph
        lat, lng = rng.uniform(*BBOX["lat"]), rng.uniform(*BBOX["lng"])
        if dist.on_network(lat, lng):
            pts.append((float(lat), float(lng)))
    demands = [0] + rng.integers(1, 11, size=n).tolist()
    k = 1 + seed % 5
    capacity = math.ceil(sum(demands) / k * 1.1)   # 10 % slack over the tightest feasible capacity
    return CVRPInstance(dist.matrix([DEPOT] + pts), demands, capacity, k, name=f"blr-n{n}-s{seed}")


def _cvrplib_ids() -> dict:
    html = urllib.request.urlopen(f"{CVRPLIB_BASE}/instances", timeout=60).read().decode("utf-8", "replace")
    return {m.group(2): m.group(1)
            for m in re.finditer(r'download/instance/(\d+)"[^>]*>\s*([A-Za-z0-9\-]+)\s*<', html)}


def fetch_cvrplib(names) -> None:
    os.makedirs(CVRPLIB_DIR, exist_ok=True)
    missing = [n for n in names if not (os.path.exists(os.path.join(CVRPLIB_DIR, n + ".vrp"))
                                        and os.path.exists(os.path.join(CVRPLIB_DIR, n + ".sol")))]
    if not missing:
        return
    ids = _cvrplib_ids()
    for name in missing:
        for kind, ext in (("instance", ".vrp"), ("bks", ".sol")):
            data = urllib.request.urlopen(f"{CVRPLIB_BASE}/download/{kind}/{ids[name]}", timeout=60).read()
            with open(os.path.join(CVRPLIB_DIR, name + ext), "wb") as f:
                f.write(data)
        print(f"downloaded {name}")


def read_cvrplib(name: str):
    text = open(os.path.join(CVRPLIB_DIR, name + ".vrp"), encoding="utf-8").read()
    capacity = int(re.search(r"CAPACITY\s*:\s*(\d+)", text).group(1))
    dim = int(re.search(r"DIMENSION\s*:\s*(\d+)", text).group(1))
    if "EUC_2D" not in text:
        raise ValueError(f"{name}: only EUC_2D instances are supported")
    lines = text.splitlines()
    i = next(k for k, l in enumerate(lines) if l.strip().startswith("NODE_COORD_SECTION"))
    coords = [tuple(map(float, lines[i + 1 + k].split()[1:3])) for k in range(dim)]
    j = next(k for k, l in enumerate(lines) if l.strip().startswith("DEMAND_SECTION"))
    demands = [int(lines[j + 1 + k].split()[1]) for k in range(dim)]
    d = next(k for k, l in enumerate(lines) if l.strip().startswith("DEPOT_SECTION"))
    depot = int(lines[d + 1].split()[0]) - 1
    if depot != 0:
        raise ValueError(f"{name}: depot must be node 1")
    xy = np.array(coords)
    # TSPLIB EUC_2D: Euclidean distance rounded to the nearest integer.
    matrix = np.floor(np.sqrt(((xy[:, None, :] - xy[None, :, :]) ** 2).sum(-1)) + 0.5)
    k = int(re.search(r"-k(\d+)", name).group(1))
    sol = open(os.path.join(CVRPLIB_DIR, name + ".sol"), encoding="utf-8").read()
    bks = float(re.search(r"Cost\s+([\d.]+)", sol).group(1))
    optimal = "optimal value" in text.lower()
    return CVRPInstance(matrix, demands, capacity, k, name=name), bks, optimal


# ── running ──────────────────────────────────────────────────────────────────

def run_solver(name, inst, seed, time_limit, ga_params):
    if name == "order_as_received":
        sol = greedy.solve_order_as_received(inst)
    elif name == "greedy":
        sol = greedy.solve(inst)
    elif name == "ga":
        sol = genetic_algorithm.solve(inst, seed=seed, time_limit=time_limit, params=ga_params)
    elif name == "ga_unseeded":
        sol = genetic_algorithm.solve(inst, seed=seed, time_limit=time_limit,
                                      params={**ga_params, "seed_with_greedy": False})
    elif name == "ortools":
        sol = ortools_solver.solve(inst, seed=seed, time_limit=time_limit)
    else:
        raise ValueError(name)
    errors = validate_solution(inst, sol.routes, enforce_fleet=False)
    if errors:
        raise AssertionError(f"{name} produced an invalid solution on {inst.name}: {errors}")
    return sol


def tune(dist: Distances, quick: bool):
    seeds = TUNE_SEEDS[:2] if quick else TUNE_SEEDS
    sizes = [20] if quick else TUNE_SIZES
    grid = [dict(zip(TUNE_GRID, values)) for values in itertools.product(*TUNE_GRID.values())]
    if quick:
        grid = grid[:2]
    instances = [(n, s, random_instance(n, s, dist)) for n in sizes for s in seeds]
    reference = {}
    for n, s, inst in instances:
        tl = TIME_LIMITS[n] / (4 if quick else 1)
        reference[(n, s)] = run_solver("ortools", inst, s, tl, {}).distance
    rows = []
    for cfg in grid:
        gaps = []
        for n, s, inst in instances:
            tl = TIME_LIMITS[n] / (4 if quick else 1)
            d = run_solver("ga", inst, s, tl, cfg).distance
            gap = 100 * (d - reference[(n, s)]) / reference[(n, s)]
            gaps.append(gap)
            rows.append({**cfg, "n": n, "seed": s, "ga_km": round(d, 4),
                         "ortools_km": round(reference[(n, s)], 4), "gap_pct": round(gap, 4)})
        print(f"tune {cfg}: mean gap vs OR-Tools {statistics.mean(gaps):.2f}%")
    write_csv(os.path.join(RESULTS, "ga_tuning.csv"), rows)
    scores = {}
    for r in rows:
        key = tuple(r[k] for k in TUNE_GRID)
        scores.setdefault(key, []).append(r["gap_pct"])
    best_key = min(scores, key=lambda k: statistics.mean(scores[k]))
    best = dict(zip(TUNE_GRID, best_key))
    summary = {"chosen_params": best, "mean_gap_vs_ortools_pct": round(statistics.mean(scores[best_key]), 4),
               "tuning_seeds": seeds, "tuning_sizes": sizes, "grid": TUNE_GRID,
               "all_configs": {str(dict(zip(TUNE_GRID, k))): round(statistics.mean(v), 4) for k, v in scores.items()},
               "distance_mode": dist.mode}
    with open(os.path.join(RESULTS, "ga_tuned_params.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return best


def write_csv(path, rows):
    if not rows:
        return
    keys = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def mean_std(values):
    values = list(values)
    if not values:
        return None, None
    return statistics.mean(values), (statistics.stdev(values) if len(values) > 1 else 0.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="tiny smoke run; numbers are not for reporting")
    ap.add_argument("--skip-tuning", action="store_true", help="reuse results/ga_tuned_params.json")
    args = ap.parse_args()
    os.makedirs(RESULTS, exist_ok=True)
    started = time.time()
    dist = Distances()
    print(f"distance mode: {dist.mode}")

    if args.skip_tuning:
        with open(os.path.join(RESULTS, "ga_tuned_params.json"), encoding="utf-8") as f:
            ga_params = json.load(f)["chosen_params"]
    else:
        ga_params = tune(dist, args.quick)
    print(f"GA params for evaluation: {ga_params}")

    solvers = ["order_as_received", "greedy", "ga", "ga_unseeded", "ortools"]
    sizes = [10, 20] if args.quick else SIZES
    seeds = EVAL_SEEDS[:3] if args.quick else EVAL_SEEDS
    rows = []
    for n in sizes:
        for s in seeds:
            inst = random_instance(n, s, dist)
            tl = TIME_LIMITS[n] / (4 if args.quick else 1)
            for name in solvers:
                sol = run_solver(name, inst, s, tl, ga_params)
                rows.append({"set": "bangalore_random", "instance": inst.name, "n": n, "vehicles": inst.n_vehicles,
                             "capacity": inst.capacity, "solver": name, "seed": s,
                             "distance": round(sol.distance, 4), "vehicles_used": sol.vehicles_used,
                             "fleet_feasible": sol.vehicles_used <= inst.n_vehicles,
                             "runtime_s": round(sol.runtime_s, 3),
                             "time_limit_s": tl if name in ("ga", "ga_unseeded", "ortools") else "",
                             "distance_mode": dist.mode, "bks": ""})
            print(f"n={n} seed={s} done ({time.time() - started:.0f}s)")

    fetch_cvrplib(CVRPLIB_INSTANCES)
    lib_names = CVRPLIB_INSTANCES[:2] if args.quick else CVRPLIB_INSTANCES
    ga_seeds = [0] if args.quick else [0, 1, 2]
    for name in lib_names:
        inst, bks, optimal = read_cvrplib(name)
        n = inst.n_customers
        tl = (5.0 if n <= 40 else 10.0 if n <= 60 else 20.0) / (4 if args.quick else 1)
        for solver in solvers:
            for s in (ga_seeds if solver.startswith("ga") else [0]):
                sol = run_solver(solver, inst, s, tl, ga_params)
                rows.append({"set": "cvrplib_A", "instance": name, "n": n, "vehicles": inst.n_vehicles,
                             "capacity": inst.capacity, "solver": solver, "seed": s,
                             "distance": round(sol.distance, 4), "vehicles_used": sol.vehicles_used,
                             "fleet_feasible": sol.vehicles_used <= inst.n_vehicles,
                             "runtime_s": round(sol.runtime_s, 3),
                             "time_limit_s": tl if solver in ("ga", "ga_unseeded", "ortools") else "",
                             "distance_mode": "euc_2d_rounded", "bks": bks, "bks_proven_optimal": optimal})
        print(f"{name} done ({time.time() - started:.0f}s)")

    for r in rows:
        r.setdefault("bks_proven_optimal", "")
    suffix = "_quick" if args.quick else ""
    write_csv(os.path.join(RESULTS, f"routing_benchmark{suffix}.csv"), rows)
    summary = summarise(rows, ga_params, dist.mode, time.time() - started, args.quick)
    with open(os.path.join(RESULTS, f"routing_benchmark_summary{suffix}.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    with open(os.path.join(RESULTS, f"routing_benchmark{suffix}.md"), "w", encoding="utf-8") as f:
        f.write(markdown(summary))
    print(markdown(summary))


def summarise(rows, ga_params, mode, runtime, quick):
    solvers = ["order_as_received", "greedy", "ga", "ga_unseeded", "ortools"]
    out = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "quick_run": quick,
           "ga_params": ga_params,
           "ga_params_effective": asdict(genetic_algorithm.GAParams.from_dict(ga_params)),
           "random_distance_mode": mode, "time_limits_s": TIME_LIMITS,
           "total_runtime_s": round(runtime, 1), "bangalore_random": {}, "cvrplib_A": {}}
    rnd = [r for r in rows if r["set"] == "bangalore_random"]
    for n in sorted({r["n"] for r in rnd}):
        by = {(r["solver"], r["seed"]): r for r in rnd if r["n"] == n}
        seeds = sorted({r["seed"] for r in rnd if r["n"] == n})
        block = {"instances": len(seeds)}
        for s_name in solvers:
            d = [by[(s_name, s)]["distance"] for s in seeds]
            gap = [100 * (by[(s_name, s)]["distance"] - by[("ortools", s)]["distance"]) / by[("ortools", s)]["distance"]
                   for s in seeds]
            vs_greedy = [100 * (by[("greedy", s)]["distance"] - by[(s_name, s)]["distance"]) / by[("greedy", s)]["distance"]
                         for s in seeds]
            vs_order = [100 * (by[("order_as_received", s)]["distance"] - by[(s_name, s)]["distance"])
                        / by[("order_as_received", s)]["distance"] for s in seeds]
            m, sd = mean_std(d)
            gm, gsd = mean_std(gap)
            block[s_name] = {
                "mean_km": round(m, 3), "std_km": round(sd, 3),
                "mean_gap_vs_ortools_pct": round(gm, 3), "std_gap_vs_ortools_pct": round(gsd, 3),
                "mean_saving_vs_greedy_pct": round(statistics.mean(vs_greedy), 3),
                "mean_saving_vs_order_pct": round(statistics.mean(vs_order), 3),
                "worse_than_greedy": sum(by[(s_name, s)]["distance"] > by[("greedy", s)]["distance"] + 1e-6 for s in seeds),
                "fleet_infeasible": sum(not by[(s_name, s)]["fleet_feasible"] for s in seeds),
                "mean_runtime_s": round(statistics.mean(by[(s_name, s)]["runtime_s"] for s in seeds), 3),
            }
        out["bangalore_random"][str(n)] = block
    lib = [r for r in rows if r["set"] == "cvrplib_A"]
    for name in dict.fromkeys(r["instance"] for r in lib):
        rs = [r for r in lib if r["instance"] == name]
        bks = rs[0]["bks"]
        block = {"n": rs[0]["n"], "vehicles": rs[0]["vehicles"], "bks": bks, "bks_proven_optimal": rs[0]["bks_proven_optimal"]}
        for s_name in solvers:
            d = [r["distance"] for r in rs if r["solver"] == s_name]
            m, sd = mean_std(d)
            block[s_name] = {"mean": round(m, 2), "std": round(sd, 2), "runs": len(d),
                             "gap_vs_bks_pct": round(100 * (m - bks) / bks, 3),
                             "fleet_infeasible_runs": sum(not r["fleet_feasible"] for r in rs if r["solver"] == s_name),
                             "mean_runtime_s": round(statistics.mean(r["runtime_s"] for r in rs if r["solver"] == s_name), 3)}
        out["cvrplib_A"][name] = block
    if lib:
        out["cvrplib_A_mean_gap_vs_bks_pct"] = {
            s: round(statistics.mean(b[s]["gap_vs_bks_pct"] for b in out["cvrplib_A"].values() if isinstance(b, dict)), 3)
            for s in solvers}
    return out


def markdown(summary) -> str:
    names = {"order_as_received": "Order as received", "greedy": "Greedy NN", "ga": "GA (tuned)",
             "ga_unseeded": "GA, no greedy seed", "ortools": "OR-Tools GLS"}
    lines = [f"<!-- generated by scripts/benchmark_routing.py at {summary['generated_at']} -->", ""]
    if summary["quick_run"]:
        lines += ["**QUICK SMOKE RUN: not for reporting.**", ""]
    lines += [f"### Random Bangalore instances (distance mode: `{summary['random_distance_mode']}`)", "",
              f"30 evaluation seeds per size (unless quick), vehicles = 1 + seed mod 5, demands U{{1..10}}, "
              f"capacity = 1.1 x total demand / vehicles. Time limits per size (s): "
              f"{', '.join(f'{k}: {v:g}' for k, v in summary['time_limits_s'].items())}. GA params: "
              f"`{json.dumps(summary['ga_params'])}`; all effective GA settings: "
              f"`{json.dumps(summary['ga_params_effective'])}`.", "",
              "| Stops | Solver | Mean km ± std | Gap vs OR-Tools | Saving vs greedy | Saving vs order-as-received | Worse than greedy | Mean runtime (s) |",
              "|---:|---|---:|---:|---:|---:|---:|---:|"]
    for n, block in summary["bangalore_random"].items():
        for s, label in names.items():
            b = block[s]
            lines.append(f"| {n} | {label} | {b['mean_km']:.2f} ± {b['std_km']:.2f} | {b['mean_gap_vs_ortools_pct']:+.2f}% "
                         f"| {b['mean_saving_vs_greedy_pct']:+.2f}% | {b['mean_saving_vs_order_pct']:+.2f}% "
                         f"| {b['worse_than_greedy']}/{block['instances']} | {b['mean_runtime_s']:.2f} |")
    if summary["cvrplib_A"]:
        lines += ["", "### CVRPLIB set A (Augerat), gap vs best-known solution from the instance's .sol file", "",
                  "| Instance | BKS | Greedy | GA mean ± std (3 seeds) | GA, no seed | OR-Tools | Greedy gap | GA gap | OR-Tools gap |",
                  "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
        for name, b in summary["cvrplib_A"].items():
            g_flag = " *" if b["greedy"]["fleet_infeasible_runs"] else ""
            lines.append(f"| {name} | {b['bks']:g} | {b['greedy']['mean']:.0f}{g_flag} | {b['ga']['mean']:.1f} ± {b['ga']['std']:.1f} "
                         f"| {b['ga_unseeded']['mean']:.1f} | {b['ortools']['mean']:.0f} | {b['greedy']['gap_vs_bks_pct']:+.2f}% "
                         f"| {b['ga']['gap_vs_bks_pct']:+.2f}% | {b['ortools']['gap_vs_bks_pct']:+.2f}% |")
        mg = summary["cvrplib_A_mean_gap_vs_bks_pct"]
        lines.append(f"| **Mean gap** | | | | | | {mg['greedy']:+.2f}% | {mg['ga']:+.2f}% | {mg['ortools']:+.2f}% |")
        lines += ["", "\\* greedy needed more routes than the instance's vehicle count (not fleet-feasible)."]
    lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
