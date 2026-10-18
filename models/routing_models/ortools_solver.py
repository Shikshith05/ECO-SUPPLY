"""
Google OR-Tools routing solver: the strong reference for the CVRP.

Setup: K vehicles starting and ending at node 0, one capacity dimension,
PATH_CHEAPEST_ARC for the first solution, then Guided Local Search until the
time limit. OR-Tools needs integer arc costs, so float distances are scaled
(km -> metres by default) and the reported distance is recomputed on the
original float matrix so every solver is scored the same way.

GLS is time-bounded, so results can vary slightly between runs on different
machines; `seed` is accepted for interface compatibility only.
"""

from __future__ import annotations

import time
from typing import Optional

import numpy as np
from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from models.routing_models.cvrp import CVRPInstance, CVRPSolution, solution_distance


def _cost_scale(dist: np.ndarray) -> int:
    """Integer matrices (e.g. CVRPLIB) are used as-is; float km are scaled to metres."""
    return 1 if np.allclose(dist, np.round(dist)) else 1000


def solve(inst: CVRPInstance, *, seed: int = 0, time_limit: Optional[float] = 5.0, **_) -> CVRPSolution:
    t0 = time.perf_counter()
    n_nodes = inst.n_customers + 1
    if inst.n_customers == 0:
        return CVRPSolution(routes=[], distance=0.0, solver="ortools", runtime_s=0.0)

    scale = _cost_scale(inst.dist)
    int_dist = np.round(inst.dist * scale).astype(np.int64).tolist()
    demands = [int(round(q)) for q in inst.demands]
    if any(abs(a - b) > 1e-9 for a, b in zip(demands, inst.demands)):
        raise ValueError("OR-Tools solver requires integer demands.")
    capacity = int(inst.capacity)

    manager = pywrapcp.RoutingIndexManager(n_nodes, inst.n_vehicles, 0)
    routing = pywrapcp.RoutingModel(manager)

    def distance_cb(from_index, to_index):
        return int_dist[manager.IndexToNode(from_index)][manager.IndexToNode(to_index)]

    transit = routing.RegisterTransitCallback(distance_cb)
    routing.SetArcCostEvaluatorOfAllVehicles(transit)

    def demand_cb(from_index):
        return demands[manager.IndexToNode(from_index)]

    demand_idx = routing.RegisterUnaryTransitCallback(demand_cb)
    routing.AddDimensionWithVehicleCapacity(demand_idx, 0, [capacity] * inst.n_vehicles, True, "Capacity")

    search = pywrapcp.DefaultRoutingSearchParameters()
    search.first_solution_strategy = routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
    search.local_search_metaheuristic = routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
    limit = max(1.0, float(time_limit if time_limit is not None else 5.0))
    search.time_limit.seconds = int(limit)
    search.time_limit.nanos = int((limit - int(limit)) * 1e9)

    assignment = routing.SolveWithParameters(search)
    if assignment is None:
        raise RuntimeError("OR-Tools found no feasible solution within the time limit.")

    routes = []
    for v in range(inst.n_vehicles):
        index = routing.Start(v)
        route = []
        while not routing.IsEnd(index):
            node = manager.IndexToNode(index)
            if node != 0:
                route.append(node)
            index = assignment.Value(routing.NextVar(index))
        if route:
            routes.append(route)

    return CVRPSolution(
        routes=routes,
        distance=solution_distance(inst, routes),
        solver="ortools",
        runtime_s=time.perf_counter() - t0,
        meta={"cost_scale": scale, "time_limit_s": limit, "fleet_feasible": True},
    )
