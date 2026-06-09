"""Routing service for Fleet Optimizer."""

import math
import os
import sys
from typing import Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

try:
    import osmnx as ox
except Exception:  # pragma: no cover
    ox = None

from models.routing_models.delay_model import RouteDelayModel
from models.routing_models.fuel_model import RouteFuelModel
from models.routing_models.genetic_algorithm import RouteGeneticAlgorithm

_GRAPH_CACHE = None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius * c


def load_bangalore_graph() -> Dict[str, object]:
    """Load the OSM road graph once and cache it in memory."""
    global _GRAPH_CACHE
    if _GRAPH_CACHE is not None:
        return {"loaded": True, "cached": True, "graph": _GRAPH_CACHE}

    if ox is None:
        return {"loaded": False, "cached": False, "graph": None, "reason": "osmnx is not installed"}

    try:
        graph = ox.graph_from_place("Bangalore, India", network_type="drive", simplify=True)
        graph = ox.project_graph(graph)
        _GRAPH_CACHE = graph
        return {"loaded": True, "cached": False, "graph": graph}
    except Exception as exc:
        return {"loaded": False, "cached": False, "graph": None, "reason": str(exc)}


def graph_status() -> Dict[str, object]:
    return {"loaded": _GRAPH_CACHE is not None, "cached": _GRAPH_CACHE is not None}


def _route_distance(stops: List[Dict]) -> float:
    total = 0.0
    for a, b in zip(stops, stops[1:]):
        total += _haversine_km(a["lat"], a["lng"], b["lat"], b["lng"])
    return total


def _greedy_route(stops: List[Dict]) -> List[Dict]:
    remaining = list(stops)
    start = remaining.pop(0)
    ordered = [start]
    current = start

    while remaining:
        next_stop = min(remaining, key=lambda item: _haversine_km(current["lat"], current["lng"], item["lat"], item["lng"]))
        ordered.append(next_stop)
        remaining.remove(next_stop)
        current = next_stop

    return ordered


def greedy_estimate(stops: List[Dict], vehicle_count: int = 1, weights: Dict[str, float] | None = None) -> Dict[str, object]:
    """Fast greedy estimate for instant UI feedback."""
    weights = weights or {"alpha": 0.35, "beta": 0.25, "gamma": 0.20, "delta": 0.20}
    delay_model = RouteDelayModel()
    fuel_model = RouteFuelModel()

    if not stops:
        return {"routes": [], "summary": {"distance_km": 0.0, "fuel_cost": 0.0, "co2_kg": 0.0, "delay_risk": 0.0}}

    ordered = _greedy_route(stops)
    distance = _route_distance(ordered)
    fuel = fuel_model.estimate_fuel(distance, vehicle_count)
    co2 = fuel * 2.31
    delay_risk = delay_model.estimate_delay_risk(distance, len(ordered), vehicle_count)

    cost = (weights.get("alpha", 0.35) * distance) + (weights.get("beta", 0.25) * fuel) + (weights.get("gamma", 0.20) * co2) + (weights.get("delta", 0.20) * delay_risk * 10)

    return {
        "routes": [{"vehicle": 1, "stops": ordered, "distance_km": round(distance, 2), "fuel_liters": round(fuel, 2), "co2_kg": round(co2, 2), "delay_risk": round(delay_risk, 3), "score": round(cost, 3)}],
        "summary": {"distance_km": round(distance, 2), "fuel_cost": round(fuel * 1.8, 2), "co2_kg": round(co2, 2), "delay_risk": round(delay_risk, 3), "baseline_co2_saved": 0.0},
    }


def optimize_routes(stops: List[Dict], vehicle_count: int = 1, weights: Dict[str, float] | None = None) -> Dict[str, object]:
    """Use a lightweight GA-inspired search to improve vehicle routing."""
    weights = weights or {"alpha": 0.35, "beta": 0.25, "gamma": 0.20, "delta": 0.20}
    delay_model = RouteDelayModel()
    fuel_model = RouteFuelModel()

    if not stops:
        return {"routes": [], "summary": {"distance_km": 0.0, "fuel_cost": 0.0, "co2_kg": 0.0, "delay_risk": 0.0, "baseline_co2_saved": 0.0}}

    ga = RouteGeneticAlgorithm(stops, vehicle_count=vehicle_count, weights=weights)
    candidate = ga.run()
    total_distance = 0.0
    total_fuel = 0.0
    total_co2 = 0.0
    total_delay = 0.0
    baseline_distance = 0.0

    for route in candidate["routes"]:
        distance = _route_distance(route["stops"])
        fuel = fuel_model.estimate_fuel(distance, len(candidate["routes"]))
        co2 = fuel * 2.31
        delay = delay_model.estimate_delay_risk(distance, len(route["stops"]), len(candidate["routes"]))
        total_distance += distance
        total_fuel += fuel
        total_co2 += co2
        total_delay += delay
        baseline_distance += distance * 1.08

    baseline_co2 = (total_fuel * 1.08) * 2.31
    co2_saved = max(0.0, baseline_co2 - total_co2)

    return {
        "routes": candidate["routes"],
        "summary": {
            "distance_km": round(total_distance, 2),
            "fuel_cost": round(total_fuel * 1.8, 2),
            "co2_kg": round(total_co2, 2),
            "delay_risk": round(total_delay / max(1, len(candidate["routes"])), 3),
            "baseline_co2_saved": round(co2_saved, 2),
        },
    }
