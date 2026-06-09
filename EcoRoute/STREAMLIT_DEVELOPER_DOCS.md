# Streamlit App - Developer Documentation

## Architecture Overview

```
streamlit_app.py (702 lines)
├── Imports & Configuration
│   ├── Streamlit setup
│   ├── Plotly visualizations
│   └── Backend module imports
│
├── Caching Layer (@st.cache_resource)
│   ├── load_graph_data() - Road network caching
│   └── initialize_delay_model() - ML model caching
│
├── Helper Functions
│   ├── Formatting utilities
│   ├── Calculation functions
│   ├── DataFrame creation
│   └── Visualization factories
│
├── Visualization Functions (6 chart types)
│   ├── Comparison bar charts
│   ├── CO₂ emission charts
│   ├── Cost comparison charts
│   └── Gauge charts for improvements
│
└── Main UI (main() function)
    ├── Header & layout
    ├── Sidebar configuration
    ├── Optimization execution
    └── Results display & export
```

## Key Components

### 1. Page Configuration

```python
st.set_page_config(
    page_title="GreenRoute - Routing Optimization",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)
```

**Configuration Options**:
- `layout="wide"`: Uses full browser width (better for charts)
- `initial_sidebar_state="expanded"`: Sidebar visible on load
- `page_icon="🌍"`: Browser tab icon

### 2. Caching Strategy

```python
@st.cache_resource
def load_graph_data():
    """Load and cache the road network graph"""
    # Expensive operation (only runs once)
    graph = load_graphml(graph_path)
    return graph
```

**Why Caching?**:
- Road network: ~30s to load
- Delay model: ~5s to load
- Cache persists across UI reruns
- First run: slow (~30s)
- Subsequent runs: fast (<2s)

**Cache Invalidation**:
- Automatic on Streamlit restart
- Manual: `streamlit run streamlit_app.py --logger.level=debug`

### 3. Session State

```python
if "optimization_results" not in st.session_state:
    st.session_state.optimization_results = None
```

**Used for**:
- Storing optimization results between reruns
- Preserving user inputs
- Preventing data loss on page interactions

### 4. Helper Functions

#### Formatting Utilities

```python
def format_metric(value: float, unit: str = "", decimals: int = 2) -> str:
    """Format metric for display"""
    return f"{value:.{decimals}f} {unit}".strip()
```

#### Calculation Functions

```python
def calculate_co2_savings(baseline: float, optimized: float) -> Dict:
    """Calculate CO₂ reduction percentage"""
    savings_kg = baseline - optimized
    savings_percent = (savings_kg / baseline) * 100
    return {"savings_kg": savings_kg, "savings_percent": savings_percent}
```

### 5. Visualization Factory Functions

#### Metrics Comparison Bar Chart

```python
def create_metrics_comparison_chart(results: Dict) -> go.Figure:
    """Create grouped bar chart comparing all metrics"""
    # Extracts values from results dict
    # Creates Plotly figure with 3 bars per metric
    # Configures layout and styling
```

**Metrics Compared**:
- Distance (km)
- Fuel (liters)
- CO₂ (kg)
- Delay (minutes)
- Total Cost

#### CO₂ Comparison Chart

```python
def create_co2_comparison_chart(results: Dict) -> go.Figure:
    """Create CO₂ emissions bar chart"""
    # Green color for optimized (low emissions)
    # Orange for greedy (medium)
    # Red for baseline (high)
```

#### Cost Comparison Chart

```python
def create_cost_comparison_chart(results: Dict) -> go.Figure:
    """Create total cost bar chart"""
    # Same color scheme as CO₂
    # Shows financial impact of optimization
```

### 6. Main UI Flow

```
main()
├── render_header()
├── load_graph_data()
├── render_sidebar()
│   ├── depot_selection
│   ├── delivery_stops_selection
│   ├── vehicle_parameters
│   ├── traffic_parameters
│   └── ga_parameters
├── render_run_button()
└── IF optimization_results:
    ├── render_kpis()
    ├── render_comparison_table()
    ├── render_visualizations()
    ├── render_summary()
    └── render_export_buttons()
```

