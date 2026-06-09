"""Lightweight GA-inspired route optimizer for Fleet Optimizer."""

import math
import random
from typing import Dict, List


class RouteGeneticAlgorithm:
    def __init__(self, stops: List[Dict], vehicle_count: int = 1, weights: Dict[str, float] | None = None):
        self.stops = list(stops)
        self.vehicle_count = max(1, int(vehicle_count))
        self.weights = weights or {"alpha": 0.35, "beta": 0.25, "gamma": 0.20, "delta": 0.20}

    @staticmethod
    def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        radius = 6371.0
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return radius * c

    def _route_distance(self, route: List[Dict]) -> float:
        total = 0.0
        for a, b in zip(route, route[1:]):
            total += self._haversine_km(a["lat"], a["lng"], b["lat"], b["lng"])
        return total

    def _route_cost(self, route: List[Dict]) -> float:
        distance = self._route_distance(route)
        fuel = max(0.2, distance * 0.08)
        co2 = fuel * 2.31
        delay = 0.05 + (distance / 120.0) * 0.30 + (len(route) / 20.0) * 0.10
        return (self.weights.get("alpha", 0.35) * distance) + (self.weights.get("beta", 0.25) * fuel) + (self.weights.get("gamma", 0.20) * co2) + (self.weights.get("delta", 0.20) * delay * 10)

    def _shuffle(self, route: List[Dict]) -> List[Dict]:
        mutated = list(route)
        if len(mutated) > 2:
            i, j = random.sample(range(len(mutated)), 2)
            mutated[i], mutated[j] = mutated[j], mutated[i]
        return mutated

    def run(self) -> Dict[str, object]:
        base_route = list(self.stops)
        random.shuffle(base_route)
        best_route = base_route
        best_cost = self._route_cost(best_route)

        for _ in range(60):
            candidate = self._shuffle(best_route)
            candidate_cost = self._route_cost(candidate)
            if candidate_cost < best_cost:
                best_route = candidate
                best_cost = candidate_cost

        # Split into vehicle buckets with a simple balanced assignment.
        chunk_size = max(1, math.ceil(len(best_route) / self.vehicle_count))
        routes = []
        for idx in range(0, len(best_route), chunk_size):
            part = best_route[idx:idx + chunk_size]
            if not part:
                continue
            routes.append({"vehicle": len(routes) + 1, "stops": part, "score": round(self._route_cost(part), 3)})

        return {"routes": routes, "score": round(best_cost, 3)}
