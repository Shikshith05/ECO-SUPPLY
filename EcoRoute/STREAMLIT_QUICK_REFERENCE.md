# GreenRoute Streamlit UI - Quick Reference Card

## 🚀 LAUNCH IN 30 SECONDS

```bash
# Navigate to project
cd c:\Users\admin\Desktop\projects\EcoRoute

# Install (first time only)
pip install -r requirements.txt

# Launch
streamlit run streamlit_app.py
```

**Output**: Browser opens to `http://localhost:8501`

---

## 📋 SIDEBAR CONFIGURATION

| Setting | Range | Default | Notes |
|---------|-------|---------|-------|
| **Depot** | Any node | - | Starting point for route |
| **Delivery Stops** | 2-5 stops | 3 | Must select at least 2 |
| **Vehicle Load** | 5-200 kg | 40 | Affects fuel & CO₂ |
| **Area Type** | urban/highway | urban | Affects speed & delays |
| **Hour of Day** | 0-23 | 9 | For traffic prediction |
| **GA Generations** | 50-300 | 100 | More = better results (slower) |

---

## 🎯 TYPICAL WORKFLOW

```
1. Configure parameters (sidebar)
        ↓
2. Click [▶️ RUN OPTIMIZATION]
        ↓
3. Wait for ✅ Optimization completed
        ↓
4. Review 5 KPI Cards (top row)
        ↓
5. Study Comparison Table
        ↓
6. Examine Charts
        ↓
7. Download CSV or JSON
```

**Total Time**: ~5 minutes per scenario

---

## 📊 UNDERSTANDING RESULTS

### Top 5 KPI Cards

| Card | Meaning | Lower is Better? |
|------|---------|-----------------|
| 🌱 CO₂ Savings | kg reduction vs baseline | ✓ Yes |
| 💰 Cost Savings | $ reduction vs baseline | ✓ Yes |
| 📏 Distance Reduction | km reduction vs baseline | ✓ Yes |
| ⛽ Fuel Savings | L reduction vs baseline | ✓ Yes |
| ⏱️ Delay Reduction | min reduction vs baseline | ✓ Yes |

### Interpretation Example

```
Baseline: 25.5 km, 0.3250 cost
Optimized: 19.8 km, 0.2450 cost

Distance Reduction: (25.5 - 19.8) / 25.5 × 100 = 22.4%
Cost Savings: (0.3250 - 0.2450) / 0.3250 × 100 = 24.6%
```

---

## 🔤 THREE ROUTING STRATEGIES

| Strategy | What It Does | Speed | Quality |
|----------|-------------|-------|---------|
| **Baseline (Dijkstra)** | Distance only | ⚡⚡⚡ Fast | ⭐ Basic |
| **Greedy** | Considers all factors | ⚡⚡ Medium | ⭐⭐ Good |
| **Optimized (GA)** | Evolutionary search | ⚡ Slow | ⭐⭐⭐ Best |

---

## ⚡ PERFORMANCE TIPS

| Goal | Recommendation |
|------|-----------------|
| **Fast testing** | GA Generations = 50 |
| **Balanced** | GA Generations = 100 |
| **Best results** | GA Generations = 150+ |
| **Many scenarios** | Use fewer stops (2-3) |
| **Production** | GA Generations = 150-200 |

**Rough timing**: Each 50 GA generations ≈ 15-30 seconds

---

## 💾 EXPORT OPTIONS

### CSV Export
- **File**: `route_comparison.csv`
- **Use**: Spreadsheet, reports, shared analysis
- **Content**: Comparison table with all metrics

### JSON Export
- **File**: `route_optimization_results.json`
- **Use**: Data analysis, archival, API integration
- **Content**: Full config + all results + improvements

---

## ⚠️ COMMON ISSUES & FIXES

| Issue | Fix |
|-------|-----|
| App won't start | `pip install streamlit>=1.28.0` |
| "Graph not found" | Run `python main.py` first |
| "Need 2+ stops" | Select at least 2 in multi-select |
| "Too slow" | Reduce GA Generations to 50 |
| "Nodes not connected" | Try different node combinations |

---

## 🎨 CHART LEGEND

### Bar Charts Color Scheme
- 🔴 **Red**: Baseline (highest values - baseline strategy)
- 🟠 **Orange**: Greedy (medium values - greedy strategy)
- 🟢 **Green**: Optimized (lowest values - best strategy)

### What Each Chart Shows

| Chart | Metrics Shown | Purpose |
|-------|---------------|---------|
| CO₂ Comparison | Carbon emissions (kg) | Environmental impact |
| Cost Comparison | Total cost | Financial impact |
| Metrics Comparison | All 5 metrics | Comprehensive view |

---

## 📱 KEYBOARD SHORTCUTS

| Action | Shortcut |
|--------|----------|
| Refresh | Ctrl+Shift+R |
| Clear cache | Cmd/Ctrl+Shift+Del |
| Rerun | Ctrl+R |
| Report issue | Click browser's refresh |

---

## 🔍 KEY METRICS REFERENCE

| Metric | Unit | Typical Range | Formula |
|--------|------|----------------|---------|
| Distance | km | 5-30 | Sum of all segments |
| Fuel | liters | 0.3-4.0 | distance × efficiency |
| CO₂ | kg | 0.8-10 | fuel × emission_factor |
| Delay | min | 0-45 | Traffic + stops |
| Cost | (weighted) | 0.1-1.0 | Weighted sum of metrics |

