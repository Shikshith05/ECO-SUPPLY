"""
Fleet Optimizer service: parse a routing request, build the distance matrix,
run a CVRP solver, and report honest comparisons.

Request (all fields except `stops` optional):
    {
      "stops": [{"lat": 12.97, "lng": 77.59, "order_id": "A", "demand": 1}, ...],
      "depot": {"lat": 12.97, "lng": 77.59},     # default: the first stop
      "vehicle_count": 2,
      "capacity": 10,                              # default: ceil(total demand / vehicles)
      "time_limit_s": 5,                           # GA / OR-Tools search time
      "seed": 0                                    # GA random seed
    }

Distances come from the cached OSM road graph when available, otherwise
straight-line distance x a measured detour factor; the response says which
mode was used and why.

Savings are always measured on the SAME distance matrix against two real
baselines computed in the same request: greedy nearest-neighbour routes and
"order as received" routes. Fuel and CO2 are labelled estimates derived
linearly from distance with constants from config (routing section).
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import numpy as np

from backend.services import road_network
from backend.services.road_network import haversine_matrix, routing_config
from models.routing_models import genetic_algorithm, greedy, ortools_solver
from models.routing_models.cvrp import CVRPInstance, CVRPSolution, default_capacity, route_distance, route_load

SOLVERS = {
    "greedy": greedy.solve,
    "ga": genetic_algorithm.solve,
    "ortools": ortools_solver.solve,
}


class RoutingInputError(ValueError):
    """Invalid request: reported to the client as HTTP 400."""


# ── Road graph access ─────────────────────────────────────────────────────────

def load_bangalore_graph() -> Dict[str, object]:
    """Return the cached road network if it is on disk. Never downloads."""
    net = road_network.load_network()
    if net is None:
        return {"loaded": False, "graph": None, "reason": road_network.status().get("error")}
    return {"loaded": True, "graph": net, "reason": None}


def graph_status() -> Dict[str, object]:
    return road_network.status()


def build_distance_matrix(points: List[Tuple[float, float]]):
    """
    Return (matrix_km, info, path_fn). info holds the distance mode actually used;
    path_fn(i, j) returns the polyline between points i and j.
    """
    cfg = routing_config()
    graph = load_bangalore_graph()
    net = graph.get("graph")
    reason = graph.get("reason")
    if net is not None:
        matrix, _, snap, pred = net.distance_matrix(points)
        max_snap = float(cfg.get("max_snap_km", 2.0))
        worst = int(np.argmax(snap))
        if snap[worst] <= max_snap:
            info = {"distance_mode": "road_network", "distance_mode_reason": None,
                    "max_snap_km": round(float(snap[worst]), 3)}
            return matrix, info, lambda i, j: net.path_coords(pred, i, j)
        reason = (f"Point {worst} is {snap[worst]:.1f} km from the nearest road-graph node "
                  f"(limit {max_snap:g} km): outside the cached graph's coverage.")

    factor = float(cfg["haversine_detour_factor"])
    matrix = haversine_matrix(points) * factor
    info = {"distance_mode": "haversine_x_detour",
            "distance_mode_reason": reason or "Road graph unavailable.",
            "detour_factor": factor}
    return matrix, info, lambda i, j: [list(points[i]), list(points[j])]


# ── Request parsing ───────────────────────────────────────────────────────────

def _point(obj, label: str) -> Tuple[float, float]:
    try:
        lat, lng = float(obj["lat"]), float(obj["lng"])
    except (KeyError, TypeError, ValueError):
        raise RoutingInputError(f"{label} needs numeric 'lat' and 'lng'.")
    if not (-90 <= lat <= 90 and -180 <= lng <= 180) or math.isnan(lat) or math.isnan(lng):
        raise RoutingInputError(f"{label} has out-of-range coordinates.")
    return lat, lng


def _positive_int(value, label: str) -> int:
    try:
        f = float(value)
    except (TypeError, ValueError):
        raise RoutingInputError(f"{label} must be a positive integer.")
    if f <= 0 or abs(f - round(f)) > 1e-9:
        raise RoutingInputError(f"{label} must be a positive integer.")
    return int(round(f))


def parse_request(payload: dict) -> dict:
    cfg = routing_config()
    stops = payload.get("stops")
    if not isinstance(stops, list):
        raise RoutingInputError("'stops' must be a list of {lat, lng} objects.")
    notes: List[str] = []

    depot_obj = payload.get("depot")
    if depot_obj:
        depot = dict(depot_obj)
        customers = list(stops)
        depot_source = "request"
    else:
        if not stops:
            return {"empty": True}
        depot, customers = dict(stops[0]), list(stops[1:])
        depot_source = "first_stop"
        notes.append("No depot given: the first stop is used as the depot, and every route starts and ends there.")
    depot_pt = _point(depot, "depot")

    max_stops = int(cfg.get("max_stops", 150))
    if len(customers) > max_stops:
        raise RoutingInputError(f"At most {max_stops} stops per request.")
    points = [depot_pt] + [_point(s, f"stop {k + 1}") for k, s in enumerate(customers)]
    demands = [0] + [_positive_int(s.get("demand", 1), f"stop {k + 1} demand") for k, s in enumerate(customers)]

    vehicle_count = _positive_int(payload.get("vehicle_count", 1) or 1, "vehicle_count")
    max_vehicles = int(cfg.get("max_vehicles", 20))
    if vehicle_count > max_vehicles:
        raise RoutingInputError(f"At most {max_vehicles} vehicles.")
    if payload.get("capacity") not in (None, ""):
        capacity = _positive_int(payload["capacity"], "capacity")
        capacity_source = "request"
    else:
        capacity = int(default_capacity(sum(demands), vehicle_count))
        capacity_source = "default_total_demand_over_vehicles"
        if vehicle_count > 1:
            notes.append(f"No capacity given: each vehicle gets ceil(total demand / vehicles) = {capacity}.")

    if payload.get("weights"):
        notes.append("Cost weights are accepted for backward compatibility but ignored: the objective is "
                     "total distance, and the fuel/CO2 estimates are proportional to distance, so a weighted "
                     "sum of them would choose exactly the same routes.")

    return {"empty": False, "depot": depot, "depot_source": depot_source, "customers": customers,
            "points": points, "demands": demands, "vehicle_count": vehicle_count,
            "capacity": capacity, "capacity_source": capacity_source, "notes": notes}


# ── Metrics ───────────────────────────────────────────────────────────────────

def estimates(distance_km: float) -> Dict[str, object]:
    cfg = routing_config()
    l_per_km = float(cfg["fuel_litres_per_km"])
    co2_per_l = float(cfg["co2_kg_per_litre"])
    price = cfg.get("fuel_price_per_litre")
    litres = distance_km * l_per_km
    return {
        "fuel_litres_est": round(litres, 2),
        "co2_kg_est": round(litres * co2_per_l, 2),
        "fuel_cost_est": round(litres * float(price), 2) if price not in (None, "") else None,
        "estimate_basis": (f"Estimate, not measured: distance x {l_per_km:g} L/km x {co2_per_l:g} kg CO2/L "
                           "(constants in config.yaml, routing section)."),
    }


def _pct(saved: float, base: float) -> Optional[float]:
    return round(100.0 * saved / base, 2) if base > 0 else None


def _brief(sol: CVRPSolution, inst: CVRPInstance) -> dict:
    return {"distance_km": round(sol.distance, 3), "vehicles_used": sol.vehicles_used,
            "fleet_feasible": sol.vehicles_used <= inst.n_vehicles}


def _empty_response(solver: str) -> dict:
    return {"solver": solver, "routes": [], "depot": None, "distance_mode": None,
            "summary": {"distance_km": 0.0, "vehicles_used": 0, **estimates(0.0)},
            "comparison": {}, "notes": ["No stops given."]}


def plan_routes(payload: dict, solver: str = "ga") -> dict:
    if solver not in SOLVERS:
        raise RoutingInputError(f"Unknown solver {solver!r}; choose one of {sorted(SOLVERS)}.")
    req = parse_request(payload or {})
    if req.get("empty"):
        return _empty_response(solver)

    cfg = routing_config()
    matrix, dist_info, path_fn = build_distance_matrix(req["points"])
    inst = CVRPInstance(matrix, req["demands"], req["capacity"], req["vehicle_count"])
    problems = inst.feasibility_problems()
    if problems:
        raise RoutingInputError(" ".join(problems))

    max_tl = float(cfg.get("max_time_limit_s", 30))
    default_tl = float(cfg.get("default_time_limit_s", 5))
    try:
        time_limit = min(max_tl, max(0.5, float(payload.get("time_limit_s", default_tl))))
    except (TypeError, ValueError):
        raise RoutingInputError("time_limit_s must be a number.")
    try:
        seed = int(payload.get("seed", 0))
    except (TypeError, ValueError):
        raise RoutingInputError("seed must be an integer.")

    kwargs = {"seed": seed, "time_limit": time_limit}
    if solver == "ga":
        kwargs["params"] = cfg.get("ga_params") or {}
    if inst.n_customers == 0:
        result = CVRPSolution(routes=[], distance=0.0, solver=solver)
    else:
        result = SOLVERS[solver](inst, **kwargs)
    baseline_greedy = result if solver == "greedy" else greedy.solve(inst)
    baseline_order = greedy.solve_order_as_received(inst)

    customers = req["customers"]
    routes_out = []
    for k, route in enumerate(result.routes, start=1):
        nodes = [0, *route, 0]
        path: List[List[float]] = []
        for a, b in zip(nodes, nodes[1:]):
            leg = path_fn(a, b)
            path.extend(leg if not path else leg[1:])
        routes_out.append({
            "vehicle": k,
            "stops": [{**customers[c - 1], "stop_index": c} for c in route],
            "distance_km": round(route_distance(inst, route), 3),
            "load": route_load(inst, route),
            "capacity": inst.capacity,
            "path": path,
        })

    saved_g = baseline_greedy.distance - result.distance
    saved_o = baseline_order.distance - result.distance
    est = estimates(result.distance)
    est_g = estimates(baseline_greedy.distance)
    est_o = estimates(baseline_order.distance)
    notes = list(req["notes"])
    if result.vehicles_used > inst.n_vehicles:
        notes.append(f"{solver} needed {result.vehicles_used} routes but only {inst.n_vehicles} vehicles were "
                     "given; increase capacity or vehicles.")
    if dist_info["distance_mode"] != "road_network":
        notes.append("Distances are straight-line x detour factor (road graph not used): "
                     + str(dist_info.get("distance_mode_reason")))

    return {
        "solver": solver,
        **dist_info,
        "depot": {**req["depot"], "source": req["depot_source"]},
        "routes": routes_out,
        "summary": {
            "distance_km": round(result.distance, 3),
            "vehicles_used": result.vehicles_used,
            "vehicle_count": inst.n_vehicles,
            "capacity": inst.capacity,
            "capacity_source": req["capacity_source"],
            "total_demand": inst.total_demand,
            "stops": inst.n_customers,
            "runtime_s": round(result.runtime_s, 3),
            "time_limit_s": time_limit if solver != "greedy" else None,
            **est,
        },
        "comparison": {
            "greedy": _brief(baseline_greedy, inst),
            "order_as_received": _brief(baseline_order, inst),
            "saved_vs_greedy_km": round(saved_g, 3),
            "saved_vs_greedy_pct": _pct(saved_g, baseline_greedy.distance),
            "saved_vs_order_as_received_km": round(saved_o, 3),
            "saved_vs_order_as_received_pct": _pct(saved_o, baseline_order.distance),
            "co2_saved_vs_greedy_kg_est": round(est_g["co2_kg_est"] - est["co2_kg_est"], 2),
            "co2_saved_vs_order_as_received_kg_est": round(est_o["co2_kg_est"] - est["co2_kg_est"], 2),
        },
        "solver_stats": {k: v for k, v in result.meta.items() if k != "best_cost_history"},
        "notes": notes,
    }
