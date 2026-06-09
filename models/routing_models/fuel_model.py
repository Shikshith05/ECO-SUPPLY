"""Simple fuel estimation model wrapper for route optimization."""

import os
from typing import Any

try:
    import joblib
except Exception:  # pragma: no cover
    joblib = None


class RouteFuelModel:
    def __init__(self, model_path: str | None = None):
        self.model_path = model_path or os.path.join("saved_models", "routing_fuel_model.pkl")
        self.model = None
        self._load()

    def _load(self) -> None:
        if joblib is None:
            return
        try:
            if os.path.exists(self.model_path):
                self.model = joblib.load(self.model_path)
        except Exception:
            self.model = None

    def estimate_fuel(self, distance_km: float, vehicle_count: int = 1) -> float:
        if self.model is not None:
            try:
                return float(self.model.predict([[distance_km, vehicle_count]])[0])
            except Exception:
                pass

        return max(0.2, distance_km * 0.08 * (1.0 + 0.03 * vehicle_count))
