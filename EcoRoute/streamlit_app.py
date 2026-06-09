"""
GreenRoute - Streamlit UI for Eco-friendly Delivery Route Optimization
Visualization and comparison dashboard for routing strategies.

This UI displays results from the backend routing optimization system,
allowing users to compare different optimization methods (Baseline, Greedy, GA)
and visualize CO₂ savings and cost improvements.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import os
import sys
from typing import Dict, List, Any, Optional
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    from analytics.baseline_comparison import BaselineComparison
    from prediction.delay_rules import DelayRulesEstimator
    from utils.graph_builder import load_graphml, base_travel_time
    USE_REAL_BACKEND = True
except ImportError:
    from analytics.mock_backend import MockBaselineComparison as BaselineComparison
    from analytics.mock_backend import MockDelayModel as DelayRulesEstimator
    USE_REAL_BACKEND = False

# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="GreenRoute - Routing Optimization",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# CUSTOM STYLING
# ============================================================================

st.markdown("""
<style>
    .metric-card {
        background-color: #f0f2f6;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
    }
    .header-title {
        color: #1f77b4;
        font-size: 2.5em;
        font-weight: bold;
        margin-bottom: 10px;
    }
    .improvement-positive {
        color: #28a745;
        font-weight: bold;
    }
    .improvement-negative {
        color: #dc3545;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# ============================================================================
# CACHE & STATE MANAGEMENT
# ============================================================================

@st.cache_resource
def load_graph_data():
    """Load and cache the road network graph."""
    if not USE_REAL_BACKEND:
        # Return mock graph for demo purposes - no errors
        return None
    
    graph_path = "data/raw/osm/bangalore.graphml"
    
    if not os.path.exists(graph_path):
        return None
    
    try:
        graph = load_graphml(graph_path)
        graph = base_travel_time(graph, speed_kmph=30)
        return graph
    except Exception as e:
        return None


@st.cache_resource
def initialize_delay_model():
    """Initialize and cache the delay prediction model."""
    try:
        return DelayRulesEstimator(is_weekend=False)
    except Exception as e:
        st.warning(f"⚠️ Could not initialize delay model: {str(e)}")
        return None


def initialize_comparison():
    """Initialize BaselineComparison with loaded graph and delay model."""
    if USE_REAL_BACKEND:
        graph = load_graph_data()
        delay_model = initialize_delay_model()
        
        if graph is None:
            return None
        
        return BaselineComparison(graph=graph, delay_model=delay_model)
    else:
        # Use mock backend
        return BaselineComparison(graph=None, delay_model=None)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_sample_nodes(graph, num_samples: int = 20) -> List[int]:
    """Get sample nodes from the graph for selection."""
    if graph is None or USE_REAL_BACKEND is False:
        # Return mock nodes for demo
        return list(range(100, 115))  # 15 mock nodes
    
    nodes = list(graph.nodes())
    return nodes[:min(num_samples, len(nodes))]


def format_metric(value: float, unit: str = "", decimals: int = 2) -> str:
    """Format a metric value for display."""
    if isinstance(value, (int, float)):
        return f"{value:.{decimals}f} {unit}".strip()
    return str(value)


def calculate_co2_savings(baseline_co2: float, optimized_co2: float) -> Dict[str, Any]:
    """Calculate CO₂ savings between baseline and optimized routes."""
    if baseline_co2 <= 0:
        return {"savings_kg": 0, "savings_percent": 0}
    
    savings_kg = baseline_co2 - optimized_co2
    savings_percent = (savings_kg / baseline_co2) * 100 if baseline_co2 > 0 else 0
    
    return {
        "savings_kg": savings_kg,
        "savings_percent": savings_percent
    }


def calculate_cost_savings(baseline_cost: float, optimized_cost: float) -> Dict[str, Any]:
    """Calculate cost savings between baseline and optimized routes."""
    if baseline_cost <= 0:
        return {"savings": 0, "savings_percent": 0}
    
    savings = baseline_cost - optimized_cost
    savings_percent = (savings / baseline_cost) * 100 if baseline_cost > 0 else 0
    
    return {
        "savings": savings,
        "savings_percent": savings_percent
    }


def create_comparison_dataframe(results: Dict[str, Any]) -> pd.DataFrame:
    """Create a formatted comparison DataFrame from results."""
    metrics_list = [
        ("Distance (km)", "distance_km", 2),
        ("Fuel (liters)", "fuel_liters", 2),
        ("CO₂ Emissions (kg)", "co2_kg", 2),
        ("Delivery Delay (min)", "delay_minutes", 1),
        ("Total Cost", "total_cost", 4),
    ]
    
    data = []
    
    for metric_name, metric_key, decimals in metrics_list:
        baseline_val = results["baseline"].get(metric_key, 0)
        greedy_val = results["greedy"].get(metric_key, 0)
        optimized_val = results["optimized"].get(metric_key, 0)
        
        improvement = ""
        if baseline_val > 0:
            improvement_percent = ((baseline_val - optimized_val) / baseline_val) * 100
            improvement = f"{improvement_percent:.1f}%"
        
        data.append({
            "Metric": metric_name,
            "Baseline": f"{baseline_val:.{decimals}f}",
            "Greedy": f"{greedy_val:.{decimals}f}",
            "Optimized (GA)": f"{optimized_val:.{decimals}f}",
            "Improvement": improvement
        })
    
    return pd.DataFrame(data)


def create_metrics_comparison_chart(results: Dict[str, Any]) -> go.Figure:
    """Create a comparison bar chart for all metrics."""
    metrics = ["distance_km", "fuel_liters", "co2_kg", "delay_minutes", "total_cost"]
    metric_labels = ["Distance (km)", "Fuel (L)", "CO₂ (kg)", "Delay (min)", "Cost"]
    
    baseline_vals = [results["baseline"].get(m, 0) for m in metrics]
    greedy_vals = [results["greedy"].get(m, 0) for m in metrics]
    optimized_vals = [results["optimized"].get(m, 0) for m in metrics]
    
    fig = go.Figure(data=[
        go.Bar(name="Baseline (Dijkstra)", x=metric_labels, y=baseline_vals, marker_color="rgba(100, 100, 200, 0.7)"),
        go.Bar(name="Greedy", x=metric_labels, y=greedy_vals, marker_color="rgba(100, 180, 100, 0.7)"),
        go.Bar(name="Optimized (GA)", x=metric_labels, y=optimized_vals, marker_color="rgba(200, 100, 100, 0.7)"),
    ])
    
    fig.update_layout(
        title="🔄 Routing Strategy Comparison",
        barmode="group",
        hovermode="x unified",
        height=400,
        showlegend=True,
        xaxis_title="Metrics",
        yaxis_title="Value",
        template="plotly_white",
    )
    
    return fig


def create_co2_comparison_chart(results: Dict[str, Any]) -> go.Figure:
    """Create a CO₂ emissions comparison pie/bar chart."""
    strategies = ["Baseline", "Greedy", "Optimized (GA)"]
    co2_values = [
        results["baseline"]["co2_kg"],
        results["greedy"]["co2_kg"],
        results["optimized"]["co2_kg"]
    ]
    colors = ["#FF6B6B", "#FFA500", "#4CAF50"]
    
    fig = go.Figure(data=[
        go.Bar(
            x=strategies,
            y=co2_values,
            marker_color=colors,
            text=[f"{v:.2f} kg" for v in co2_values],
            textposition="auto",
        )
    ])
    
    fig.update_layout(
        title="🌱 CO₂ Emissions Comparison",
        xaxis_title="Strategy",
        yaxis_title="CO₂ (kg)",
        height=350,
        showlegend=False,
        template="plotly_white",
    )
    
    return fig


def create_cost_comparison_chart(results: Dict[str, Any]) -> go.Figure:
    """Create a cost comparison chart."""
    strategies = ["Baseline", "Greedy", "Optimized (GA)"]
    cost_values = [
        results["baseline"]["total_cost"],
        results["greedy"]["total_cost"],
        results["optimized"]["total_cost"]
    ]
    colors = ["#FF6B6B", "#FFA500", "#4CAF50"]
    
    fig = go.Figure(data=[
        go.Bar(
            x=strategies,
            y=cost_values,
            marker_color=colors,
            text=[f"${v:.4f}" for v in cost_values],
            textposition="auto",
        )
    ])
    
    fig.update_layout(
        title="💰 Total Cost Comparison",
        xaxis_title="Strategy",
        yaxis_title="Total Cost",
        height=350,
        showlegend=False,
        template="plotly_white",
    )
    
    return fig


def create_improvement_gauge_chart(improvement_percent: float, metric_name: str) -> go.Figure:
    """Create a gauge chart for showing improvement percentage."""
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=improvement_percent,
        title={'text': f"{metric_name} Improvement"},
        delta={'reference': 0},
        gauge={'axis': {'range': [0, 100]},
               'bar': {'color': "darkgreen" if improvement_percent > 0 else "darkred"},
               'steps': [
                   {'range': [0, 25], 'color': "lightgray"},
                   {'range': [25, 50], 'color': "gray"},
                   {'range': [50, 75], 'color': "lightgreen"},
                   {'range': [75, 100], 'color': "darkgreen"}
               ],
               'threshold': {'line': {'color': "red", 'width': 4},
                            'thickness': 0.75,
                            'value': 90}}
    ))
    
    fig.update_layout(height=300)
    return fig


