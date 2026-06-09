# EcoRoute - Running the Complete Pipeline

## Quick Start

To execute the complete routing and comparison pipeline, simply run:

```bash
python main.py
```

## What Happens When You Run main.py

The pipeline automatically executes the following steps:

### 1️⃣ **Load Road Network**
- Downloads Bangalore road network (if not cached)
- Builds graph with ~150,000+ nodes and edges

### 2️⃣ **Initialize Delay Prediction**
- Loads trained ML model (Random Forest) if available
- Falls back to rule-based estimator if model not found

### 3️⃣ **Run Baseline Routing (Dijkstra)**
- Traditional shortest path algorithm
- Distance-only optimization
- Computes fuel, CO₂, and delay metrics

### 4️⃣ **Run Greedy Multi-Objective Routing**
- Considers distance, fuel, CO₂, and delay
- Uses delay model for real-time predictions
- Greedy nearest-neighbor heuristic

### 5️⃣ **Run Genetic Algorithm Optimization**
- Advanced evolutionary optimization
- 100 generations of route improvement
- Multi-objective cost minimization

### 6️⃣ **Compute All Metrics**
- Distance (km)
- Fuel consumption (liters)
- CO₂ emissions (kg)
- Traffic delays (minutes)
- Total cost (normalized)

### 7️⃣ **Generate Comparison Results**
- Detailed comparison table
- Improvement percentages
- Environmental impact analysis
- Cost savings calculations

### 8️⃣ **Output Reports**
- Console: Formatted summary with insights
- `reports/baseline_comparison.png`: 4-panel visualization
- `reports/comparison_report.csv`: Detailed metrics table

## Expected Output

```
==================================================================
EcoRoute - Eco-friendly Delivery Route Optimization
==================================================================

📂 Loading road network from file...

📊 Graph Statistics:
  Nodes: 150,234
  Edges: 245,678

⏱️  Initializing delay prediction model...
✅ Loaded Random Forest delay model

🧪 Testing delay prediction:
  Predicted delay for 1km primary road at 9 AM: 145.32 seconds

📌 Selecting delivery locations...
  Start node: 123456789
  Delivery nodes: [987654321, 111222333, ...]... (5 total)

==================================================================
RUNNING COMPLETE ROUTING AND COMPARISON PIPELINE
==================================================================

[1/3] Running baseline routing (Dijkstra - distance only)...
  ✓ Distance: 18.45 km | Cost: 0.6234

[2/3] Running greedy routing (multi-objective)...
  ✓ Distance: 16.78 km | Cost: 0.5421

[3/3] Running genetic algorithm optimization...
🚀 Starting Genetic Algorithm optimization...
Generation 0 | Best Cost: 0.5421
Generation 10 | Best Cost: 0.5012
...
✅ GA Optimization Complete
  ✓ Distance: 15.23 km | Cost: 0.4856

==================================================================
BASELINE vs OPTIMIZED ROUTE COMPARISON
==================================================================

                 Metric  Baseline (Dijkstra)    Greedy  Optimized (GA)  Improvement (%)
        Distance (km)              18.45     16.78           15.23            17.43
      Fuel (liters)                 2.21      2.01            1.83            17.19
  CO₂ Emissions (kg)                5.11      4.64            4.22            17.42
    Delay (minutes)                27.68     25.17           22.85            17.45
          Total Cost                0.62      0.54            0.49            21.38

----------------------------------------------------------------------
KEY INSIGHTS:
----------------------------------------------------------------------
✓ Best Improvement: Total Cost
  Reduced by 21.38%

✓ Overall Cost Reduction: 21.38%

✓ CO₂ Emissions Saved: 0.89 kg
  Equivalent to planting ~0 trees annually

==================================================================

📊 Generating comparison plots and reports...
📊 Comparison plot saved to: reports/baseline_comparison.png
💾 Exporting results...
📄 Comparison report exported to: reports/comparison_report.csv

ROUTE OPTIMIZATION SUMMARY
==================================================
Distance Reduction: 17.43%
Fuel Savings: 17.19%
CO₂ Reduction: 17.42%
Delay Reduction: 17.45%
Cost Savings: 21.38%
==================================================

==================================================================
✅ PIPELINE EXECUTION COMPLETE!
==================================================================

📁 Results saved to:
  - reports/baseline_comparison.png  (Visualizations)
  - reports/comparison_report.csv    (Detailed metrics)

💡 Tip: Check the reports/ folder for detailed analysis
```

## Customization

To use specific delivery locations, edit `main.py` around line 82:

```python
# Replace random selection with your nodes:
start_node = 123456789  # Your depot
delivery_nodes = [
    987654321,  # Customer 1
    111222333,  # Customer 2
    444555666,  # Customer 3
]
```

## Output Files

- **reports/baseline_comparison.png**: 4-panel visualization showing:
  - Metric comparison bar chart
  - Improvement percentages
  - Baseline route composition
  - Environmental impact (CO₂)

- **reports/comparison_report.csv**: Detailed metrics table with all values

## Requirements

Make sure all dependencies are installed:

```bash
pip install -r requirements.txt
```

## First Time Setup

If the road network doesn't exist, it will be downloaded automatically.
This may take a few minutes on first run.

---

**That's it!** Just run `python main.py` and the complete pipeline executes automatically.
