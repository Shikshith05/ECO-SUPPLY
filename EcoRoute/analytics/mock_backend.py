"""
Mock backend for testing - provides working optimization functions
without requiring full Bangalore graph download
"""

from typing import Dict, List, Any
import random


class MockBaselineComparison:
    """Mock implementation for testing"""
    
    def __init__(self, graph=None, delay_model=None):
        self.graph = graph
        self.delay_model = delay_model
    
    def run_comparison(
        self,
        start_node,
        delivery_nodes,
        load_kg: float = 40.0,
        area_type: str = "urban",
        hour_of_day: int = 9,
        ga_generations: int = 100
    ) -> Dict[str, Any]:
        """
        Run complete comparison with mock data.
        Returns realistic results for demonstration.
        """
        
        # Generate base metrics based on number of stops
        num_stops = len(delivery_nodes)
        base_distance = 10 + num_stops * 5 + random.uniform(-2, 2)
        
        # Baseline: longest (pure distance)
        baseline_distance = base_distance * (1.1 + random.uniform(0, 0.1))
        baseline_fuel = baseline_distance * 0.12
        baseline_co2 = baseline_fuel * 2.31
        baseline_delay = 5 + num_stops * 2 + random.uniform(-1, 1)
        baseline_cost = (
            baseline_distance * 0.25 +
            baseline_fuel * 0.25 +
            baseline_co2 * 0.30 +
            baseline_delay * 0.20
        ) / 100
        
        # Greedy: medium (balanced)
        greedy_distance = base_distance * (1.05 + random.uniform(0, 0.05))
        greedy_fuel = greedy_distance * 0.12
        greedy_co2 = greedy_fuel * 2.31
        greedy_delay = 5 + num_stops * 2 * 0.9 + random.uniform(-0.5, 0.5)
        greedy_cost = (
            greedy_distance * 0.25 +
            greedy_fuel * 0.25 +
            greedy_co2 * 0.30 +
            greedy_delay * 0.20
        ) / 100
        
        # Optimized GA: shortest (best)
        optimized_distance = base_distance * (0.95 + random.uniform(0, 0.04))
        optimized_fuel = optimized_distance * 0.12
        optimized_co2 = optimized_fuel * 2.31
        optimized_delay = 5 + num_stops * 2 * 0.8 + random.uniform(-0.5, 0.5)
        optimized_cost = (
            optimized_distance * 0.25 +
            optimized_fuel * 0.25 +
            optimized_co2 * 0.30 +
            optimized_delay * 0.20
        ) / 100
        
        # Calculate improvements
        improvements = {}
        for metric_key, baseline_val, optimized_val in [
            ("distance_km", baseline_distance, optimized_distance),
            ("fuel_liters", baseline_fuel, optimized_fuel),
            ("co2_kg", baseline_co2, optimized_co2),
            ("delay_minutes", baseline_delay, optimized_delay),
            ("total_cost", baseline_cost, optimized_cost),
        ]:
            if baseline_val > 0:
                improvement = ((baseline_val - optimized_val) / baseline_val) * 100
                improvements[metric_key] = round(max(0, improvement), 2)
            else:
                improvements[metric_key] = 0.0
        
        return {
            "baseline": {
                "distance_km": round(baseline_distance, 2),
                "fuel_liters": round(baseline_fuel, 2),
                "co2_kg": round(baseline_co2, 2),
                "delay_minutes": round(baseline_delay, 1),
                "total_cost": round(baseline_cost, 4),
            },
            "greedy": {
                "distance_km": round(greedy_distance, 2),
                "fuel_liters": round(greedy_fuel, 2),
                "co2_kg": round(greedy_co2, 2),
                "delay_minutes": round(greedy_delay, 1),
                "total_cost": round(greedy_cost, 4),
            },
            "optimized": {
                "distance_km": round(optimized_distance, 2),
                "fuel_liters": round(optimized_fuel, 2),
                "co2_kg": round(optimized_co2, 2),
                "delay_minutes": round(optimized_delay, 1),
                "total_cost": round(optimized_cost, 4),
            },
            "improvements": improvements,
        }


class MockDelayModel:
    """Mock delay prediction"""
    
    def predict(self, *args, **kwargs):
        return random.uniform(5, 15)
