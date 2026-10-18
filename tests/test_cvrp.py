"""CVRP core, solvers and road-distance service."""

import math
import random

import numpy as np
import pytest
from scipy.sparse import csr_matrix

from backend.services import road_network, route_optimizer
from backend.services.road_network import RoadNetwork, haversine_matrix
from models.routing_models import genetic_algorithm, greedy, ortools_solver
from models.routing_models.cvrp import (CVRPInstance, relocate, route_distance, solution_distance, split,
                                        two_opt, validate_solution)


def random_instance(n, k, seed, slack=1.1, asymmetric=False):
    rng = random.Random(seed)
    pts = [(12.97, 77.59)] + [(rng.uniform(12.85, 13.1), rng.uniform(77.45, 77.75)) for _ in range(n)]
    d = haversine_matrix(pts) * 1.2
    if asymmetric:
        d = d * np.array([[1.0 if i < j else 1.3 for j in range(n + 1)] for i in range(n + 1)])
        np.fill_diagonal(d, 0)
    demands = [0] + [rng.randint(1, 10) for _ in range(n)]
    cap = math.ceil(sum(demands) / k * slack)
    return CVRPInstance(d, demands, cap, k)


SOLVERS = [
    ("greedy", lambda inst, seed: greedy.solve(inst)),
    ("ga", lambda inst, seed: genetic_algorithm.solve(inst, seed=seed, time_limit=1.0)),
    ("ortools", lambda inst, seed: ortools_solver.solve(inst, time_limit=1.0)),
]


@pytest.mark.parametrize("name,solve", SOLVERS, ids=[s[0] for s in SOLVERS])
@pytest.mark.parametrize("n,k,seed", [(8, 1, 0), (15, 3, 1), (25, 4, 2)])
def test_solution_is_valid(name, solve, n, k, seed):
    inst = random_instance(n, k, seed)
    sol = solve(inst, seed)
    assert validate_solution(inst, sol.routes) == []
    # every stop exactly once
    visited = sorted(c for r in sol.routes for c in r)
    assert visited == list(range(1, n + 1))
    # capacity respected
    assert all(sum(inst.demands[c] for c in r) <= inst.capacity for r in sol.routes)
    # routes start and end at the depot: the reported distance includes both depot legs
    expected = sum(inst.dist[0][r[0]] + sum(inst.dist[a][b] for a, b in zip(r, r[1:])) + inst.dist[r[-1]][0]
                   for r in sol.routes)
    assert sol.distance == pytest.approx(expected)
    assert all(0 not in r for r in sol.routes)


@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_ga_never_worse_than_greedy(seed):
    inst = random_instance(20, 1 + seed % 3, seed)
    g = greedy.solve(inst)
    ga = genetic_algorithm.solve(inst, seed=seed, time_limit=1.0)
    assert ga.distance <= g.distance + 1e-9


def test_ga_is_reproducible_with_fixed_seed_and_generation_cap():
    inst = random_instance(15, 2, 5)
    params = {"max_generations": 15}
    a = genetic_algorithm.solve(inst, seed=7, time_limit=60, params=params)
    b = genetic_algorithm.solve(inst, seed=7, time_limit=60, params=params)
    assert a.routes == b.routes


def test_order_crossover_produces_permutations():
    ga = genetic_algorithm.GeneticAlgorithm(random_instance(10, 1, 0), genetic_algorithm.GAParams(), seed=3)
    p1, p2 = list(range(1, 11)), list(range(10, 0, -1))
    for _ in range(50):
        child = ga.order_crossover(p1, p2)
        assert sorted(child) == p1
        assert sorted(ga.mutate(child)) == p1


def test_split_is_optimal_for_a_fixed_order():
    inst = random_instance(9, 3, 4)
    tour = list(range(1, 10))
    cost, routes = split(inst, tour, max_routes=3)
    best = math.inf   # brute force over every way to cut the fixed order
    for mask in range(1 << 8):
        cuts = [i + 1 for i in range(8) if mask >> i & 1]
        parts = [tour[a:b] for a, b in zip([0] + cuts, cuts + [9])]
        if len(parts) > 3 or any(sum(inst.demands[c] for c in p) > inst.capacity for p in parts):
            continue
        best = min(best, sum(route_distance(inst, p) for p in parts))
    assert cost == pytest.approx(best)
    assert [c for r in routes for c in r] == tour


def test_two_opt_handles_asymmetric_distances():
    inst = random_instance(12, 1, 3, slack=2, asymmetric=True)
    route = list(range(1, 13))
    improved = two_opt(inst, route)
    assert sorted(improved) == route
    assert route_distance(inst, improved) <= route_distance(inst, route) + 1e-9


