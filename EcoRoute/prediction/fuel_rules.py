"""
Rule-based fuel consumption estimation.
Estimates fuel consumption based on distance, vehicle type, and driving conditions.

TODO:
- Implement FuelRulesEstimator class
- Calculate base fuel consumption by distance
- Add area type multipliers (urban/suburban/highway)
- Factor in load weight
- Support different vehicle types
- Calculate CO2 emissions from fuel consumption
- Implement batch processing
"""

# TODO: Import required libraries
# TODO: FuelRulesEstimator class
# TODO: estimate_fuel() method
# TODO: estimate_co2() method
# TODO: Batch estimation support

"""
Rule-based fuel consumption estimation.

Estimates fuel consumption based on distance, vehicle type,
load weight, and driving conditions (area type).

Supports:
- Multiple vehicle types
- Area-based multipliers
- CO₂ emission estimation
- Batch processing
"""

from typing import List, Dict


class FuelRulesEstimator:
    """
    Rule-based fuel consumption and CO₂ estimation.
    """

    # ----------------------------
    # DEFAULT CONFIGURATIONS
    # ----------------------------

    VEHICLE_MILEAGE = {
        "bike": 40.0,      # km/l
        "car": 15.0,
        "van": 10.0
    }

    AREA_MULTIPLIERS = {
        "urban": 1.2,       # more stop-go
        "suburban": 1.0,
        "highway": 0.85
    }

    EMISSION_FACTORS = {
        "petrol": 2.31,     # kg CO₂ per liter
        "diesel": 2.68
    }

    LOAD_PENALTY = 0.0004  # mileage reduction per kg

    # ----------------------------
    # INITIALIZATION
    # ----------------------------

    def __init__(
        self,
        fuel_type: str = "petrol"
    ):
        if fuel_type not in self.EMISSION_FACTORS:
            raise ValueError("Unsupported fuel type")

        self.fuel_type = fuel_type

    # ----------------------------
    # CORE FUEL ESTIMATION
    # ----------------------------

    def estimate_fuel(
        self,
        distance_km: float,
        vehicle_type: str,
        load_kg: float = 0.0,
        area_type: str = "urban"
    ) -> float:
        """
        Estimate fuel consumption in liters.
        """

        if vehicle_type not in self.VEHICLE_MILEAGE:
            raise ValueError("Unsupported vehicle type")

        if area_type not in self.AREA_MULTIPLIERS:
            raise ValueError("Unsupported area type")

        # Base mileage
        mileage = self.VEHICLE_MILEAGE[vehicle_type]

        # Apply load penalty
        mileage -= self.LOAD_PENALTY * load_kg

        # Prevent invalid mileage
        mileage = max(mileage, 1.0)

        # Apply area multiplier
        adjusted_distance = distance_km * self.AREA_MULTIPLIERS[area_type]

        fuel_used = adjusted_distance / mileage
        return fuel_used

    # ----------------------------
    # CO₂ ESTIMATION
    # ----------------------------

    def estimate_co2(
        self,
        fuel_liters: float
    ) -> float:
        """
        Convert fuel consumption to CO₂ emissions (kg).
        """

        return fuel_liters * self.EMISSION_FACTORS[self.fuel_type]

    # ----------------------------
    # FULL PIPELINE (OPTIONAL)
    # ----------------------------

    def estimate_route_emissions(
        self,
        distance_km: float,
        vehicle_type: str,
        load_kg: float = 0.0,
        area_type: str = "urban"
    ) -> Dict[str, float]:
        """
        Estimate fuel and CO₂ for a route.
        """

        fuel = self.estimate_fuel(
            distance_km,
            vehicle_type,
            load_kg,
            area_type
        )

        co2 = self.estimate_co2(fuel)

        return {
            "fuel_liters": fuel,
            "co2_kg": co2
        }

    # ----------------------------
    # BATCH PROCESSING
    # ----------------------------

    def batch_estimate(
        self,
        routes: List[Dict]
    ) -> List[Dict]:
        """
        Batch estimation for multiple routes.
        Each route dict must contain:
        - distance_km
        - vehicle_type
        - load_kg
        - area_type
        """

        results = []

        for route in routes:
            result = self.estimate_route_emissions(
                distance_km=route["distance_km"],
                vehicle_type=route["vehicle_type"],
                load_kg=route.get("load_kg", 0.0),
                area_type=route.get("area_type", "urban")
            )
            results.append(result)

        return results
