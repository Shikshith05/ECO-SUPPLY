"""
Emissions analysis and carbon footprint calculation.

This module evaluates environmental impact AFTER routing.
It does NOT influence routing decisions directly.

Responsibilities:
- Calculate total CO₂ emissions
- Compare emissions across routes
- Compute emission savings
- Track sustainability improvements
"""

from typing import Dict, List
from prediction.fuel_rules import FuelRulesEstimator

class EmissionsAnalyzer:
    """
    Performs CO₂ emission analysis for routing solutions.
    """

    def __init__(
        self,
        vehicle_type: str = "van",
        fuel_type: str = "petrol",
        base_mileage: float = 15.0
    ):
        self.vehicle_type = vehicle_type
        self.base_mileage = base_mileage
        self.estimator = FuelRulesEstimator(fuel_type=fuel_type)
    def calculate_total_emissions(
        self,
        distance_km: float,
        load_kg: float,
        area_type: str = "urban"
    ) -> float:
        """
        Calculate total CO₂ emissions (kg) for a route.
        """

        result = self.estimator.estimate_route_emissions(
            distance_km=distance_km,
            vehicle_type=self.vehicle_type,
            load_kg=load_kg,
            area_type=area_type
        )

        return result["co2_kg"]
    def compare_routes(
        self,
        baseline_distance: float,
        optimized_distance: float,
        load_kg: float,
        area_type: str = "urban"
    ) -> Dict[str, float]:
        """
        Compare baseline and optimized route emissions.
        """

        baseline_co2 = self.calculate_total_emissions(
            baseline_distance,
            load_kg,
            area_type
        )

        optimized_co2 = self.calculate_total_emissions(
            optimized_distance,
            load_kg,
            area_type
        )

        savings = baseline_co2 - optimized_co2
        savings_pct = (savings / baseline_co2) * 100 if baseline_co2 > 0 else 0

        return {
            "baseline_co2_kg": baseline_co2,
            "optimized_co2_kg": optimized_co2,
            "co2_saved_kg": savings,
            "co2_saved_percent": savings_pct
        }
    def track_emissions_over_time(
        self,
        distances: List[float],
        load_kg: float,
        area_type: str = "urban"
    ) -> List[float]:
        """
        Track CO₂ emissions across multiple routes or days.
        """

        emissions = []

        for d in distances:
            emissions.append(
                self.calculate_total_emissions(
                    distance_km=d,
                    load_kg=load_kg,
                    area_type=area_type
                )
            )

        return emissions
    def sustainability_metrics(
        self,
        baseline_distance: float,
        optimized_distance: float,
        load_kg: float,
        area_type: str = "urban"
    ) -> Dict[str, float]:
        """
        Compute high-level sustainability indicators.
        """

        comparison = self.compare_routes(
            baseline_distance,
            optimized_distance,
            load_kg,
            area_type
        )

        return {
            "co2_saved_kg": comparison["co2_saved_kg"],
            "co2_saved_percent": comparison["co2_saved_percent"],
            "emissions_intensity_reduction": (
                comparison["co2_saved_kg"] / baseline_distance
                if baseline_distance > 0 else 0
            )
        }