@pytest.mark.parametrize("asymmetric", [False, True])
def test_relocate_keeps_solution_valid_and_never_worse(asymmetric):
    inst = random_instance(20, 4, 9, asymmetric=asymmetric)
    start = greedy.solve(inst).routes
    moved = relocate(inst, start)
    assert validate_solution(inst, moved) == []
    assert solution_distance(inst, moved) <= solution_distance(inst, start) + 1e-9


def test_infeasible_instance_is_reported():
    inst = CVRPInstance(np.zeros((3, 3)), [0, 5, 5], capacity=4, n_vehicles=1)
    assert inst.feasibility_problems()


# ── service ───────────────────────────────────────────────────────────────────

STOPS = [
    {"lat": 12.9716, "lng": 77.5946, "order_id": "A"},
    {"lat": 13.0055, "lng": 77.5721, "order_id": "B"},
    {"lat": 12.9784, "lng": 77.6408, "order_id": "C"},
    {"lat": 12.9352, "lng": 77.6245, "order_id": "D"},
    {"lat": 12.9141, "lng": 77.6101, "order_id": "E"},
]


def test_fallback_mode_is_reported_without_graph():
    out = route_optimizer.plan_routes({"stops": STOPS, "vehicle_count": 2}, solver="greedy")
    assert out["distance_mode"] == "haversine_x_detour"
    assert out["distance_mode_reason"]
    assert out["depot"]["source"] == "first_stop"
    served = sorted(s["order_id"] for r in out["routes"] for s in r["stops"])
    assert served == ["B", "C", "D", "E"]
    for r in out["routes"]:
        assert r["path"][0] == r["path"][-1] == [12.9716, 77.5946]   # starts and ends at the depot


def test_more_vehicles_never_beat_the_single_vehicle_tour():
    one = route_optimizer.plan_routes({"stops": STOPS, "vehicle_count": 1, "time_limit_s": 1}, solver="ortools")
    two = route_optimizer.plan_routes({"stops": STOPS, "vehicle_count": 2, "time_limit_s": 1}, solver="ortools")
    # Every vehicle returns to the depot, so splitting the work cannot beat the best
    # single tour (triangle inequality). The old chunking code violated this.
    assert two["summary"]["distance_km"] >= one["summary"]["distance_km"] - 1e-6


def test_explicit_depot_demand_and_capacity():
    payload = {"stops": [dict(s, demand=3) for s in STOPS], "depot": {"lat": 12.95, "lng": 77.6},
               "vehicle_count": 3, "capacity": 6, "time_limit_s": 1}
    out = route_optimizer.plan_routes(payload, solver="ga")
    assert all(r["load"] <= 6 for r in out["routes"])
    assert sum(len(r["stops"]) for r in out["routes"]) == 5
    assert out["summary"]["vehicles_used"] <= 3


def test_invalid_requests_raise_input_errors():
    with pytest.raises(route_optimizer.RoutingInputError):
        route_optimizer.plan_routes({"stops": [{"lat": "x", "lng": 1}]})
    with pytest.raises(route_optimizer.RoutingInputError):   # total demand > fleet capacity
        route_optimizer.plan_routes({"stops": STOPS, "vehicle_count": 1, "capacity": 2})
    with pytest.raises(route_optimizer.RoutingInputError):
        route_optimizer.plan_routes({"stops": STOPS}, solver="simulated_annealing")


def tiny_grid_network():
    """3x3 grid of nodes ~1.1 km apart; the top row is one-way eastbound."""
    lat0, lon0, step = 12.95, 77.58, 0.01
    lat = [lat0 + r * step for r in range(3) for c in range(3)]
    lon = [lon0 + c * step for r in range(3) for c in range(3)]
    edges = {}
    for r in range(3):
        for c in range(3):
            for dr, dc in ((0, 1), (1, 0)):
                if r + dr < 3 and c + dc < 3:
                    a, b = r * 3 + c, (r + dr) * 3 + c + dc
                    km = road_network.haversine_km(lat[a], lon[a], lat[b], lon[b])
                    edges[(a, b)] = km
                    if not (r == 2 and dr == 0):
                        edges[(b, a)] = km
    rows, cols = zip(*edges)
    adj = csr_matrix((list(edges.values()), (rows, cols)), shape=(9, 9))
    return RoadNetwork(np.arange(9), np.array(lat), np.array(lon), adj, lat0)


