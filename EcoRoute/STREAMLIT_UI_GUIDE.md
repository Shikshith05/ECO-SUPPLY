# GreenRoute Streamlit UI Guide

## Overview

The **GreenRoute Streamlit Application** (`streamlit_app.py`) provides a web-based visualization and comparison dashboard for the eco-friendly delivery route optimization system. It allows users to configure delivery scenarios and compare three routing strategies: Baseline (Dijkstra), Greedy, and Genetic Algorithm (GA).

## Features

### 🎯 Core Capabilities

- **Interactive Route Configuration**: Select depots and delivery stops from available network nodes
- **Multi-Strategy Comparison**: Compare Baseline, Greedy, and Optimized (GA) routing methods
- **Real-time Optimization**: Run complete route optimization with configurable parameters
- **Sustainability Metrics**: Track CO₂ emissions, fuel consumption, and environmental impact
- **Cost Analysis**: Calculate total route costs including distance, fuel, and delay penalties
- **Visual Analytics**: Interactive charts and tables for easy comparison

### 📊 Metrics Tracked

- **Distance** (km): Total route distance
- **Fuel Consumption** (liters): Estimated fuel used
- **CO₂ Emissions** (kg): Carbon footprint
- **Delivery Delay** (minutes): Traffic-based delay estimation
- **Total Cost**: Weighted composite cost function

## Installation

### 1. Install Dependencies

Add Streamlit to your environment:

```bash
pip install -r requirements.txt
```

Or install Streamlit specifically:

```bash
pip install streamlit>=1.28.0
```

### 2. Required Project Files

Ensure the following backend components are available:

```
EcoRoute/
├── streamlit_app.py          # Main UI application
├── data/
│   └── raw/osm/
│       └── bangalore.graphml  # Road network graph
├── analytics/
│   └── baseline_comparison.py # Core comparison logic
├── prediction/
│   ├── delay_model.py
│   └── delay_rules.py
├── optimization/
│   ├── cost_function.py
│   ├── genetic_algorithm.py
│   ├── dijkstra_baseline.py
│   └── greedy_optimizer.py
└── config/
    └── config.yaml           # Cost weights and parameters
```

## Running the Application

### Start the Streamlit App

```bash
streamlit run streamlit_app.py
```

The application will launch at `http://localhost:8501`

### Command-line Options

```bash
# Run with custom port
streamlit run streamlit_app.py --server.port 8000

# Run in headless mode (for servers)
streamlit run streamlit_app.py --logger.level=debug

# Clear cache
streamlit run streamlit_app.py --logger.level=debug --client.showErrorDetails=true
```

## User Interface Guide

### 📍 Left Sidebar - Configuration Panel

#### 1. **Depot Selection**
- Select the starting point for deliveries
- Dropdown menu shows available network nodes
- Confirmation message appears when depot is selected

#### 2. **Delivery Stops**
- Multi-select interface for delivery destinations
- Minimum: 2 stops
- Maximum: 5 stops
- Useful for realistic delivery scenarios

#### 3. **Vehicle Parameters**
- **Vehicle Load**: 5-200 kg (default: 40 kg)
  - Affects fuel consumption and CO₂ calculations
  - Heavier loads = higher environmental impact
- **Area Type**: Urban or Highway
  - Urban: City streets with more congestion
  - Highway: Main roads with higher speeds

#### 4. **Hour of Day**
- Time of day (0-23 hours)
- Used for traffic pattern prediction
- Peak hours (7-9 AM, 5-7 PM) have more delays

#### 5. **Genetic Algorithm Settings**
- **GA Generations**: 50-300 (default: 100)
- More generations = better optimization but longer runtime
- Recommended: 100-150 for balanced results

### 🚀 Optimization Execution

1. Configure all parameters in the sidebar
2. Click the **"▶️ Run Optimization"** button
3. Wait for optimization to complete (1-3 minutes depending on GA generations)
4. Results will appear below

### 📊 Results Dashboard

#### Key Performance Indicators (KPIs)

Display top-level metrics showing improvements vs. baseline:

- **🌱 CO₂ Savings**: Emission reduction in kg and percentage
- **💰 Cost Savings**: Cost reduction and percentage
- **📏 Distance Reduction**: Optimized distance and percentage
- **⛽ Fuel Savings**: Fuel reduction and percentage
- **⏱️ Delay Reduction**: Delay reduction and percentage

#### Detailed Comparison Table

Shows metrics across all three strategies:

| Metric | Baseline | Greedy | Optimized (GA) | Improvement |
|--------|----------|--------|----------------|------------|
| Distance (km) | ... | ... | ... | ... |
| Fuel (liters) | ... | ... | ... | ... |
| CO₂ Emissions (kg) | ... | ... | ... | ... |
| Delivery Delay (min) | ... | ... | ... | ... |
| Total Cost | ... | ... | ... | ... |

#### Interactive Visualizations

1. **CO₂ Emissions Comparison**: Bar chart comparing emissions across strategies
2. **Total Cost Comparison**: Bar chart comparing route costs
3. **Metrics Comparison**: Grouped bar chart for all metrics across strategies

### 💾 Export Options

Two export formats available:

1. **CSV Export**: Comparison table in tabular format
   - File: `route_comparison.csv`
   - Use for: Spreadsheet analysis, reports

2. **JSON Export**: Complete optimization results
   - File: `route_optimization_results.json`
   - Includes: Configuration, all metrics, improvements, raw values

