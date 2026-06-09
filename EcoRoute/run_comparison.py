"""
Run complete route optimization comparison.
This script compares Dijkstra, Greedy, and GA approaches.
"""

from utils.graph_builder import load_graphml, base_travel_time
from analytics.baseline_comparison import BaselineComparison
from prediction.delay_model import DelayMLModel
from prediction.delay_rules import DelayRulesEstimator
import os
import random


def main():
    """
    Main comparison execution.
    """
    print("=" * 70)
    print("EcoRoute - Route Optimization Comparison")
    print("=" * 70)
    
    # 1. Load graph
    GRAPH_PATH = "data/raw/osm/bangalore.graphml"
    
    if not os.path.exists(GRAPH_PATH):
        print(f"\n❌ Error: Graph file not found at {GRAPH_PATH}")
        print("Please run main.py first to download the road network.")
        return
    
    print("\n📍 Loading road network...")
    G = load_graphml(GRAPH_PATH)
    G = base_travel_time(G, speed_kmph=30)
    print(f"   ✓ Loaded {len(G.nodes):,} nodes and {len(G.edges):,} edges")
    
    # 2. Initialize delay model
    print("\n⏱️  Initializing delay model...")
    MODEL_DIR = "data/models"
    model_path = os.path.join(MODEL_DIR, "delay_random_forest.pkl")
    
    if os.path.exists(model_path):
        try:
            delay_model = DelayMLModel(model_type="random_forest")
            delay_model.load(MODEL_DIR, "delay_random_forest")
            print("   ✓ Loaded Random Forest delay model")
        except Exception as e:
            print(f"   ⚠️  Could not load ML model: {e}")
            print("   ✓ Using rule-based delay estimator")
            delay_model = DelayRulesEstimator(is_weekend=False)
    else:
        print("   ⚠️  No trained model found")
        print("   ✓ Using rule-based delay estimator")
        delay_model = DelayRulesEstimator(is_weekend=False)
    
    # 3. Select test nodes
    print("\n📌 Selecting delivery locations...")
    nodes = list(G.nodes())
    
    # Use random nodes or specify your own
    start_node = random.choice(nodes)
    delivery_nodes = random.sample([n for n in nodes if n != start_node], 5)
    
    print(f"   Start node: {start_node}")
    print(f"   Delivery nodes: {delivery_nodes}")
    
    # 4. Create comparison instance
    comparison = BaselineComparison(graph=G, delay_model=delay_model)
    
    # 5. Run complete comparison
    print("\n" + "=" * 70)
    print("Starting Route Optimization...")
    print("=" * 70)
    
    results = comparison.run_comparison(
        start_node=start_node,
        delivery_nodes=delivery_nodes,
        load_kg=40.0,          # Van with 40kg load
        area_type="urban",     # Urban delivery
        hour_of_day=9,         # Morning rush hour
        ga_generations=30      # GA optimization iterations (reduced for faster testing)
    )
    
    # 6. Display results
    comparison.print_summary()
    
    # 7. Generate visualizations
    print("\n📊 Generating comparison plots...")
    os.makedirs("reports", exist_ok=True)
    comparison.plot_comparison(save_path="reports/baseline_comparison.png")
    
    # 8. Export report
    print("\n💾 Exporting results...")
    comparison.export_report("reports/comparison_report.csv")
    
    # 9. Print text summary
    print("\n" + comparison.get_improvement_summary())
    
    print("\n" + "=" * 70)
    print("✅ Comparison Complete!")
    print("=" * 70)
    print("\nResults saved to:")
    print("  - reports/baseline_comparison.png")
    print("  - reports/comparison_report.csv")


if __name__ == "__main__":
    main()
