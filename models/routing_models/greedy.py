"""
Baselines with the common solver interface `solve(instance, *, seed, time_limit)`.

* greedy  — capacity-aware nearest neighbour: from the current node, drive to
            the nearest unvisited stop that still fits in the vehicle; when no
            stop fits, return to the depot and start the next vehicle.
* order   — "order as received": stops are loaded in input order, starting a
            new vehicle whenever the next stop would exceed capacity.

Neither enforces the fleet limit by itself. If one needs more routes than
there are vehicles, the solution says so in meta["fleet_feasible"] instead of
silently dropping stops.
"""

from __future__ import annotations

import time
from typing import List, Optional

from models.routing_models.cvrp import CVRPInstance, CVRPSolution, solution_distance


def nearest_neighbour_routes(inst: CVRPInstance) -> List[List[int]]:
    d, q, cap = inst.dist_list, inst.demands, inst.capacity
    unvisited = set(range(1, inst.n_customers + 1))
    routes: List[List[int]] = []
    while unvisited:
        route: List[int] = []
        current, load = 0, 0.0
        while True:
            feasible = [c for c in unvisited if load + q[c] <= cap + 1e-9]
            if not feasible:
                break
            nxt = min(feasible, key=lambda c: (d[current][c], c))  # index breaks ties deterministically
            route.append(nxt)
            unvisited.remove(nxt)
            load += q[nxt]
            current = nxt
        if not route:  # a single stop larger than the capacity
            raise ValueError("A stop's demand exceeds the vehicle capacity.")
        routes.append(route)
    return routes


def order_as_received_routes(inst: CVRPInstance) -> List[List[int]]:
    q, cap = inst.demands, inst.capacity
    routes: List[List[int]] = [[]]
    load = 0.0
    for c in range(1, inst.n_customers + 1):
        if q[c] > cap + 1e-9:
            raise ValueError("A stop's demand exceeds the vehicle capacity.")
        if load + q[c] > cap + 1e-9:
            routes.append([])
            load = 0.0
        routes[-1].append(c)
        load += q[c]
    return [r for r in routes if r]


def _package(inst: CVRPInstance, routes: List[List[int]], name: str, t0: float) -> CVRPSolution:
    return CVRPSolution(
        routes=routes,
        distance=solution_distance(inst, routes),
        solver=name,
        runtime_s=time.perf_counter() - t0,
        meta={"fleet_feasible": len(routes) <= inst.n_vehicles},
    )


def solve(inst: CVRPInstance, *, seed: int = 0, time_limit: Optional[float] = None, **_) -> CVRPSolution:
    """Greedy nearest neighbour (deterministic; seed and time_limit are unused)."""
    t0 = time.perf_counter()
    return _package(inst, nearest_neighbour_routes(inst), "greedy", t0)


def solve_order_as_received(inst: CVRPInstance, *, seed: int = 0, time_limit: Optional[float] = None, **_) -> CVRPSolution:
    t0 = time.perf_counter()
    return _package(inst, order_as_received_routes(inst), "order_as_received", t0)
