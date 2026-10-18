"""
Capacitated Vehicle Routing Problem (CVRP) core: instance/solution types,
distance helpers, feasibility checks, Prins' optimal split and 2-opt.

Conventions
-----------
* Node 0 is the depot; customers are 1..n.
* `dist[i][j]` is the travel distance from i to j. It may be asymmetric
  (road networks have one-way streets), so nothing here assumes
  dist[i][j] == dist[j][i].
* A route is a list of customer indices WITHOUT the depot; it is implicitly
  depot -> route[0] -> ... -> route[-1] -> depot.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

INF = float("inf")


@dataclass
class CVRPInstance:
    dist: np.ndarray                 # (n+1, n+1) distance matrix, node 0 = depot
    demands: Sequence[float]         # length n+1, demands[0] == 0
    capacity: float                  # identical capacity for every vehicle
    n_vehicles: int                  # fleet size (max number of routes)
    name: str = ""
    dist_list: List[List[float]] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self.dist = np.asarray(self.dist, dtype=float)
        n_nodes = self.dist.shape[0]
        if self.dist.shape != (n_nodes, n_nodes):
            raise ValueError("Distance matrix must be square.")
        if len(self.demands) != n_nodes:
            raise ValueError("demands must have one entry per node (depot included).")
        if self.demands[0] != 0:
            raise ValueError("Depot demand (node 0) must be 0.")
        if self.n_vehicles < 1:
            raise ValueError("n_vehicles must be >= 1.")
        if self.capacity <= 0:
            raise ValueError("capacity must be > 0.")
        self.demands = [float(q) for q in self.demands]
        # Plain nested lists: element access is much faster than numpy scalars
        # inside the pure-Python loops of split / greedy.
        self.dist_list = self.dist.tolist()

    @property
    def n_customers(self) -> int:
        return self.dist.shape[0] - 1

    @property
    def total_demand(self) -> float:
        return float(sum(self.demands))

    def feasibility_problems(self) -> List[str]:
        """Reasons the instance cannot be solved at all (empty list = solvable)."""
        problems = []
        too_big = [i for i in range(1, self.n_customers + 1) if self.demands[i] > self.capacity]
        if too_big:
            problems.append(f"Stops {too_big} each exceed the vehicle capacity {self.capacity:g}.")
        if self.total_demand > self.capacity * self.n_vehicles + 1e-9:
            problems.append(
                f"Total demand {self.total_demand:g} exceeds fleet capacity "
                f"{self.n_vehicles} x {self.capacity:g} = {self.n_vehicles * self.capacity:g}."
            )
        return problems


@dataclass
class CVRPSolution:
    routes: List[List[int]]
    distance: float
    solver: str
    runtime_s: float = 0.0
    meta: Dict[str, object] = field(default_factory=dict)

    @property
    def vehicles_used(self) -> int:
        return sum(1 for r in self.routes if r)


# ── Distances ─────────────────────────────────────────────────────────────────

def route_distance(inst: CVRPInstance, route: Sequence[int]) -> float:
    if not route:
        return 0.0
    d = inst.dist_list
    total = d[0][route[0]] + d[route[-1]][0]
    for a, b in zip(route, route[1:]):
        total += d[a][b]
    return total


def solution_distance(inst: CVRPInstance, routes: Sequence[Sequence[int]]) -> float:
    return sum(route_distance(inst, r) for r in routes)


def route_load(inst: CVRPInstance, route: Sequence[int]) -> float:
    return sum(inst.demands[i] for i in route)


def validate_solution(inst: CVRPInstance, routes: Sequence[Sequence[int]], enforce_fleet: bool = True) -> List[str]:
    """Return a list of constraint violations (empty list = valid solution)."""
    errors = []
    visited = [c for r in routes for c in r]
    expected = set(range(1, inst.n_customers + 1))
    if len(visited) != len(set(visited)):
        errors.append("A customer is visited more than once.")
    if set(visited) != expected:
        missing = sorted(expected - set(visited))
        extra = sorted(set(visited) - expected)
        if missing:
            errors.append(f"Customers not visited: {missing}")
        if extra:
            errors.append(f"Unknown nodes in routes (the depot must not appear inside a route): {extra}")
    for k, r in enumerate(routes):
        load = route_load(inst, r)
        if load > inst.capacity + 1e-9:
            errors.append(f"Route {k} load {load:g} exceeds capacity {inst.capacity:g}.")
    used = sum(1 for r in routes if r)
    if enforce_fleet and used > inst.n_vehicles:
        errors.append(f"{used} routes used but only {inst.n_vehicles} vehicles available.")
    return errors


# ── Prins' split ──────────────────────────────────────────────────────────────

def _split_unlimited(inst: CVRPInstance, tour: Sequence[int]) -> Tuple[float, List[int]]:
    """Shortest-path split with an unlimited fleet. Returns (cost, predecessor array)."""
    d, q, cap = inst.dist_list, inst.demands, inst.capacity
    n = len(tour)
    V = [INF] * (n + 1)
    P = [0] * (n + 1)
    V[0] = 0.0
    for i in range(n):
        if V[i] == INF:
            continue
        load = 0.0
        cost = 0.0
        for j in range(i, n):
            cj = tour[j]
            load += q[cj]
            if load > cap + 1e-9:
                break
            if j == i:
                cost = d[0][cj] + d[cj][0]
            else:
                cprev = tour[j - 1]
                cost += d[cprev][cj] + d[cj][0] - d[cprev][0]
            if V[i] + cost < V[j + 1]:
                V[j + 1] = V[i] + cost
                P[j + 1] = i
    return V[n], P


def _split_limited(inst: CVRPInstance, tour: Sequence[int], max_routes: int) -> Tuple[float, List[List[int]]]:
    """Split using at most `max_routes` trips (Bellman layers k = 1..max_routes)."""
    d, q, cap = inst.dist_list, inst.demands, inst.capacity
    n = len(tour)
    V = [[INF] * (n + 1) for _ in range(max_routes + 1)]
    P = [[0] * (n + 1) for _ in range(max_routes + 1)]
    V[0][0] = 0.0
    for k in range(max_routes):
        Vk, Vk1, Pk1 = V[k], V[k + 1], P[k + 1]
        for i in range(n):
            if Vk[i] == INF:
                continue
            load = 0.0
            cost = 0.0
            for j in range(i, n):
                cj = tour[j]
                load += q[cj]
                if load > cap + 1e-9:
                    break
                if j == i:
                    cost = d[0][cj] + d[cj][0]
                else:
                    cprev = tour[j - 1]
                    cost += d[cprev][cj] + d[cj][0] - d[cprev][0]
                if Vk[i] + cost < Vk1[j + 1]:
                    Vk1[j + 1] = Vk[i] + cost
                    Pk1[j + 1] = i
    best_k = min(range(max_routes + 1), key=lambda k: V[k][n])
    if V[best_k][n] == INF:
        return INF, []
    routes = []
    j, k = n, best_k
    while j > 0:
        i = P[k][j]
        routes.append(list(tour[i:j]))
        j, k = i, k - 1
    routes.reverse()
    return V[best_k][n], routes


def split(inst: CVRPInstance, tour: Sequence[int], max_routes: Optional[int] = None) -> Tuple[float, List[List[int]]]:
    """
    Prins (2004) split: optimally cut a giant tour (a permutation of all
    customers) into capacity-feasible depot-to-depot trips, preserving order.
    It is a shortest path on an auxiliary DAG where arc (i, j) is the trip
    serving tour[i:j].

    With `max_routes`, at most that many trips are allowed. Returns
    (INF, []) if no feasible split exists under that limit.
    """
    if not tour:
        return 0.0, []
    cost, P = _split_unlimited(inst, tour)
    if cost == INF:
        return INF, []
    routes = []
    j = len(tour)
    while j > 0:
        i = P[j]
        routes.append(list(tour[i:j]))
        j = i
    routes.reverse()
    if max_routes is None or len(routes) <= max_routes:
        return cost, routes
    return _split_limited(inst, tour, max_routes)


# ── 2-opt (asymmetric-safe) ───────────────────────────────────────────────────

def two_opt(inst: CVRPInstance, route: Sequence[int], max_passes: int = 50) -> List[int]:
    """
    Intra-route 2-opt: reverse a segment whenever that shortens the route.

    Reversing route[i..j] changes the two boundary arcs AND the direction of
    every arc inside the segment. On an asymmetric matrix the internal cost is
    not preserved, so the gain is computed with forward/backward prefix sums:
        delta = d[a,s_j] + d[s_i,b] - d[a,s_i] - d[s_j,b] + (back(i,j) - fwd(i,j))
    All j for a given i are evaluated at once with numpy.
    """
    m = len(route)
    if m < 3:
        return list(route)
    D = inst.dist
    path = np.array([0, *route, 0], dtype=np.int64)
    for _ in range(max_passes):
        improved = False
        fwd = np.concatenate(([0.0], np.cumsum(D[path[:-1], path[1:]])))
        bwd = np.concatenate(([0.0], np.cumsum(D[path[1:], path[:-1]])))
        # Segment path[i..j], 1 <= i < j <= m; its neighbours are path[i-1] and path[j+1].
        for i in range(1, m):
            js = np.arange(i + 1, m + 1)
            a, si = path[i - 1], path[i]
            sj, b = path[js], path[js + 1]
            delta = (D[a, sj] + D[si, b] - D[a, si] - D[sj, b]
                     + (bwd[js] - bwd[i]) - (fwd[js] - fwd[i]))
            k = int(np.argmin(delta))
            if delta[k] < -1e-9:
                j = int(js[k])
                path[i:j + 1] = path[i:j + 1][::-1].copy()
                improved = True
                fwd = np.concatenate(([0.0], np.cumsum(D[path[:-1], path[1:]])))
                bwd = np.concatenate(([0.0], np.cumsum(D[path[1:], path[:-1]])))
        if not improved:
            break
    return path[1:-1].tolist()


def default_capacity(total_demand: float, n_vehicles: int) -> float:
    """Default vehicle capacity when the caller gives none: just enough for the fleet."""
    return float(max(1, math.ceil(total_demand / max(1, n_vehicles))))
