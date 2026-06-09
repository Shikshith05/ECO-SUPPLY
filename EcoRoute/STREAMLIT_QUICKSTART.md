# 🚀 Quick Start Guide - GreenRoute Streamlit UI

## Installation (60 seconds)

### 1. Install Dependencies

```bash
# Navigate to EcoRoute directory
cd c:\Users\admin\Desktop\projects\EcoRoute

# Install all requirements including Streamlit
pip install -r requirements.txt
```

### 2. Verify Installation

```bash
# Check Streamlit is installed
streamlit --version

# Check road network exists
ls data/raw/osm/bangalore.graphml
```

If the graph file doesn't exist, run:
```bash
python main.py
```

## Launch the App (5 seconds)

```bash
streamlit run streamlit_app.py
```

**Output**:
```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

Auto-opens browser at `http://localhost:8501` → **UI is ready!**

## First Run - Example Scenario (3 minutes)

### Configuration

1. **Left Sidebar Settings**:
   - Depot: Select any node (e.g., "Node 123")
   - Delivery Stops: Select 3 nodes (multi-select)
   - Vehicle Load: 40 kg (default is fine)
   - Area Type: urban
   - Hour of Day: 9
   - GA Generations: 100

2. **Click "▶️ Run Optimization"**
   - Status: ⏳ Running optimization...
   - Wait: ~30-60 seconds (first run slower due to caching)
   - Result: ✅ Optimization completed successfully!

3. **View Results**
   - Top cards show: CO₂ savings, cost savings, etc.
   - Comparison table shows all three strategies
   - Charts visualize the differences

4. **Export Results**
   - CSV: Download comparison table
   - JSON: Download full results

## What the App Does

```
INPUT (Sidebar)
├── Depot location
├── Delivery stops (2-5)
├── Vehicle load
├── Area type & time
└── GA parameters
        ↓
    [RUN OPTIMIZATION]
        ↓
BACKEND EXECUTION
├── Baseline Routing (Dijkstra)
├── Greedy Routing (multi-objective)
└── GA Optimization (evolutionary)
        ↓
OUTPUT (Dashboard)
├── KPI Cards (CO₂, Cost, Distance)
├── Comparison Table
├── Interactive Charts
└── Export Options (CSV/JSON)
```

## Key Metrics Explained

| Metric | What It Means | Lower is Better? |
|--------|---------------|-----------------|
| **Distance (km)** | Total route length | ✓ Yes |
| **Fuel (liters)** | Fuel consumption | ✓ Yes |
| **CO₂ (kg)** | Carbon emissions | ✓ Yes |
| **Delay (min)** | Traffic-based delay | ✓ Yes |
| **Cost** | Weighted composite score | ✓ Yes |

## Understanding Results

### Example Output

```
Baseline (Dijkstra):    Distance: 25.5 km | Cost: 0.3250
Greedy:                Distance: 22.1 km | Cost: 0.2890
Optimized (GA):        Distance: 19.8 km | Cost: 0.2450
                       
Improvement: 22.4% better than baseline
CO₂ Savings: 2.15 kg
Cost Savings: $0.0800
```

### Interpretation

- **Optimized (GA)** shows the best solution
- **Improvement %** = `(Baseline - GA) / Baseline * 100`
- **Greedy** is often between Baseline and GA
- **CO₂ Savings** = direct environmental benefit
- **Cost Savings** = business/operational benefit

## Common Issues & Fixes

### ❌ "Road network file not found"

**Fix**:
```bash
python main.py    # Downloads the graph
streamlit run streamlit_app.py
```

### ❌ "At least 2 delivery stops required"

**Fix**: Select at least 2 stops in the sidebar (currently selecting fewer)

### ❌ App runs very slowly

**Fix**:
- Reduce GA Generations from 100 → 50
- Use fewer delivery stops (2-3 instead of 5)
- Check system RAM (need 4GB minimum)

### ❌ "No path found from X to Y"

**Fix**: Try different node combinations (some nodes may not be connected in graph)

### ⚠️ "Could not initialize delay model"

**No Action Needed**: Falls back to rules-based estimator automatically

## Tips & Tricks

### ⚡ Speed Up Testing
```bash
# Run with reduced GA generations
# In sidebar: Set GA Generations to 50 (fastest)
```

### 📊 Better Visualizations
```bash
# Run on a larger screen (wide layout)
# Charts and tables render better on wider screens
```

### 🔄 Rerun Optimization
```bash
# Click "▶️ Run Optimization" again
# New seed = different GA results (optimization is stochastic)
```

### 💾 Save All Results
```bash
# After each run:
# 1. Download CSV for spreadsheet
# 2. Download JSON for records
```

## File Locations

| File | Purpose |
|------|---------|
| `streamlit_app.py` | Main UI application |
| `STREAMLIT_UI_GUIDE.md` | Full documentation |
| `STREAMLIT_QUICKSTART.md` | This file |
| `config/config.yaml` | Optimization weights |
| `data/raw/osm/bangalore.graphml` | Road network |

## Typical Session Timeline

```
0:00  → streamlit run streamlit_app.py
0:10  → Configure parameters in sidebar
0:15  → Click "Run Optimization"
0:20  → ⏳ Waiting for results...
1:15  → ✅ Results display
1:30  → Review metrics and charts
2:00  → Download results (CSV/JSON)
2:05  → End session
```

## Next Steps

1. ✅ Run the app with example parameters
2. ✅ Try different depot/stop combinations
3. ✅ Compare results across different times of day
4. ✅ Export results for reporting
5. ✅ Read full docs: [STREAMLIT_UI_GUIDE.md](STREAMLIT_UI_GUIDE.md)

## Advanced: Command-line Options

```bash
# Run on specific port
streamlit run streamlit_app.py --server.port 8000

# Run in headless mode (no browser auto-open)
streamlit run streamlit_app.py --logger.level=error

# Run with developer options
streamlit run streamlit_app.py --logger.level=debug

# Clear cache and restart
rm -rf ~/.streamlit/cache/
streamlit run streamlit_app.py
```

## Getting Help

| Issue | Resource |
|-------|----------|
| How to use Streamlit features | https://docs.streamlit.io |
| Project structure & backend | [README.md](README.md) |
| UI customization | [STREAMLIT_UI_GUIDE.md](STREAMLIT_UI_GUIDE.md) |
| Backend optimization details | [RUN_PIPELINE.md](RUN_PIPELINE.md) |

---

**Ready?** Open terminal, run `streamlit run streamlit_app.py` and start optimizing! 🚀

**Time to first result**: ~3 minutes  
**Difficulty**: Beginner-friendly  
**No coding required**: UI is fully self-contained
