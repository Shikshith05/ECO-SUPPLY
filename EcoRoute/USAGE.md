# How to Run Route Optimization Comparison

## Quick Start

### Option 1: Run Complete Comparison (Recommended)
```bash
python run_comparison.py
```

This will:
1. Load the Bangalore road network
2. Initialize the delay prediction model
3. Run **3 routing algorithms**:
   - Baseline (Dijkstra - distance only)
   - Greedy (multi-objective)
   - GA (optimized)
4. Extract all metrics (distance, fuel, CO₂, delay)
5. Compute costs
6. Display comparison table
7. Generate plots → `reports/baseline_comparison.png`
8. Export CSV → `reports/comparison_report.csv`

### Option 2: Integrate into Your Code

```python
from utils.graph_builder import load_graphml, base_travel_time
from analytics.baseline_comparison import BaselineComparison
from prediction.delay_rules import DelayRulesEstimator

# Load graph
G = load_graphml("data/raw/osm/bangalore.graphml")
G = base_travel_time(G, speed_kmph=30)

# Initialize comparison
delay_model = DelayRulesEstimator(is_weekend=False)
comparison = BaselineComparison(graph=G, delay_model=delay_model)

# Define route
start_node = 123456789  # Your start node
delivery_nodes = [987654321, 111222333, 444555666]  # Your delivery nodes

# Run comparison
results = comparison.run_comparison(
    start_node=start_node,
    delivery_nodes=delivery_nodes,
    load_kg=40.0,
    area_type="urban",
    hour_of_day=9,
    ga_generations=100
)

# Display results
comparison.print_summary()
comparison.plot_comparison(save_path="reports/comparison.png")
```

### Option 3: Use Specific Nodes

Edit `run_comparison.py` and replace the random selection:

```python
# Instead of random selection:
# start_node = random.choice(nodes)
# delivery_nodes = random.sample([n for n in nodes if n != start_node], 5)

# Use specific nodes:
start_node = 123456789  # Your depot
delivery_nodes = [
    987654321,  # Customer 1
    111222333,  # Customer 2
    444555666,  # Customer 3
    777888999   # Customer 4
]
```

## Parameters

- `start_node`: Starting location (depot)
- `delivery_nodes`: List of delivery locations
- `load_kg`: Vehicle load in kilograms (default: 40.0)
- `area_type`: `"urban"` or `"highway"` (default: "urban")
- `hour_of_day`: Hour 0-23 for traffic prediction (default: 9)
- `ga_generations`: GA iterations (default: 100, higher = better but slower)

## Output

### Console Output
- Progress for each algorithm
- Comparison table with all metrics
- Key insights and improvements
- Environmental impact (CO₂ savings)

### Files Generated
- `reports/baseline_comparison.png` - 4-panel visualization
- `reports/comparison_report.csv` - Detailed metrics table

## Troubleshooting

**If graph not found:**
```bash
python main.py  # Downloads Bangalore road network
```

**If delay model not found:**
- The system automatically uses rule-based estimator
- To train ML model: `python -m prediction.delay_model`

**If imports fail:**
```bash
pip install -r requirements.txt
```
