"""
Baseline comparison between greedy and optimized routes.

Automatically runs:
1. Baseline routing (Dijkstra)
2. Greedy routing
3. GA routing
4. Extracts metrics
5. Computes cost
6. Prints/returns comparison
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from typing import Dict, List, Any, Tuple
import os

from optimization.dijkstra_baseline import DijkstraBaseline
from optimization.greedy_optimizer import GreedyMultiStopRouter
from optimization.genetic_algorithm import GeneticAlgorithm
from optimization.cost_function import CostFunction
from analytics.emissions_analysis import EmissionsAnalyzer
from prediction.delay_model import DelayMLModel
from prediction.delay_rules import DelayRulesEstimator


class BaselineComparison:
    """
    Compare baseline (Dijkstra) vs Greedy vs optimized (GA) routes.
    """

    def __init__(self, graph=None, delay_model=None):
        """
        Initialize the baseline comparison analyzer.
        
        Args:
            graph: Road network graph (NetworkX or adjacency list)
            delay_model: DelayMLModel or DelayRulesEstimator instance
        """
        self.graph = graph
        self.delay_model = delay_model
        self.cost_function = CostFunction()
        self.emissions = EmissionsAnalyzer()
        
        self.results = {
            "baseline": {},
            "greedy": {},
            "optimized": {},
            "improvements": {}
        }

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
        Run complete comparison: baseline -> greedy -> GA.
        
        Args:
            start_node: Starting node
            delivery_nodes: List of delivery node IDs
            load_kg: Vehicle load in kg
            area_type: 'urban' or 'highway'
            hour_of_day: Hour (0-23) for delay prediction
            ga_generations: Number of GA generations
            
        Returns:
            Dictionary with all results and comparisons
        """
        if self.graph is None:
            raise ValueError("Graph must be provided to run comparison")
        
        print("\n" + "=" * 70)
        print("RUNNING ROUTE OPTIMIZATION COMPARISON")
        print("=" * 70)
        
        # 1. Run Baseline (Dijkstra - distance only)
        print("\n[1/3] Running baseline routing (Dijkstra - distance only)...")
        baseline_result = self._run_baseline(start_node, delivery_nodes, load_kg, area_type, hour_of_day)
        
        # 2. Run Greedy (considers all factors)
        print("\n[2/3] Running greedy routing (multi-objective)...")
        greedy_result = self._run_greedy(start_node, delivery_nodes, load_kg, area_type, hour_of_day)
        
        # 3. Run GA (optimized)
        print("\n[3/3] Running genetic algorithm optimization...")
        ga_result = self._run_ga(start_node, delivery_nodes, load_kg, area_type, hour_of_day, ga_generations)
        
        # Store results
        self.results["baseline"] = baseline_result
        self.results["greedy"] = greedy_result
        self.results["optimized"] = ga_result
        
        # Calculate improvements
        self.calculate_improvements()
        
        return self.results
    
    def _run_baseline(self, start_node, delivery_nodes, load_kg, area_type, hour_of_day) -> Dict:
        """Run baseline Dijkstra routing."""
        import networkx as nx
        
        current = start_node
        total_distance = 0.0
        full_path = []
        
        for node in delivery_nodes:
            # Use NetworkX's built-in shortest path for baseline
            try:
                path = nx.shortest_path(self.graph, current, node, weight='length')
                
                # Calculate distance
                segment_distance = 0.0
                for i in range(len(path) - 1):
                    edge_data = self.graph.get_edge_data(path[i], path[i+1], 0) or {}
                    segment_distance += edge_data.get('length', 0) / 1000  # Convert to km
                
                total_distance += segment_distance
                
                if full_path:
                    path = path[1:]
                full_path.extend(path)
                current = node
            except nx.NetworkXNoPath:
                print(f"  ⚠️ No path found from {current} to {node}")
                continue
        
        metrics = self._calculate_metrics(total_distance, load_kg, area_type, hour_of_day, full_path)
        
        print(f"  ✓ Distance: {total_distance:.2f} km | Cost: {metrics['total_cost']:.4f}")
        return metrics
    
    def _run_greedy(self, start_node, delivery_nodes, load_kg, area_type, hour_of_day) -> Dict:
        """Run greedy multi-objective routing."""
        greedy = GreedyMultiStopRouter(self.graph, delay_model=self.delay_model)
        
        result = greedy.route(
            start_node=start_node,
            delivery_nodes=delivery_nodes,
            load_kg=load_kg,
            area_type=area_type,
            hour_of_day=hour_of_day
        )
        
        path = result["path"]
        total_distance = self._calculate_path_distance(path)
        metrics = self._calculate_metrics(total_distance, load_kg, area_type, hour_of_day, path)
        metrics["total_cost"] = result["total_cost"]
        
        print(f"  ✓ Distance: {total_distance:.2f} km | Cost: {metrics['total_cost']:.4f}")
        return metrics
    
    def _run_ga(self, start_node, delivery_nodes, load_kg, area_type, hour_of_day, generations) -> Dict:
        """Run genetic algorithm optimization."""
        import networkx as nx
        
        distance_matrix = {}
        
        all_nodes = [start_node] + delivery_nodes
        for i, node_i in enumerate(all_nodes):
            for j, node_j in enumerate(all_nodes):
                if i != j:
                    try:
                        path = nx.shortest_path(self.graph, node_i, node_j, weight='length')
                        dist = 0.0
                        for k in range(len(path) - 1):
                            edge_data = self.graph.get_edge_data(path[k], path[k+1], 0) or {}
                            dist += edge_data.get('length', 0) / 1000  # Convert to km
                        distance_matrix[(node_i, node_j)] = dist
                    except nx.NetworkXNoPath:
                        distance_matrix[(node_i, node_j)] = float('inf')
        
        ga = GeneticAlgorithm(
            locations=delivery_nodes,
            distance_matrix=distance_matrix,
            cost_function=self.cost_function,
            delay_model=self.delay_model,
            hour_of_day=hour_of_day,
            generations=generations,
            population_size=50
        )
        
        best_route, best_cost = ga.run()
        
        total_distance = sum(
            distance_matrix[(best_route[i], best_route[i+1])]
            for i in range(len(best_route) - 1)
        )
        
        metrics = self._calculate_metrics(total_distance, load_kg, area_type, hour_of_day, best_route)
        metrics["total_cost"] = best_cost
        
        print(f"  ✓ Distance: {total_distance:.2f} km | Cost: {metrics['total_cost']:.4f}")
        return metrics
    
    def _calculate_path_distance(self, path) -> float:
        """Calculate total distance of a path."""
        total_distance = 0.0
        
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            if hasattr(self.graph, 'edges'):
                edge_data = self.graph.get_edge_data(u, v, 0) or {}
                length_m = edge_data.get('length', 0)
                total_distance += length_m / 1000
        
        return total_distance
    
    def _calculate_metrics(self, distance_km, load_kg, area_type, hour_of_day, path=None) -> Dict:
        """Calculate all metrics for a route."""
        fuel_liters = self.emissions.estimator.estimate_fuel(distance_km, "van", load_kg, area_type)
        co2_kg = self.emissions.calculate_total_emissions(distance_km, load_kg, area_type)
        
        if path and self.delay_model:
            delay_minutes = self._estimate_path_delay(path, hour_of_day)
        else:
            delay_minutes = distance_km * 1.5
        
        metrics_dict = {
            "distance": distance_km,
            "fuel": fuel_liters,
            "co2": co2_kg,
            "delay": delay_minutes
        }
        total_cost = self.cost_function.compute_cost(metrics_dict)
        
        return {
            "distance_km": distance_km,
            "fuel_liters": fuel_liters,
            "co2_kg": co2_kg,
            "delay_minutes": delay_minutes,
            "total_cost": total_cost
        }
    
    def _estimate_path_delay(self, path, hour_of_day) -> float:
        """Estimate delay for entire path."""
        total_delay_sec = 0.0
        
        for i in range(len(path) - 1):
            u, v = path[i], path[i + 1]
            
            if hasattr(self.graph, 'edges'):
                edge_data = self.graph.get_edge_data(u, v, 0) or {}
                length_m = edge_data.get('length', 500)
                road_type = edge_data.get('highway', 'primary')
                
                if isinstance(road_type, list):
                    road_type = road_type[0]
                
                road_type = road_type if road_type in ['motorway', 'primary', 'secondary', 'tertiary', 'residential'] else 'primary'
                
                if isinstance(self.delay_model, DelayMLModel):
                    delay_sec = self.delay_model.predict_single(road_type, length_m, hour_of_day)
                else:
                    delay_data = self.delay_model.estimate_delay(road_type, length_m, hour_of_day)
                    delay_sec = delay_data['delay_sec']
                
                total_delay_sec += delay_sec
        
        return total_delay_sec / 60.0

    def calculate_improvements(self) -> Dict[str, float]:
        """Calculate improvement percentages (baseline vs optimized)."""
        baseline = self.results["baseline"]
        optimized = self.results["optimized"]

        if not baseline or not optimized:
            raise ValueError("Both baseline and optimized results must be present")

        improvements = {}
        
        for metric in ["distance_km", "fuel_liters", "co2_kg", "delay_minutes", "total_cost"]:
            base_val = baseline.get(metric, 0)
            opt_val = optimized.get(metric, 0)
            
            if base_val > 0:
                improvement = ((base_val - opt_val) / base_val) * 100
                improvements[metric] = round(improvement, 2)
            else:
                improvements[metric] = 0.0

        self.results["improvements"] = improvements
        return improvements

    def generate_comparison_table(self) -> pd.DataFrame:
        """Generate a comparison table with all three methods."""
        if not self.results["improvements"]:
            self.calculate_improvements()

        data = {
            "Metric": [
                "Distance (km)",
                "Fuel (liters)",
                "CO₂ Emissions (kg)",
                "Delay (minutes)",
                "Total Cost"
            ],
            "Baseline (Dijkstra)": [
                self.results["baseline"]["distance_km"],
                self.results["baseline"]["fuel_liters"],
                self.results["baseline"]["co2_kg"],
                self.results["baseline"]["delay_minutes"],
                self.results["baseline"]["total_cost"]
            ],
            "Greedy": [
                self.results["greedy"]["distance_km"],
                self.results["greedy"]["fuel_liters"],
                self.results["greedy"]["co2_kg"],
                self.results["greedy"]["delay_minutes"],
                self.results["greedy"]["total_cost"]
            ],
            "Optimized (GA)": [
                self.results["optimized"]["distance_km"],
                self.results["optimized"]["fuel_liters"],
                self.results["optimized"]["co2_kg"],
                self.results["optimized"]["delay_minutes"],
                self.results["optimized"]["total_cost"]
            ],
            "Improvement (%)": [
                self.results["improvements"]["distance_km"],
                self.results["improvements"]["fuel_liters"],
                self.results["improvements"]["co2_kg"],
                self.results["improvements"]["delay_minutes"],
                self.results["improvements"]["total_cost"]
            ]
        }

        df = pd.DataFrame(data)
        return df

    def print_summary(self):
        """Print a formatted summary of the comparison."""
        if not self.results["improvements"]:
            self.calculate_improvements()

        print("\n" + "=" * 70)
        print("BASELINE vs OPTIMIZED ROUTE COMPARISON")
        print("=" * 70)
        
        df = self.generate_comparison_table()
        print("\n" + df.to_string(index=False))
        
        print("\n" + "-" * 70)
        print("KEY INSIGHTS:")
        print("-" * 70)
        
        improvements = self.results["improvements"]
        
        best_metric = max(improvements.items(), key=lambda x: x[1])
        print(f"✓ Best Improvement: {best_metric[0].replace('_', ' ').title()}")
        print(f"  Reduced by {best_metric[1]:.2f}%")
        
        cost_improvement = improvements["total_cost"]
        if cost_improvement > 0:
            print(f"\n✓ Overall Cost Reduction: {cost_improvement:.2f}%")
        else:
            print(f"\n⚠ Overall Cost Increase: {abs(cost_improvement):.2f}%")
        
        co2_improvement = improvements["co2_kg"]
        baseline_co2 = self.results["baseline"]["co2_kg"]
        co2_saved = baseline_co2 * (co2_improvement / 100)
        print(f"\n✓ CO₂ Emissions Saved: {co2_saved:.2f} kg")
        print(f"  Equivalent to planting ~{int(co2_saved / 21.77)} trees annually")
        
        print("\n" + "=" * 70)

    def plot_comparison(self, save_path: str = None):
        """Plot comparison charts."""
        if not self.results["improvements"]:
            self.calculate_improvements()

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Baseline vs Optimized Route Comparison', fontsize=16, fontweight='bold')

        df = self.generate_comparison_table()
        
        # 1. Metric Comparison Bar Chart
        ax1 = axes[0, 0]
        metrics = df['Metric'].tolist()[:4]
        baseline_vals = df['Baseline (Dijkstra)'].tolist()[:4]
        optimized_vals = df['Optimized (GA)'].tolist()[:4]
        
        x = range(len(metrics))
        width = 0.35
        
        ax1.bar([i - width/2 for i in x], baseline_vals, width, label='Baseline', color='#e74c3c')
        ax1.bar([i + width/2 for i in x], optimized_vals, width, label='Optimized', color='#27ae60')
        ax1.set_xlabel('Metrics')
        ax1.set_ylabel('Values')
        ax1.set_title('Metric Comparison')
        ax1.set_xticks(x)
        ax1.set_xticklabels([m.split('(')[0].strip() for m in metrics], rotation=45, ha='right')
        ax1.legend()
        ax1.grid(True, alpha=0.3)

        # 2. Improvement Percentages
        ax2 = axes[0, 1]
        improvements = list(self.results["improvements"].values())
        metric_names = ['Distance', 'Fuel', 'CO₂', 'Delay', 'Cost']
        colors = ['#27ae60' if x > 0 else '#e74c3c' for x in improvements]
        
        bars = ax2.barh(metric_names, improvements, color=colors)
        ax2.set_xlabel('Improvement (%)')
        ax2.set_title('Improvement Percentages')
        ax2.axvline(x=0, color='black', linestyle='-', linewidth=0.8)
        ax2.grid(True, alpha=0.3, axis='x')
        
        for i, (bar, val) in enumerate(zip(bars, improvements)):
            x_pos = val + (2 if val > 0 else -2)
            ax2.text(x_pos, i, f'{val:.1f}%', va='center', ha='left' if val > 0 else 'right')

        # 3. Baseline Route Composition
        ax3 = axes[1, 0]
        baseline_data = [
            self.results["baseline"]["distance_km"],
            self.results["baseline"]["fuel_liters"],
            self.results["baseline"]["co2_kg"],
            self.results["baseline"]["delay_minutes"]
        ]
        labels = ['Distance', 'Fuel', 'CO₂', 'Delay']
        colors_pie = ['#3498db', '#e67e22', '#e74c3c', '#9b59b6']
        
        ax3.pie(baseline_data, labels=labels, autopct='%1.1f%%', colors=colors_pie, startangle=90)
        ax3.set_title('Baseline Route Composition')

        # 4. Environmental Impact
        ax4 = axes[1, 1]
        co2_baseline = self.results["baseline"]["co2_kg"]
        co2_optimized = self.results["optimized"]["co2_kg"]
        co2_saved = co2_baseline - co2_optimized
        
        categories = ['Baseline\nEmissions', 'Optimized\nEmissions', 'Emissions\nSaved']
        values = [co2_baseline, co2_optimized, co2_saved]
        colors_env = ['#e74c3c', '#f39c12', '#27ae60']
        
        bars = ax4.bar(categories, values, color=colors_env)
        ax4.set_ylabel('CO₂ (kg)')
        ax4.set_title('Environmental Impact')
        ax4.grid(True, alpha=0.3, axis='y')
        
        for bar in bars:
            height = bar.get_height()
            ax4.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.2f}',
                    ha='center', va='bottom', fontweight='bold')

        plt.tight_layout()
        
        if save_path:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"\n📊 Comparison plot saved to: {save_path}")
        
        plt.show()

    def export_report(self, filepath: str):
        """Export comparison report to CSV."""
        if not self.results["improvements"]:
            self.calculate_improvements()

        df = self.generate_comparison_table()
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        df.to_csv(filepath, index=False)
        print(f"\n📄 Comparison report exported to: {filepath}")

    def get_improvement_summary(self) -> str:
        """Get a text summary of improvements."""
        if not self.results["improvements"]:
            self.calculate_improvements()

        improvements = self.results["improvements"]
        
        summary = "ROUTE OPTIMIZATION SUMMARY\n"
        summary += "=" * 50 + "\n"
        summary += f"Distance Reduction: {improvements['distance_km']:.2f}%\n"
        summary += f"Fuel Savings: {improvements['fuel_liters']:.2f}%\n"
        summary += f"CO₂ Reduction: {improvements['co2_kg']:.2f}%\n"
        summary += f"Delay Reduction: {improvements['delay_minutes']:.2f}%\n"
        summary += f"Cost Savings: {improvements['total_cost']:.2f}%\n"
        summary += "=" * 50 + "\n"
        
        return summary