---

## 🎯 OPTIMIZATION SCENARIOS

### Scenario 1: Fast Delivery (City)
```
Load: 20 kg (light)
Area: Urban
Hour: 14 (afternoon, less traffic)
GA Generations: 50 (fast)
Expected: Low cost, moderate CO₂
```

### Scenario 2: Heavy Delivery (Highway)
```
Load: 100 kg (heavy)
Area: Highway
Hour: 6 (early morning)
GA Generations: 150 (thorough)
Expected: Higher fuel, CO₂ but efficient
```

### Scenario 3: Eco-Friendly (Evening)
```
Load: 40 kg (medium)
Area: Urban
Hour: 18 (evening, peak traffic)
GA Generations: 200 (best results)
Expected: Best CO₂ optimization
```

---

## 🔗 IMPORTANT PATHS

| Path | Purpose |
|------|---------|
| `streamlit_app.py` | Main application (run this) |
| `config/config.yaml` | Cost weights configuration |
| `data/raw/osm/bangalore.graphml` | Road network graph |
| `STREAMLIT_QUICKSTART.md` | 5-minute guide |
| `STREAMLIT_UI_GUIDE.md` | Complete documentation |

---

## 📞 TROUBLESHOOTING FLOWCHART

```
App won't start
├─ pip install streamlit [YES] → Try again
└─ File not found [YES] → Download graph: python main.py

Optimization fails
├─ Nodes not selected [YES] → Select 2+ stops
├─ Graph not loaded [YES] → Run python main.py
└─ Out of memory [YES] → Use fewer stops/generations

Results look wrong
├─ Check if all 3 strategies present [YES] → Report issue
├─ Verify input parameters match sidebar [YES] → Re-run
└─ Compare metrics range table [YES] → Results OK
```

---

## 📊 COMPARISON TABLE LEGEND

```
Metric            │ Baseline  │ Greedy    │ Optimized │ Improvement
                  │ (Pure)    │ (Heuristic)│ (GA)     │ (GA vs Base)
──────────────────┼───────────┼──────────┼──────────┼─────────────
Distance (km)     │ 25.50     │ 22.10    │ 19.80    │ 22.4%
Fuel (liters)     │ 3.06      │ 2.65     │ 2.38     │ 22.2%
CO₂ Emissions (kg) │ 7.07     │ 6.12     │ 5.48     │ 22.5%
Delay (minutes)   │ 15.00     │ 14.50    │ 13.20    │ 12.0%
Total Cost        │ 0.3250    │ 0.2890   │ 0.2450   │ 24.6%
```

Lower numbers = Better = Green in GA column

---

## 🚀 POWER USER TIPS

1. **Batch Testing**: Run 5-10 different scenarios, save all JSON results
2. **Time Analysis**: Compare different hours (6, 9, 12, 15, 18, 21) to find best times
3. **Load Testing**: Vary vehicle load to find optimal capacity
4. **Route Stability**: Run same route 3 times (GA is stochastic) to check variance
5. **Cost Optimization**: Adjust weights in `config.yaml`, re-run to compare

---

## ⏱️ TIMING REFERENCE

| Operation | Time | First Run | Subsequent |
|-----------|------|-----------|------------|
| App start | 2-3s | ✓ | ✓ |
| Graph load | 30s | ✓ | - |
| Model init | 5s | ✓ | - |
| Optimization | 45-75s | ✓ | ✓ |
| Display | ~2s | ✓ | ✓ |
| **TOTAL FIRST** | **~90s** | | |
| **TOTAL SUBSEQUENT** | **~50s** | | |

---

## 🎓 LEARNING PATH

### Beginner (15 minutes)
- [ ] Read STREAMLIT_QUICKSTART.md
- [ ] Run app with default settings
- [ ] View example results
- [ ] Download one CSV

### Intermediate (45 minutes)
- [ ] Read STREAMLIT_UI_GUIDE.md
- [ ] Try 5+ different parameter combinations
- [ ] Understand metrics
- [ ] Compare results

### Advanced (2+ hours)
- [ ] Read STREAMLIT_DEVELOPER_DOCS.md
- [ ] Modify visualizations
- [ ] Integrate with external systems
- [ ] Deploy to server

---

## 📋 CHECKLIST FOR SUCCESSFUL RUN

- [ ] Python 3.8+ installed
- [ ] `pip install -r requirements.txt` completed
- [ ] `data/raw/osm/bangalore.graphml` exists (or ran `python main.py`)
- [ ] No errors in terminal
- [ ] Browser opened to `http://localhost:8501`
- [ ] Sidebar configuration visible
- [ ] Can click "Run Optimization"
- [ ] Results display after optimization
- [ ] Can download CSV/JSON files

---

**Version**: 1.0  
**Last Updated**: January 2026  
**Status**: Ready to Use

For full documentation, see:
- Quick Start: `STREAMLIT_QUICKSTART.md`
- Complete Guide: `STREAMLIT_UI_GUIDE.md`
- Developer Docs: `STREAMLIT_DEVELOPER_DOCS.md`
