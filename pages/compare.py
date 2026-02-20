"""
Compare Results Page
"""

import streamlit as st
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_manager import get_all_runs
from utils.visualizer import create_comparison_chart, create_scatter_plot

def show():
    st.header("📊 Compare Results")
    
    df = get_all_runs()
    
    if len(df) == 0:
        st.info("No runs yet. Run an analysis first!")
        return
    
    st.success(f"Found {len(df)} runs")
    
    # Filters
    col1, col2, col3 = st.columns(3)
    with col1:
        stands = ['All'] + sorted(df['stand_name'].unique().tolist())
        stand = st.selectbox("Stand:", stands)
    with col2:
        primaries = ['All'] + sorted(df['primary_strategy'].unique().tolist())
        primary = st.selectbox("Primary:", primaries)
    with col3:
        secondaries = ['All'] + sorted(df['secondary_strategy'].unique().tolist())
        secondary = st.selectbox("Secondary:", secondaries)
    
    # Apply filters
    filtered = df.copy()
    if stand != 'All':
        filtered = filtered[filtered['stand_name'] == stand]
    if primary != 'All':
        filtered = filtered[filtered['primary_strategy'] == primary]
    if secondary != 'All':
        filtered = filtered[filtered['secondary_strategy'] == secondary]
    
    st.info(f"Showing {len(filtered)} runs")
    
    # Sort
    sort_by = st.selectbox("Sort by:", ['final_mean_dbh', 'final_mean_height', 'growth_in_volume', 'ba_removal_pct'])
    filtered = filtered.sort_values(by=sort_by, ascending=False)
    
    # Table
    st.markdown("### Comparison Table")
    display_cols = ['primary_strategy', 'secondary_strategy', 'final_mean_dbh', 'final_mean_height', 
                    'growth_in_volume', 'ba_removal_pct', 'survival_rate']
    st.dataframe(filtered[display_cols], use_container_width=True, height=400)
    
    # Charts
    if len(filtered) > 1:
        st.markdown("### Visualizations")
        tab1, tab2 = st.tabs(["Bar Chart", "Scatter"])
        
        with tab1:
            metric = st.selectbox("Metric:", ['final_mean_dbh', 'final_mean_height', 'growth_in_volume'])
            fig = create_comparison_chart(filtered, metric)
            st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            fig = create_scatter_plot(filtered)
            st.plotly_chart(fig, use_container_width=True)
    
    # Export
    st.markdown("### Export")
    csv = filtered.to_csv(index=False)
    st.download_button("📥 Download CSV", csv, "comparison.csv", "text/csv")

if __name__ == "__main__":
    show()