def test_road_mode_uses_shortest_paths(monkeypatch):
    net = tiny_grid_network()
    monkeypatch.setattr(road_network, "load_network", lambda: net)
    stops = [{"lat": 12.95, "lng": 77.58}, {"lat": 12.97, "lng": 77.60}, {"lat": 12.97, "lng": 77.58}]
    out = route_optimizer.plan_routes({"stops": stops, "vehicle_count": 1, "time_limit_s": 1}, solver="ortools")
    assert out["distance_mode"] == "road_network"
    pts = [(s["lat"], s["lng"]) for s in stops]
    matrix, *_ = net.distance_matrix(pts)
    assert (matrix >= haversine_matrix(pts) - 1e-9).all()      # roads are never shorter than the straight line
    assert matrix[2, 1] != pytest.approx(matrix[1, 2])          # one-way street -> asymmetric
    path = out["routes"][0]["path"]
    assert path[0] == path[-1] == [12.95, 77.58] and len(path) > 3


def test_far_away_stop_falls_back_to_haversine(monkeypatch):
    monkeypatch.setattr(road_network, "load_network", lambda: tiny_grid_network())
    stops = [{"lat": 12.95, "lng": 77.58}, {"lat": 13.5, "lng": 78.2}]
    out = route_optimizer.plan_routes({"stops": stops}, solver="greedy")
    assert out["distance_mode"] == "haversine_x_detour"
    assert "coverage" in out["distance_mode_reason"]


# ── honest metrics (Task 3) ───────────────────────────────────────────────────

def test_savings_are_measured_against_real_baselines():
    out = route_optimizer.plan_routes({"stops": STOPS, "vehicle_count": 2, "time_limit_s": 1}, solver="ortools")
    cmp = out["comparison"]
    dist = out["summary"]["distance_km"]
    assert cmp["saved_vs_greedy_km"] == pytest.approx(cmp["greedy"]["distance_km"] - dist, abs=1e-3)
    assert cmp["saved_vs_order_as_received_km"] == pytest.approx(
        cmp["order_as_received"]["distance_km"] - dist, abs=1e-3)
    assert cmp["saved_vs_greedy_pct"] == pytest.approx(
        100 * (cmp["greedy"]["distance_km"] - dist) / cmp["greedy"]["distance_km"], abs=0.01)


def test_greedy_shows_zero_saving_vs_itself():
    out = route_optimizer.plan_routes({"stops": STOPS, "vehicle_count": 2}, solver="greedy")
    assert out["comparison"]["saved_vs_greedy_km"] == 0


def test_fuel_and_co2_are_linear_labelled_estimates():
    from backend.services.road_network import routing_config

    cfg = routing_config()
    est = route_optimizer.estimates(100.0)
    assert est["fuel_litres_est"] == pytest.approx(100 * cfg["fuel_litres_per_km"])
    assert est["co2_kg_est"] == pytest.approx(100 * cfg["fuel_litres_per_km"] * cfg["co2_kg_per_litre"])
    assert "estimate" in est["estimate_basis"].lower()
    assert route_optimizer.estimates(0.0)["co2_kg_est"] == 0


# ── exact small instances and early stopping ──────────────────────────────────

def brute_force_optimum(inst):
    import itertools

    best = math.inf
    for perm in itertools.permutations(range(1, inst.n_customers + 1)):
        cost, _ = split(inst, list(perm), max_routes=inst.n_vehicles)
        best = min(best, cost)
    return best


@pytest.mark.parametrize("n,k,seed,asym", [(5, 1, 0, False), (6, 2, 1, True), (7, 3, 2, False), (7, 2, 3, True)])
def test_exact_solver_matches_brute_force(n, k, seed, asym):
    from models.routing_models import exact

    inst = random_instance(n, k, seed, asymmetric=asym)
    sol = exact.solve(inst)
    assert validate_solution(inst, sol.routes) == []
    assert sol.distance == pytest.approx(brute_force_optimum(inst))


def test_ga_solves_small_instances_exactly_and_quickly():
    from models.routing_models import exact

    inst = random_instance(8, 2, 11)
    ga = genetic_algorithm.solve(inst, seed=0, time_limit=5)
    assert ga.meta["exact"] is True and ga.meta["stopped_by"] == "solved_exactly"
    assert ga.runtime_s < 2.0
    assert ga.distance == pytest.approx(exact.solve(inst).distance)
    assert ortools_solver.solve(inst, time_limit=1).distance >= ga.distance - 1e-6


def test_ga_early_stopping_before_time_limit():
    inst = random_instance(12, 2, 4)
    sol = genetic_algorithm.solve(inst, seed=0, time_limit=30, params={"stall_generations": 10})
    assert sol.meta["stopped_by"] in ("stall", "converged")
    assert sol.runtime_s < 30
