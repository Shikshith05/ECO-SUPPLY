"""Simple delay-risk model wrapper for routing optimization."""

import math
import os
from typing import Dict, Any

try:
    import joblib
except Exception:  # pragma: no cover
    joblib = None


class RouteDelayModel:
    def __init__(self, model_path: str | None = None):
        self.model_path = model_path or os.path.join("saved_models", "routing_delay_model.pkl")
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

    def estimate_delay_risk(self, distance_km: float, stop_count: int, vehicle_count: int = 1) -> float:
        if self.model is not None:
            try:
                return float(self.model.predict([[distance_km, stop_count, vehicle_count]])[0])
            except Exception:
                pass

        base = min(0.95, 0.05 + (distance_km / 120.0) * 0.30 + (stop_count / 20.0) * 0.10)
        congestion = 0.05 if vehicle_count <= 2 else 0.10
        return round(min(0.98, base + congestion), 3)