## Backend Integration

### Backend Functions Called

```python
# Initialize comparison system
comparison = BaselineComparison(graph=graph, delay_model=delay_model)

# Run optimization with user parameters
results = comparison.run_comparison(
    start_node=selected_depot,           # Selected depot
    delivery_nodes=selected_delivery_stops,  # Selected stops
    load_kg=vehicle_load_kg,              # Vehicle load
    area_type=area_type,                  # Urban/Highway
    hour_of_day=hour_of_day,              # Time for traffic
    ga_generations=ga_generations        # GA iterations
)
```

### Results Structure

```python
results = {
    "baseline": {
        "distance_km": float,
        "fuel_liters": float,
        "co2_kg": float,
        "delay_minutes": float,
        "total_cost": float
    },
    "greedy": {...},           # Same structure
    "optimized": {...},        # Same structure
    "improvements": {
        "distance_km": float,  # % improvement
        "fuel_liters": float,
        "co2_kg": float,
        "delay_minutes": float,
        "total_cost": float
    }
}
```

## Code Organization

### Constants & Configuration

```python
GRAPH_PATH = "data/raw/osm/bangalore.graphml"
MODEL_DIR = "data/models"
```

### Imports Organization

```python
# UI Framework
import streamlit as st

# Data & Analysis
import pandas as pd
import numpy as np

# Visualization
import plotly.graph_objects as go
import plotly.express as px

# Utilities
import os
import sys
from typing import Dict, List, Any

# Project modules
from analytics.baseline_comparison import BaselineComparison
from prediction.delay_rules import DelayRulesEstimator
from utils.graph_builder import load_graphml, base_travel_time
```

## Extending the App

### Adding New Metrics

```python
# 1. Add calculation function
def calculate_new_metric(results):
    """Calculate custom metric"""
    return value

# 2. Add to display
st.metric("🎯 New Metric", calculate_new_metric(results))

# 3. Add to table
comparison_df["New Metric"] = [...]

# 4. Add to export
export_results["new_metric"] = calculate_new_metric(results)
```

### Adding New Visualization

```python
# 1. Create factory function
def create_new_chart(results: Dict) -> go.Figure:
    """Create custom visualization"""
    fig = go.Figure(...)
    fig.update_layout(...)
    return fig

# 2. Add to UI
st.plotly_chart(
    create_new_chart(results),
    use_container_width=True
)
```

### Adding New Parameter

```python
# 1. Add sidebar input
new_param = st.sidebar.slider(
    "New Parameter",
    min_value=0,
    max_value=100,
    value=50
)

# 2. Pass to backend
results = comparison.run_comparison(
    ...,
    new_param=new_param
)

# 3. Display result
st.write(f"Parameter used: {new_param}")
```

## Performance Considerations

### Current Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Load Graph | 30s | First run only, then cached |
| Run Baseline | 3-5s | Pure distance routing |
| Run Greedy | 5-10s | Considers all factors |
| Run GA (100 gen) | 30-60s | Evolutionary optimization |
| **Total** | ~45-75s | ~1 min typical |

### Optimization Strategies

#### 1. Increase Caching

```python
@st.cache_data
def expensive_calculation(param):
    """Cache calculation results"""
    return compute(param)
```

#### 2. Parallel Computation

```python
# Current: Sequential
# baseline → greedy → ga → results

# Potential: Parallel
# baseline, greedy, ga all run simultaneously
```

#### 3. Lazy Loading

```python
# Only load visualizations user is viewing
with st.expander("Advanced Metrics"):
    st.plotly_chart(advanced_chart())
```

### Resource Management

```
Memory Usage:
├── Road network: ~200-500 MB
├── Delay model: ~50 MB
├── GA population: ~10 MB
└── Results: ~1 MB
Total: ~300-700 MB

CPU Usage:
├── Graph operations: 50% utilization
├── GA optimization: 100% utilization (1 core)
└── UI rendering: 5% utilization
```

## Debugging

### Enable Debug Logging

```python
st.set_page_config(..., logger_level="debug")
```

### Debug Optimization Results

```python
# Add to main() function
st.write("Debug - Results:")
st.write(results)
```

