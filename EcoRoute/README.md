# EcoRoute 

**Eco-friendly Delivery Route Optimization System**

## Overview
GreenRoute optimizes delivery routes by minimizing distance, fuel consumption, CO₂ emissions, and delays using a multi-objective cost function and advanced optimization algorithms.

## Architecture

### Project Structure
```
GreenRoute/
├── config/              # Configuration files and constants
├── data/                # Raw and processed datasets
├── prediction/          # ML models for delay and fuel prediction
├── optimization/        # Core route optimization algorithms
├── analytics/           # Performance metrics and reporting
├── utils/               # Shared utilities
├── notebooks/           # Jupyter notebooks for exploration
├── tests/               # Unit tests
├── main.py              # Main entry point
└── requirements.txt     # Python dependencies
```

### Prediction Layer
- **delay_rules.py**: Rule-based delay estimation
- **fuel_rules.py**: Rule-based fuel consumption
- **delay_model.py**: ML delay prediction (LR/RF)
- **fuel_model.py**: ML fuel prediction (optional)
- **feature_engineering.py**: Feature creation and encoding

### Optimization Layer (CORE)
- **cost_function.py**: Multi-objective cost (distance + fuel + CO₂ + delay)
- **greedy_optimizer.py**: Baseline nearest neighbor heuristic
- **genetic_algorithm.py**: Advanced GA optimizer
- **vrp_utils.py**: Distance matrices and VRP utilities

### Analytics Layer
- **baseline_comparison.py**: Compare greedy vs optimized routes
- **emissions_analysis.py**: CO₂ calculations and savings
- **performance_metrics.py**: MAE, RMSE, improvement percentages
- **explainability.py**: Route selection explanations

## Installation

```bash
# Clone repository
git clone <repository-url>
cd EcoRoute

# Install dependencies
pip install -r requirements.txt
```

## OpenStreetMap Data Setup

This project uses OpenStreetMap road network data for route optimization.

**Note:** Due to file size constraints, the road graph file (`*.graphml`) is not stored in the repository and is excluded via `.gitignore`.

### Generate Road Graph Locally

To download and generate the road graph for your location:

```bash
python main.py
```

The script will automatically:
- Download road network data from OpenStreetMap (first run only)
- Save the graph to `data/raw/osm/bangalore.graphml`
- Load and visualize the road network

On subsequent runs, the cached graph will be loaded from the local file.

## Usage

```bash
# Run the optimization pipeline (downloads OSM data on first run)
python main.py
```

## Cost Function

The multi-objective cost function is:

**Cost = α × distance + β × fuel + γ × CO₂ + δ × delay**

Weights (α, β, γ, δ) are configurable in `config/config.yaml`

## Project Files

### Excluded from Repository (.gitignore)
The following files are excluded from version control:
- **Road network data**: `*.graphml` files (large graph files)
- **Data files**: `*.csv`, raw and processed data
- **Cache files**: OSM API cache in `cache/` directory
- **Model files**: Trained models (`*.pkl`, `*.h5`, `*.pt`)
- **Python artifacts**: `__pycache__/`, `*.pyc`
- **Notebooks**: `.ipynb_checkpoints`

These files will be generated locally when you run the project.

## TODO
- [ ] Implement all modules
- [ ] Train prediction models
- [ ] Integrate optimization algorithms
- [ ] Generate synthetic data
- [ ] Create visualization dashboards
- [ ] Add comprehensive tests

## License
See LICENSE file for details.

---
*Carbon-Aware, Delay-Sensitive Route Optimization for Small-Scale Delivery Fleets Using AI-Driven Decision Models*
