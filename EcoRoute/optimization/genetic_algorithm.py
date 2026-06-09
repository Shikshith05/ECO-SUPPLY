"""
Genetic Algorithm for route optimization.

Optimizes the visiting order of delivery locations
to minimize a multi-objective cost function.

Uses:
- CostFunction (distance, fuel, CO₂, delay)
"""

import random
import os
from typing import List
from optimization.cost_function import CostFunction
from prediction.delay_model import DelayMLModel
from prediction.delay_rules import DelayRulesEstimator


class GeneticAlgorithm:
    """
    Genetic Algorithm for route optimization.
    """

    def __init__(
        self,
        locations: List[str],
        distance_matrix: dict,
        cost_function: CostFunction,
        delay_model=None,
        hour_of_day: int = 9,
        population_size: int = 50,
        generations: int = 100,
        crossover_rate: float = 0.8,
        mutation_rate: float = 0.2,
        elite_size: int = 2
    ):
        """
        Args:
            locations: List of delivery locations (excluding depot)
            distance_matrix: dict[(i, j)] -> distance in km
            cost_function: CostFunction instance
            delay_model: DelayMLModel or DelayRulesEstimator instance
            hour_of_day: Hour of day for delay prediction (0-23)
        """

        self.locations = locations
        self.distance_matrix = distance_matrix
        self.cost_function = cost_function
        self.hour_of_day = hour_of_day

        self.population_size = population_size
        self.generations = generations
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.elite_size = elite_size

        self.population = []
        
        # Initialize delay model
        if delay_model is not None:
            self.delay_model = delay_model
        else:
            # Try to load trained model, fallback to rules-based
            model_path = os.path.join("data", "models")
            if os.path.exists(os.path.join(model_path, "delay_random_forest.pkl")):
                try:
                    self.delay_model = DelayMLModel(model_type="random_forest")
                    self.delay_model.load(model_path, "delay_random_forest")
                except Exception:
                    self.delay_model = DelayRulesEstimator(is_weekend=False)
            else:
                self.delay_model = DelayRulesEstimator(is_weekend=False)

    # --------------------------------------------------
    # POPULATION INITIALIZATION
    # --------------------------------------------------

    def _create_individual(self) -> List[str]:
        """
        Create a random route (permutation of locations).
        """
        route = self.locations[:]
        random.shuffle(route)
        return route

    def _initialize_population(self):
        self.population = [
            self._create_individual()
            for _ in range(self.population_size)
        ]

    # --------------------------------------------------
    # FITNESS EVALUATION
    # --------------------------------------------------

    def _evaluate_route(self, route: List[str]) -> float:
        """
        Compute fitness (lower is better).
        """

        total_distance = 0.0
        total_delay_minutes = 0.0

        # Compute total distance and delay
        for i in range(len(route) - 1):
            segment_distance = self.distance_matrix[
                (route[i], route[i + 1])
            ]
            total_distance += segment_distance
            
            # Predict delay for this segment
            # Estimate average road type and segment length
            segment_length_m = segment_distance * 1000
            road_type = 'primary'  # Default assumption for GA
            
            if isinstance(self.delay_model, DelayMLModel):
                # Use ML model
                delay_sec = self.delay_model.predict_single(
                    road_type=road_type,
                    length_m=segment_length_m,
                    hour_of_day=self.hour_of_day
                )
            else:
                # Use rules-based estimator
                delay_data = self.delay_model.estimate_delay(
                    road_type=road_type,
                    length_m=segment_length_m,
                    hour_of_day=self.hour_of_day
                )
                delay_sec = delay_data['delay_sec']
            
            total_delay_minutes += delay_sec / 60.0

        metrics = {
            "distance": total_distance,
            "fuel": total_distance * 0.08,   # approx fuel (can be improved)
            "co2": total_distance * 0.18,     # approx CO₂ (can be improved)
            "delay": total_delay_minutes
        }

        return self.cost_function.compute_cost(metrics)

    def _rank_population(self):
        """
        Rank population by fitness.
        """
        return sorted(
            self.population,
            key=lambda route: self._evaluate_route(route)
        )

    # --------------------------------------------------
    # SELECTION
    # --------------------------------------------------

    def _selection(self, ranked_population):
        """
        Tournament selection.
        """
        selected = []
        for _ in range(self.population_size):
            a, b = random.sample(ranked_population, 2)
            selected.append(a if self._evaluate_route(a) <
                            self._evaluate_route(b) else b)
        return selected

    # --------------------------------------------------
    # CROSSOVER
    # --------------------------------------------------

    def _crossover(self, parent1, parent2):
        """
        Ordered crossover (OX).
        """
        if random.random() > self.crossover_rate:
            return parent1[:]

        start, end = sorted(
            random.sample(range(len(parent1)), 2)
        )

        child = [None] * len(parent1)
        child[start:end] = parent1[start:end]

        fill = [x for x in parent2 if x not in child]
        idx = 0

        for i in range(len(child)):
            if child[i] is None:
                child[i] = fill[idx]
                idx += 1

        return child

    # --------------------------------------------------
    # MUTATION
    # --------------------------------------------------

    def _mutate(self, route):
        """
        Swap mutation.
        """
        if random.random() < self.mutation_rate:
            i, j = random.sample(range(len(route)), 2)
            route[i], route[j] = route[j], route[i]
        return route

    # --------------------------------------------------
    # EVOLUTION LOOP
    # --------------------------------------------------

    def run(self):
        """
        Run the Genetic Algorithm.
        """
        print("🚀 Starting Genetic Algorithm optimization...")

        self._initialize_population()

        for gen in range(self.generations):
            ranked = self._rank_population()

            # Elitism
            next_generation = ranked[:self.elite_size]

            selected = self._selection(ranked)

            while len(next_generation) < self.population_size:
                parent1, parent2 = random.sample(selected, 2)
                child = self._crossover(parent1, parent2)
                child = self._mutate(child)
                next_generation.append(child)

            self.population = next_generation

            if gen % 10 == 0:
                best_cost = self._evaluate_route(ranked[0])
                print(f"Generation {gen} | Best Cost: {best_cost:.4f}")

        best_route = self._rank_population()[0]
        best_cost = self._evaluate_route(best_route)

        print("✅ GA Optimization Complete")
        return best_route, best_cost
