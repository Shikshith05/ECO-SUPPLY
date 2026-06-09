"""
Multi-objective cost function for route optimization.
Combines distance, fuel consumption, CO2 emissions, and delay penalties.

Cost = α × distance + β × fuel + γ × CO2 + δ × delay

TODO:
- Implement cost calculation function
- Add weight normalization
- Support different optimization objectives
- Add constraint handling
"""

# TODO: Define cost function class
# TODO: Implement individual cost components
# TODO: Add weight configuration support

"""
Multi-objective cost function with normalization.

Cost = α·distance + β·fuel + γ·CO₂ + δ·delay
All components are min-max normalized.
"""

import yaml


class CostFunction:
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, "r") as f:
            cfg = yaml.safe_load(f)

        self.weights = cfg["cost_function"]["weights"]
        self.bounds = cfg["cost_function"]["bounds"]

    @staticmethod
    def _normalize(value: float, min_v: float, max_v: float) -> float:
        """
        Min-max normalization to [0, 1].
        """
        if max_v == min_v:
            return 0.0
        return (value - min_v) / (max_v - min_v)

    def compute_cost(self, metrics: dict) -> float:
        """
        Compute total normalized cost for a route.

        metrics must contain:
        - distance (km)
        - fuel (liters)
        - co2 (kg)
        - delay (minutes)
        """

        d_norm = self._normalize(
            metrics["distance"], *self.bounds["distance"]
        )
        f_norm = self._normalize(
            metrics["fuel"], *self.bounds["fuel"]
        )
        c_norm = self._normalize(
            metrics["co2"], *self.bounds["co2"]
        )
        t_norm = self._normalize(
            metrics["delay"], *self.bounds["delay"]
        )

        cost = (
            self.weights["distance"] * d_norm +
            self.weights["fuel"] * f_norm +
            self.weights["co2"] * c_norm +
            self.weights["delay"] * t_norm
        )

        return cost