if __name__ == "__main__":
    from utils.graph_builder import load_graphml, base_travel_time
    
    print("Loading graph...")
    GRAPH_PATH = "data/raw/osm/bangalore.graphml"
    
    if not os.path.exists(GRAPH_PATH):
        print(f"Error: Graph file not found at {GRAPH_PATH}")
        print("Please run main.py first to download the road network.")
        exit(1)
    
    G = load_graphml(GRAPH_PATH)
    G = base_travel_time(G, speed_kmph=30)
    
    delay_model = DelayRulesEstimator(is_weekend=False)
    
    comparison = BaselineComparison(graph=G, delay_model=delay_model)
    
    import random
    nodes = list(G.nodes())
    start_node = random.choice(nodes)
    delivery_nodes = random.sample([n for n in nodes if n != start_node], 5)
    
    print(f"\nTesting with:")
    print(f"  Start node: {start_node}")
    print(f"  Delivery nodes: {delivery_nodes}")
    
    results = comparison.run_comparison(
        start_node=start_node,
        delivery_nodes=delivery_nodes,
        load_kg=40.0,
        area_type="urban",
        hour_of_day=9,
        ga_generations=50
    )
    
    comparison.print_summary()
    comparison.plot_comparison(save_path="reports/baseline_comparison.png")
    comparison.export_report("reports/comparison_report.csv")
    print("\n" + comparison.get_improvement_summary())
