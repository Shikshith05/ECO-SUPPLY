"""
GreenRoute - Eco-friendly Delivery Route Optimization
Main entry point for the optimization pipeline.

TODO:
- Load configuration from config.yaml
- Load and preprocess data
- Initialize prediction models
- Run route optimization
- Generate analytics and reports
- Export optimized routes
"""

# TODO: Import necessary modules
# TODO: Load configuration
# TODO: Set up logging
# TODO: Load data from data/processed/
# TODO: Initialize DelayEstimator and FuelEstimator
# TODO: Run optimization (greedy baseline + GA)
# TODO: Compare results
# TODO: Generate reports
# TODO: Save optimized routes
"""
GreenRoute - Eco-friendly Delivery Route Optimization
Main entry point for the complete optimization pipeline.

Executes:
1. Load road network
2. Initialize delay prediction model
3. Run baseline routing (Dijkstra)
4. Run greedy multi-objective routing
5. Run genetic algorithm optimization
6. Compare all approaches
7. Generate reports and visualizations
"""

from optimization.dijkstra_baseline import DijkstraBaseline
from optimization.greedy_optimizer import GreedyMultiStopRouter
from analytics.baseline_comparison import BaselineComparison
from prediction.delay_model import DelayMLModel
from prediction.delay_rules import DelayRulesEstimator
from utils.osm_loader import road_graph
from utils.graph_builder import load_graphml, base_travel_time
import matplotlib.pyplot as plt
import osmnx as ox
import os
import random

GRAPH_PATH = "data/raw/osm/bangalore.graphml"
MODEL_DIR = "data/models"

def initialize_delay_model():
    """
    Initialize the delay prediction model.
    Tries to load trained ML model, falls back to rules-based estimator.
    """
    model_path = os.path.join(MODEL_DIR, "delay_random_forest.pkl")
    
    if os.path.exists(model_path):
        try:
            print("Loading trained delay model...")
            delay_model = DelayMLModel(model_type="random_forest")
            delay_model.load(MODEL_DIR, "delay_random_forest")
            print("✅ Loaded Random Forest delay model")
            return delay_model
        except Exception as e:
            print(f"⚠️ Could not load ML model: {e}")
            print("Falling back to rule-based estimator...")
            return DelayRulesEstimator(is_weekend=False)
    else:
        print("⚠️ No trained delay model found at", model_path)
        print("Using rule-based delay estimator...")
        return DelayRulesEstimator(is_weekend=False)

def main():
    """
    Main execution function - runs complete routing and comparison pipeline.
    """
    print("="*70)
    print("EcoRoute - Eco-friendly Delivery Route Optimization")
    print("="*70)
    
    # 1. Load road network
    if not os.path.exists(GRAPH_PATH):
        print("\n📥 Downloading road network...")
        G = road_graph("Bangalore, India", GRAPH_PATH)
    else:
        print("\n📂 Loading road network from file...")

    G = load_graphml(GRAPH_PATH)
    G = base_travel_time(G, speed_kmph=30)

    print(f"\n📊 Graph Statistics:")
    print(f"  Nodes: {len(G.nodes):,}")
    print(f"  Edges: {len(G.edges):,}")
    
    # 2. Initialize delay prediction model
    print("\n⏱️  Initializing delay prediction model...")
    delay_model = initialize_delay_model()
    
    # Test delay prediction
    print("\n🧪 Testing delay prediction:")
    if isinstance(delay_model, DelayMLModel):
        test_delay = delay_model.predict_single(
            road_type="primary",
            length_m=1000,
            hour_of_day=9  # Morning peak
        )
        print(f"  Predicted delay for 1km primary road at 9 AM: {test_delay:.2f} seconds")
    else:
        test_result = delay_model.estimate_delay(
            road_type="primary",
            length_m=1000,
            hour_of_day=9
        )
        print(f"  Predicted delay for 1km primary road at 9 AM: {test_result['delay_sec']:.2f} seconds")
    
    # 3. Select delivery nodes for comparison
    print("\n📌 Selecting delivery locations...")
    nodes = list(G.nodes())
    
    # Use random nodes (or specify your own)
    start_node = random.choice(nodes)
    delivery_nodes = random.sample([n for n in nodes if n != start_node], 5)
    
    print(f"  Start node: {start_node}")
    print(f"  Delivery nodes: {delivery_nodes[:3]}... (5 total)")
    
    # 4. Run complete routing and comparison pipeline
    print("\n" + "="*70)
    print("RUNNING COMPLETE ROUTING AND COMPARISON PIPELINE")
    print("="*70)
    
    comparison = BaselineComparison(graph=G, delay_model=delay_model)
    
    # Execute all algorithms and compute metrics
    results = comparison.run_comparison(
        start_node=start_node,
        delivery_nodes=delivery_nodes,
        load_kg=40.0,          # Van with 40kg load
        area_type="urban",     # Urban delivery
        hour_of_day=9,         # Morning rush hour (9 AM)
        ga_generations=30      # GA optimization iterations (reduced for faster execution)
    )
    
    # 5. Display comparison results
    comparison.print_summary()
    
    # 6. Generate visualizations and reports
    print("\n📊 Generating comparison plots and reports...")
    os.makedirs("reports", exist_ok=True)
    
    comparison.plot_comparison(save_path="reports/baseline_comparison.png")
    comparison.export_report("reports/comparison_report.csv")
    
    # 7. Print text summary
    print("\n" + comparison.get_improvement_summary())
    
    print("\n" + "="*70)
    print("✅ PIPELINE EXECUTION COMPLETE!")
    print("="*70)
    print("\n📁 Results saved to:")
    print("  - reports/baseline_comparison.png  (Visualizations)")
    print("  - reports/comparison_report.csv    (Detailed metrics)")
    print("\n💡 Tip: Check the reports/ folder for detailed analysis")
    
    # Optional: Visualize graph
    # print("\nVisualizing the graph...")
    # fig, ax = ox.plot_graph(G, show=False)
    # plt.show()

if __name__ == "__main__":
    main()
