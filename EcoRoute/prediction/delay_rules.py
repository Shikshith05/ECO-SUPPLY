"""
Rule-based delay estimation for deliveries.

Estimates average travel delay based on:
- Road type (from OSM)
- Distance
- Time of day (traffic patterns)
- Weekday vs weekend

This module is used to:
1. Generate synthetic traffic data
2. Act as a fallback if ML model is unavailable
"""

import random
import os
import pandas as pd


class DelayRulesEstimator:
    """
    Rule-based delay estimator.
    """

    # Base free-flow speeds (km/h)
    ROAD_BASE_SPEED = {
        "motorway": 60,
        "primary": 45,
        "secondary": 35,
        "tertiary": 30,
        "residential": 20,
        "service": 15,
        "unclassified": 25
    }

    # Time-of-day traffic multipliers (urban – Bangalore style)
    TIME_MULTIPLIERS = {
        "early_morning": (0, 7, 0.85),
        "morning_peak":  (7, 10, 1.4),
        "midday":        (10, 16, 1.1),
        "evening_peak":  (17, 21, 1.6),
        "night":         (21, 24, 0.9)
    }

    def __init__(self, is_weekend: bool = False):
        self.is_weekend = is_weekend

    def _get_time_multiplier(self, hour: int) -> float:
        for _, (start, end, multiplier) in self.TIME_MULTIPLIERS.items():
            if start <= hour < end:
                return multiplier
        return 1.1

    def estimate_delay(
        self,
        road_type: str,
        length_m: float,
        hour_of_day: int
    ) -> dict:
        """
        Estimate delay for a single road segment.
        """

        base_speed = self.ROAD_BASE_SPEED.get(road_type, 25)

        # Free-flow time (seconds)
        base_time_sec = (length_m / 1000) / base_speed * 3600

        # Traffic effect
        time_multiplier = self._get_time_multiplier(hour_of_day)

        # Weekend traffic adjustment
        if self.is_weekend:
            time_multiplier *= 0.85

        # Small randomness for realism
        noise = random.uniform(0.9, 1.1)

        observed_time_sec = base_time_sec * time_multiplier * noise
        delay_sec = observed_time_sec - base_time_sec

        return {
            "base_time_sec": round(base_time_sec, 2),
            "observed_time_sec": round(observed_time_sec, 2),
            "delay_sec": round(delay_sec, 2)
        }

    def estimate_batch(self, records: list) -> pd.DataFrame:
        """
        Batch delay estimation.
        """

        output = []

        for r in records:
            delay_info = self.estimate_delay(
                r["road_type"],
                r["length_m"],
                r["hour_of_day"]
            )

            output.append({**r, **delay_info})

        return pd.DataFrame(output)


# --------------------------------------------------
# Standalone usage: synthetic data generation
# --------------------------------------------------
if __name__ == "__main__":

    OUTPUT_DIR = os.path.join("data", "processed")
    OUTPUT_FILE = os.path.join(OUTPUT_DIR, "synthetic_delay_data.csv")

    # Ensure directory exists
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    estimator = DelayRulesEstimator(is_weekend=False)

    road_types = list(DelayRulesEstimator.ROAD_BASE_SPEED.keys())
    samples = []

    for _ in range(5000):
        samples.append({
            "road_type": random.choice(road_types),
            "length_m": random.uniform(50, 1500),
            "hour_of_day": random.randint(0, 23)
        })

    df = estimator.estimate_batch(samples)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"✅ Synthetic delay data generated at: {OUTPUT_FILE}")