### Check Backend Integration

```python
# Verify backend imports
from analytics.baseline_comparison import BaselineComparison
# If import fails, backend not installed correctly
```

### Profile Execution

```python
import time

start = time.time()
results = comparison.run_comparison(...)
elapsed = time.time() - start

st.write(f"Optimization took {elapsed:.2f} seconds")
```

## Testing

### Unit Tests for Helper Functions

```python
def test_calculate_co2_savings():
    baseline = 10.0
    optimized = 7.0
    result = calculate_co2_savings(baseline, optimized)
    assert result["savings_kg"] == 3.0
    assert result["savings_percent"] == 30.0
```

### Integration Tests

```python
def test_full_workflow():
    # Mock user inputs
    depot = 100
    stops = [101, 102, 103]
    
    # Run optimization
    results = run_optimization(depot, stops, ...)
    
    # Verify results
    assert "baseline" in results
    assert "greedy" in results
    assert "optimized" in results
```

### Manual Testing Checklist

- [ ] App starts without errors
- [ ] Graph loads successfully
- [ ] All sidebar inputs work
- [ ] Optimization completes
- [ ] Results display correctly
- [ ] Charts render properly
- [ ] Export buttons work
- [ ] No memory leaks (check RAM over time)

## Deployment Considerations

### Local Deployment

```bash
streamlit run streamlit_app.py
```

### Server Deployment

```bash
# Install on server
pip install streamlit==1.28.0

# Run as service
streamlit run streamlit_app.py --server.port 8501
```

### Docker Deployment

```dockerfile
FROM python:3.10
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8501
CMD ["streamlit", "run", "streamlit_app.py"]
```

### Environment Variables

```bash
# Set in deployment
export STREAMLIT_SERVER_PORT=8501
export STREAMLIT_LOGGER_LEVEL=warning
```

## Common Modifications

### Change Color Scheme

```python
# In visualization functions
colors = ["#FF6B6B", "#FFA500", "#4CAF50"]  # Modify these
```

### Change Weights in Cost Function

Edit [config/config.yaml](config/config.yaml):
```yaml
cost_function:
  weights:
    distance: 0.25  # Increase for distance-sensitive optimization
    fuel: 0.25
    co2: 0.30       # Increase for eco-friendly optimization
    delay: 0.20
```

### Add Custom Area Types

In [prediction/delay_rules.py](prediction/delay_rules.py):
```python
area_types = ["urban", "highway", "rural", "mountain"]
```

## Error Handling

### Current Error Handling

```python
try:
    comparison = initialize_comparison()
    results = comparison.run_comparison(...)
except Exception as e:
    st.error(f"❌ Error: {str(e)}")
    st.write(f"Debug: {e}")
```

### Improvements

```python
# Add specific error types
if not graph:
    st.error("Graph not available")
elif not delay_model:
    st.warning("Using fallback delay model")
else:
    proceed_with_optimization()
```

## Monitoring & Logging

### Add Logging

```python
import logging

logging.basicConfig(
    filename="streamlit_app.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# In code
logging.info(f"Running optimization with {len(selected_delivery_stops)} stops")
```

## Version Control

### Important Files to Track

```
streamlit_app.py (main UI)
STREAMLIT_UI_GUIDE.md (documentation)
STREAMLIT_QUICKSTART.md (quick start)
requirements.txt (dependencies)
```

### Changes to Backend

- Do NOT modify backend functions
- Backend changes handled by optimization team
- UI should adapt to backend API changes

## Future Enhancements

### Phase 2 Features

- [ ] Real-time route visualization on map
- [ ] Route history & comparison
- [ ] Custom cost function UI
- [ ] Batch optimization (multiple scenarios)
- [ ] API endpoint for programmatic access

### Phase 3 Features

- [ ] Historical performance tracking
- [ ] Route simulation
- [ ] Driver assignment
- [ ] Real-time traffic integration
- [ ] Mobile app version

---

**Maintainer**: AI Development Team  
**Last Updated**: January 2026  
**Status**: Production Ready  
**Python Version**: 3.8+  
**Streamlit Version**: 1.28.0+