## Example Workflow

### Step-by-Step Guide

1. **Select Depot**
   - Choose "Node 1234" as starting depot
   - Appears in sidebar confirmation

2. **Select Delivery Stops**
   - Multi-select "Node 2000", "Node 2100", "Node 2200" (3 stops)
   - Click "Selected 3 delivery stops" confirmation

3. **Set Parameters**
   - Vehicle Load: 50 kg (medium delivery van)
   - Area Type: Urban (city roads)
   - Hour of Day: 09 (morning, moderate traffic)
   - GA Generations: 100 (balanced optimization)

4. **Run Optimization**
   - Click "▶️ Run Optimization"
   - Monitor progress (⏳ indicator)
   - Wait for completion (✅ confirmation)

5. **Review Results**
   - Check KPI cards for top-level improvements
   - Study comparison table for detailed metrics
   - Examine visualizations for trends

6. **Export Results**
   - Download CSV for spreadsheet analysis
   - Download JSON for programmatic processing

## Performance Optimization

### Caching Strategy

The app caches expensive operations:

```python
@st.cache_resource
def load_graph_data():
    # Loads and caches road network (one-time load)
    
@st.cache_resource
def initialize_delay_model():
    # Loads and caches delay prediction model
```

**Benefits**:
- First run: ~30 seconds (includes caching)
- Subsequent runs: < 5 seconds (uses cache)
- Cache cleared on Streamlit restart

### Recommended Hardware

- **Minimum**: 4GB RAM, 2-core CPU
- **Recommended**: 8GB RAM, 4-core CPU
- **Optimal**: 16GB+ RAM, 8+ cores (for large graphs and high GA generations)

## Troubleshooting

### Issue: "Road network file not found"

**Solution**: Ensure `data/raw/osm/bangalore.graphml` exists
```bash
# Download the graph by running main.py
python main.py
```

### Issue: "No path found between nodes"

**Solution**: 
- Try different depot/stop combinations
- Ensure selected nodes are connected in the network
- Check that graph file loaded correctly

### Issue: App runs slowly

**Solutions**:
- Reduce GA generations (start with 50)
- Reduce number of delivery stops (use 2-3 initially)
- Run on a machine with more RAM
- Check system resources (open Task Manager)

### Issue: "Could not initialize delay model"

**Solution**: Uses fallback rules-based estimator automatically
- App continues with reduced functionality
- Delay estimates use traffic rules instead of ML

### Clear Cache

If experiencing stale data:

```bash
# Delete Streamlit cache directory
rm -rf ~/.streamlit/cache/

# Or restart the app
streamlit run streamlit_app.py --logger.level=debug
```

## Configuration

### Cost Function Weights (config/config.yaml)

The optimization uses weighted metrics:

```yaml
cost_function:
  weights:
    distance: 0.25    # 25% weight on distance
    fuel: 0.25        # 25% weight on fuel
    co2: 0.30         # 30% weight on CO2
    delay: 0.20       # 20% weight on delay
```

These weights can be adjusted to change optimization priorities.

### GA Parameters (config/config.yaml)

```yaml
optimization:
  max_iterations: 1000
  population_size: 50
  mutation_rate: 0.1
  crossover_rate: 0.8
```

## API Integration

### Backend Functions Called

The UI calls these backend functions:

```python
# Main optimization comparison
results = comparison.run_comparison(
    start_node=selected_depot,
    delivery_nodes=selected_delivery_stops,
    load_kg=vehicle_load_kg,
    area_type=area_type,
    hour_of_day=hour_of_day,
    ga_generations=ga_generations
)

# Returns dictionary with:
results = {
    "baseline": {...},       # Dijkstra results
    "greedy": {...},         # Greedy results
    "optimized": {...},      # GA results
    "improvements": {...}    # Percentage improvements
}
```

## Development & Customization

### Adding New Visualizations

```python
def create_custom_chart(results):
    """Add custom visualization"""
    import plotly.graph_objects as go
    fig = go.Figure(...)
    return fig

# In main UI:
st.plotly_chart(create_custom_chart(results), use_container_width=True)
```

### Extending Parameters

```python
# Add new parameter in sidebar
new_param = st.sidebar.slider("New Parameter", min, max, default)

# Pass to run_comparison
results = comparison.run_comparison(
    ...,
    new_param=new_param
)
```

### Modifying Display Formats

```python
# Change metric formatting
st.metric(label, value, delta, delta_color="normal")
```

## Best Practices

1. **Parameter Selection**:
   - Start with 2-3 delivery stops for faster testing
   - Use GA generations of 100 for balanced results
   - Peak hours (7-9, 17-19) show realistic delays

2. **Result Interpretation**:
   - Look at CO₂ savings % for environmental impact
   - Check cost savings % for business value
   - Compare all three strategies

3. **Export Strategy**:
   - Export results immediately after optimization
   - Use CSV for reporting, JSON for systems

4. **Performance**:
   - Limit stops to 5 maximum
   - Use reasonable GA generations (50-200)
   - Run during off-peak hours for consistent performance

## Support & Documentation

- **Main Project README**: See [README.md](README.md)
- **Backend Documentation**: See [analytics/baseline_comparison.py](analytics/baseline_comparison.py)
- **Configuration Guide**: See [config/config.yaml](config/config.yaml)
- **Streamlit Docs**: https://docs.streamlit.io

---

**Last Updated**: January 2026  
**Version**: 1.0  
**Status**: Production Ready
