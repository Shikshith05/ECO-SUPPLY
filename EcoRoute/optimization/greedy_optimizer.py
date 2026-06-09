"""
Greedy baseline optimizer for route planning.
Nearest neighbor heuristic for VRP.

TODO:
- Implement nearest neighbor algorithm
- Add route construction logic
- Calculate baseline metrics
- Support multiple vehicles
"""

# TODO: GreedyOptimizer class
# TODO: Nearest neighbor selection
# TODO: Route construction
# TODO: Performance metrics


from optimization.cost_function import CostFunction
from analytics.emissions_analysis import EmissionsAnalyzer
from prediction.delay_model import DelayMLModel
from prediction.delay_rules import DelayRulesEstimator
import networkx as nx
import os


class GreedyMultiStopRouter:
    """
    Greedy heuristic for multi-stop routing.
    """

    def __init__(self, graph, delay_model=None):
        self.graph = graph
        self.cost_fn = CostFunction()
        self.emissions = EmissionsAnalyzer()
        
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
                    print("✅ Loaded trained delay model (Random Forest)")
                except Exception as e:
                    print(f"⚠️ Could not load ML model: {e}. Using rule-based estimator.")
                    self.delay_model = DelayRulesEstimator(is_weekend=False)
            else:
                print("⚠️ No trained model found. Using rule-based delay estimator.")
                self.delay_model = DelayRulesEstimator(is_weekend=False)

    def route(
        self,
        start_node,
        delivery_nodes,
        load_kg=40.0,
        area_type="urban",
        hour_of_day=9
    ):
        current = start_node
        unvisited = delivery_nodes.copy()

        full_path = []
        total_cost = 0.0

        while unvisited:
            best_candidate = None
            best_candidate_data = None
            best_cost = float("inf")

            for node in unvisited:
                # Use NetworkX shortest path
                try:
                    path = nx.shortest_path(self.graph, current, node, weight='length')
                    
                    # Calculate distance
                    distance_km = 0.0
                    for i in range(len(path) - 1):
                        edge_data = self.graph.get_edge_data(path[i], path[i+1], 0) or {}
                        distance_km += edge_data.get('length', 0) / 1000
                except nx.NetworkXNoPath:
                    continue

                # Get delay prediction
                delay_minutes = self._predict_delay(
                    path, distance_km, hour_of_day
                )

                metrics = {
                    "distance": distance_km,
                    "fuel": self.emissions.estimator.estimate_fuel(
                        distance_km, "van", load_kg, area_type
                    ),
                    "co2": self.emissions.calculate_total_emissions(
                        distance_km, load_kg, area_type
                    ),
                    "delay": delay_minutes
                }

                cost = self.cost_fn.compute_cost(metrics)

                if cost < best_cost:
                    best_cost = cost
                    best_candidate = node
                    best_candidate_data = (path, metrics)

            path, metrics = best_candidate_data

            # Append path (avoid duplication)
            if full_path:
                path = path[1:]

            full_path.extend(path)
            total_cost += best_cost

            current = best_candidate
            unvisited.remove(best_candidate)

        return {
            "path": full_path,
            "total_cost": total_cost
        }

    def _predict_delay(
        self,
        path,
        distance_km,
        hour_of_day
    ) -> float:
        """
        Predict delay for a path segment.
        
        Args:
            path: List of nodes in the path
            distance_km: Total distance of the path in km
            hour_of_day: Current hour (0-23)
            
        Returns:
            Predicted delay in minutes
        """
        # Get edge data from graph
        total_delay_sec = 0.0
        
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            
            # Get edge data
            if hasattr(self.graph, 'edges'):
                # NetworkX graph
                edge_data = self.graph.get_edge_data(u, v, 0) or {}
                length_m = edge_data.get('length', 0)
                road_type = edge_data.get('highway', 'unclassified')
                
                # Handle highway as list
                if isinstance(road_type, list):
                    road_type = road_type[0]
                    
                # Map OSM road types to delay model categories
                road_type_map = {
                    'motorway': 'motorway',
                    'motorway_link': 'motorway',
                    'trunk': 'primary',
                    'trunk_link': 'primary',
                    'primary': 'primary',
                    'primary_link': 'primary',
                    'secondary': 'secondary',
                    'secondary_link': 'secondary',
                    'tertiary': 'tertiary',
                    'tertiary_link': 'tertiary',
                    'residential': 'residential',
                    'service': 'service',
                    'unclassified': 'unclassified'
                }
                road_type = road_type_map.get(road_type, 'unclassified')
            else:
                # Simple adjacency list - estimate from total distance
                length_m = (distance_km * 1000) / max(1, len(path) - 1)
                road_type = 'primary'
            
            # Predict delay for this segment
            if isinstance(self.delay_model, DelayMLModel):
                # Use ML model
                delay_sec = self.delay_model.predict_single(
                    road_type=road_type,
                    length_m=length_m,
                    hour_of_day=hour_of_day
                )
            else:
                # Use rules-based estimator
                delay_data = self.delay_model.estimate_delay(
                    road_type=road_type,
                    length_m=length_m,
                    hour_of_day=hour_of_day
                )
                delay_sec = delay_data['delay_sec']
            
            total_delay_sec += delay_sec
        
        # Convert to minutes
        return total_delay_sec / 60.0