# ============================================================================
# MAIN UI LAYOUT
# ============================================================================

def main():
    """Main Streamlit application."""
    
    # Header
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown('<div class="header-title">🌍 GreenRoute</div>', unsafe_allow_html=True)
        st.markdown("**Eco-friendly Delivery Route Optimization Dashboard**")
    with col2:
        st.image("https://img.icons8.com/color/96/000000/leaf--v1.png", width=96)
    
    if not USE_REAL_BACKEND:
        st.info("ℹ️ Demo Mode: Using simulated data for testing. For production, ensure graph file exists at data/raw/osm/bangalore.graphml")
    
    st.divider()
    
    # ========================================================================
    # SIDEBAR - USER INPUTS
    # ========================================================================
    
    st.sidebar.title("⚙️ Optimization Settings")
    
    # Load graph for node selection (or use mock)
    if USE_REAL_BACKEND:
        graph = load_graph_data()
    else:
        graph = None
    
    # Get available nodes (mock or real)
    sample_nodes = get_sample_nodes(graph, num_samples=50)
    
    # Sidebar: Depot Selection
    st.sidebar.subheader("📍 Depot Selection")
    depot_index = st.sidebar.selectbox(
        "Select starting depot:",
        range(len(sample_nodes)),
        format_func=lambda x: f"Node {sample_nodes[x]}"
    )
    selected_depot = sample_nodes[depot_index]
    st.sidebar.success(f"✅ Depot: Node {selected_depot}")
    
    # Sidebar: Delivery Stops
    st.sidebar.subheader("📦 Delivery Stops")
    available_stops = [n for n in sample_nodes if n != selected_depot]
    available_stop_labels = [f"Node {n}" for n in available_stops]
    
    selected_stops_indices = st.sidebar.multiselect(
        "Select delivery stops (min 2, max 5):",
        range(len(available_stops)),
        default=list(range(min(3, len(available_stops)))),
        format_func=lambda x: f"Node {available_stops[x]}"
    )
    
    # Validate number of stops
    if len(selected_stops_indices) < 2:
        st.sidebar.warning("⚠️ Please select at least 2 delivery stops")
        return
    
    if len(selected_stops_indices) > 5:
        st.sidebar.error("❌ Maximum 5 delivery stops allowed")
        return
    
    selected_delivery_stops = [available_stops[i] for i in selected_stops_indices]
    st.sidebar.success(f"✅ Selected {len(selected_delivery_stops)} delivery stops")
    
    # Sidebar: Vehicle Load
    st.sidebar.subheader("🚚 Vehicle Parameters")
    vehicle_load_kg = st.sidebar.slider(
        "Vehicle Load (kg):",
        min_value=5,
        max_value=200,
        value=40,
        step=5
    )
    st.sidebar.info(f"💡 Load: {vehicle_load_kg} kg")
    
    # Sidebar: Area Type
    area_type = st.sidebar.selectbox(
        "Area Type:",
        ["urban", "highway"],
        help="Urban = city streets, Highway = main roads"
    )
    
    # Sidebar: Hour of Day (for delay prediction)
    hour_of_day = st.sidebar.slider(
        "Hour of Day (for traffic patterns):",
        min_value=0,
        max_value=23,
        value=9,
        step=1
    )
    st.sidebar.caption(f"🕐 {hour_of_day:02d}:00")
    
    # Sidebar: GA Parameters
    st.sidebar.subheader("🧬 Genetic Algorithm")
    ga_generations = st.sidebar.slider(
        "GA Generations:",
        min_value=50,
        max_value=300,
        value=100,
        step=50
    )
    
    # ========================================================================
    # MAIN CONTENT - RUN OPTIMIZATION
    # ========================================================================
    
    st.markdown("### 🚀 Route Optimization")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.write(f"""
        **Optimization Configuration:**
        - 📍 Depot: Node {selected_depot}
        - 📦 Delivery Stops: {len(selected_delivery_stops)} stops
        - 🚚 Vehicle Load: {vehicle_load_kg} kg
        - 🗺️ Area Type: {area_type.capitalize()}
        - 🕐 Time: {hour_of_day:02d}:00
        - 🧬 GA Generations: {ga_generations}
        """)
    
    run_button = st.button(
        "▶️ Run Optimization",
        use_container_width=True,
        type="primary",
        key="run_optimization"
    )
    
    if run_button:
        # Initialize comparison and run optimization
        with st.spinner("⏳ Running optimization... this may take a minute"):
            try:
                comparison = initialize_comparison()
                
                if comparison is None:
                    st.error("❌ Could not initialize comparison system")
                    return
                
                # Run the optimization
                results = comparison.run_comparison(
                    start_node=selected_depot,
                    delivery_nodes=selected_delivery_stops,
                    load_kg=vehicle_load_kg,
                    area_type=area_type,
                    hour_of_day=hour_of_day,
                    ga_generations=ga_generations
                )
                
                # Store results in session state
                st.session_state.optimization_results = results
                st.session_state.comparison = comparison
                st.success("✅ Optimization completed successfully!")
                
            except Exception as e:
                st.error(f"❌ Error during optimization: {str(e)}")
                st.write(f"Debug: {e}")
                return
    
    # ========================================================================
    # RESULTS DISPLAY
    # ========================================================================
    
    if "optimization_results" in st.session_state and st.session_state.optimization_results is not None:
        results = st.session_state.optimization_results
        
        st.divider()
        st.markdown("## 📊 Results & Comparison")
        
        # ====================================================================
        # KEY METRICS - TOP ROW
        # ====================================================================
        
        st.markdown("### 🎯 Key Performance Indicators")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        # CO₂ Savings
        co2_savings = calculate_co2_savings(
            results["baseline"]["co2_kg"],
            results["optimized"]["co2_kg"]
        )
        with col1:
            st.metric(
                "🌱 CO₂ Savings",
                f"{co2_savings['savings_kg']:.2f} kg",
                f"{co2_savings['savings_percent']:.1f}%",
                delta_color="normal"
            )
        
        # Cost Savings
        cost_savings = calculate_cost_savings(
            results["baseline"]["total_cost"],
            results["optimized"]["total_cost"]
        )
        with col2:
            st.metric(
                "💰 Cost Savings",
                f"${cost_savings['savings']:.4f}",
                f"{cost_savings['savings_percent']:.1f}%",
                delta_color="normal"
            )
        
        # Distance Savings
        distance_savings = (
            (results["baseline"]["distance_km"] - results["optimized"]["distance_km"])
            / results["baseline"]["distance_km"] * 100
            if results["baseline"]["distance_km"] > 0 else 0
        )
        with col3:
            st.metric(
                "📏 Distance Reduction",
                f"{results['optimized']['distance_km']:.2f} km",
                f"{distance_savings:.1f}%",
                delta_color="inverse"
            )
        
        # Fuel Savings
        fuel_savings = (
            (results["baseline"]["fuel_liters"] - results["optimized"]["fuel_liters"])
            / results["baseline"]["fuel_liters"] * 100
            if results["baseline"]["fuel_liters"] > 0 else 0
        )
        with col4:
            st.metric(
                "⛽ Fuel Savings",
                f"{results['optimized']['fuel_liters']:.2f} L",
                f"{fuel_savings:.1f}%",
                delta_color="inverse"
            )
        
        # Delay Savings
        delay_savings = (
            (results["baseline"]["delay_minutes"] - results["optimized"]["delay_minutes"])
            / results["baseline"]["delay_minutes"] * 100
            if results["baseline"]["delay_minutes"] > 0 else 0
        )
        with col5:
            st.metric(
                "⏱️ Delay Reduction",
                f"{results['optimized']['delay_minutes']:.1f} min",
                f"{delay_savings:.1f}%",
                delta_color="inverse"
            )
        
        st.divider()
        
        # ====================================================================
        # DETAILED COMPARISON TABLE
        # ====================================================================
        
        st.markdown("### 📋 Detailed Comparison Table")
        
        comparison_df = create_comparison_dataframe(results)
        st.dataframe(
            comparison_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Metric": st.column_config.TextColumn(width="medium"),
                "Baseline": st.column_config.TextColumn(width="small"),
                "Greedy": st.column_config.TextColumn(width="small"),
                "Optimized (GA)": st.column_config.TextColumn(width="small"),
                "Improvement": st.column_config.TextColumn(width="small"),
            }
        )
        
        st.divider()
        
        # ====================================================================
        # VISUALIZATIONS - METRICS COMPARISON
        # ====================================================================
        
        st.markdown("### 📈 Visualizations")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.plotly_chart(
                create_co2_comparison_chart(results),
                use_container_width=True
            )
        
        with col2:
            st.plotly_chart(
                create_cost_comparison_chart(results),
                use_container_width=True
            )
        
        # Full metrics comparison
        st.plotly_chart(
            create_metrics_comparison_chart(results),
            use_container_width=True
        )
        
        st.divider()
        
        # ====================================================================
        # SUMMARY
        # ====================================================================
        
        st.markdown("### ✅ Optimization Summary")
        
        summary_text = f"""
        #### Route Details
        - **Depot**: Node {selected_depot}
        - **Stops**: {len(selected_delivery_stops)} delivery locations
        - **Vehicle Load**: {vehicle_load_kg} kg
        
        #### Optimized Route Results
        - **Total Distance**: {results['optimized']['distance_km']:.2f} km
        - **Fuel Consumption**: {results['optimized']['fuel_liters']:.2f} liters
        - **CO₂ Emissions**: {results['optimized']['co2_kg']:.2f} kg
        - **Estimated Delay**: {results['optimized']['delay_minutes']:.1f} minutes
        - **Total Cost**: ${results['optimized']['total_cost']:.4f}
        
        #### Improvements vs Baseline
        - **Distance Reduction**: {distance_savings:.1f}%
        - **Fuel Savings**: {fuel_savings:.1f}%
        - **CO₂ Reduction**: {co2_savings['savings_percent']:.1f}%
        - **Cost Savings**: {cost_savings['savings_percent']:.1f}%
        """
        
        st.info(summary_text)
        
        # ====================================================================
        # EXPORT OPTIONS
        # ====================================================================
        
        st.divider()
        st.markdown("### 💾 Export Results")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Export as CSV
            csv_data = comparison_df.to_csv(index=False)
            st.download_button(
                label="📥 Download Comparison Table (CSV)",
                data=csv_data,
                file_name="route_comparison.csv",
                mime="text/csv"
            )
        
        with col2:
            # Export detailed results as JSON
            import json
            
            export_results = {
                "optimization_config": {
                    "depot": int(selected_depot),
                    "delivery_stops": [int(n) for n in selected_delivery_stops],
                    "vehicle_load_kg": vehicle_load_kg,
                    "area_type": area_type,
                    "hour_of_day": hour_of_day,
                    "ga_generations": ga_generations
                },
                "results": {
                    "baseline": {k: float(v) if isinstance(v, (int, float)) else v
                                for k, v in results["baseline"].items()},
                    "greedy": {k: float(v) if isinstance(v, (int, float)) else v
                              for k, v in results["greedy"].items()},
                    "optimized": {k: float(v) if isinstance(v, (int, float)) else v
                                 for k, v in results["optimized"].items()},
                    "improvements": {k: float(v) if isinstance(v, (int, float)) else v
                                    for k, v in results["improvements"].items()}
                }
            }
            
            json_data = json.dumps(export_results, indent=2)
            st.download_button(
                label="📥 Download Full Results (JSON)",
                data=json_data,
                file_name="route_optimization_results.json",
                mime="application/json"
            )


# ============================================================================
# APP ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    # Initialize session state
    if "optimization_results" not in st.session_state:
        st.session_state.optimization_results = None
    
    main()
