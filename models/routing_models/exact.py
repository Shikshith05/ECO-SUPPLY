"""
Exact CVRP solver for small instances (default: up to 8 stops).

1. Held-Karp dynamic programming gives, for every subset S of customers, the
   shortest depot -> S -> depot route (directed distances, so asymmetric
   matrices are fine): O(2^n * n^2).
2. A set-partition DP chooses at most K disjoint, capacity-feasible subsets
   that cover all customers with minimum total route length: O(3^n * K).

For n = 8 that is 256 subsets and 6,561 subset/sub-subset pairs, i.e.
milliseconds, and the result is provably optimal, so heuristics are pointless
at this size.
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from models.routing_models.cvrp import INF, CVRPInstance, CVRPSolution, solution_distance

MAX_EXACT_STOPS = 12   # hard ceiling: 3^12 x K partition steps is still fine, 2^n x n^2 too


def _best_routes_per_subset(inst: CVRPInstance) -> Tuple[List[float], List[Optional[List[int]]]]:
    n, d = inst.n_customers, inst.dist_list
    full = 1 << n
    # dp[mask][j]: shortest path depot -> (all of mask) ending at customer j (j in mask, 0-based)
    dp = [[INF] * n for _ in range(full)]
    parent = [[-1] * n for _ in range(full)]
    for j in range(n):
        dp[1 << j][j] = d[0][j + 1]
    for mask in range(1, full):
        row = dp[mask]
        for j in range(n):
            cost = row[j]
            if cost == INF or not (mask >> j) & 1:
                continue
            for k in range(n):
                if (mask >> k) & 1:
                    continue
                nm = mask | (1 << k)
                c = cost + d[j + 1][k + 1]
                if c < dp[nm][k]:
                    dp[nm][k] = c
                    parent[nm][k] = j
    route_cost = [INF] * full
    route_order: List[Optional[List[int]]] = [None] * full
    route_cost[0] = 0.0
    route_order[0] = []
    for mask in range(1, full):
        best_j, best = -1, INF
        for j in range(n):
            if (mask >> j) & 1 and dp[mask][j] + d[j + 1][0] < best:
                best, best_j = dp[mask][j] + d[j + 1][0], j
        route_cost[mask] = best
        order, m, j = [], mask, best_j
        while j != -1:
            order.append(j + 1)
            pj = parent[m][j]
            m ^= 1 << j
            j = pj
        route_order[mask] = order[::-1]
    return route_cost, route_order


def solve(inst: CVRPInstance, *, seed: int = 0, time_limit: Optional[float] = None, **_) -> CVRPSolution:
    t0 = time.perf_counter()
    n = inst.n_customers
    if n > MAX_EXACT_STOPS:
        raise ValueError(f"Exact solver supports at most {MAX_EXACT_STOPS} stops (got {n}).")
    if n == 0:
        return CVRPSolution(routes=[], distance=0.0, solver="exact", runtime_s=0.0, meta={"exact": True})
    q, cap, K = inst.demands, inst.capacity, inst.n_vehicles
    full = 1 << n
    load = [0.0] * full
    for mask in range(1, full):
        low = (mask & -mask).bit_length() - 1
        load[mask] = load[mask & (mask - 1)] + q[low + 1]
    route_cost, route_order = _best_routes_per_subset(inst)

    # best[k][mask]: min cost to serve exactly `mask` with k routes
    best = [[INF] * full for _ in range(K + 1)]
    choice: Dict[Tuple[int, int], int] = {}
    best[0][0] = 0.0
    for k in range(1, K + 1):
        prev, cur = best[k - 1], best[k]
        for mask in range(1, full):
            low_bit = mask & -mask
            sub = mask
            while sub:
                # the route containing the lowest customer avoids counting partitions twice
                if sub & low_bit and load[sub] <= cap + 1e-9:
                    c = prev[mask ^ sub] + route_cost[sub]
                    if c < cur[mask]:
                        cur[mask] = c
                        choice[(k, mask)] = sub
                sub = (sub - 1) & mask
    k_best = min(range(1, K + 1), key=lambda k: best[k][full - 1])
    if best[k_best][full - 1] == INF:
        raise ValueError("No feasible solution: capacity/fleet too small.")
    routes, mask, k = [], full - 1, k_best
    while mask:
        sub = choice[(k, mask)]
        routes.append(route_order[sub])
        mask ^= sub
        k -= 1
    return CVRPSolution(routes=routes, distance=solution_distance(inst, routes), solver="exact",
                        runtime_s=time.perf_counter() - t0,
                        meta={"exact": True, "method": "Held-Karp per subset + set-partition DP",
                              "fleet_feasible": True})
