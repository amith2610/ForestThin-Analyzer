"""
Visualizer - Display results in Streamlit UI
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from PIL import Image
import os

def display_results(summary):
    """Display comprehensive results from a pipeline run"""
    
    # Extract data
    thin = summary['thinning_results']
    growth = summary['growth_projection']
    files = summary['output_files']
    
    # Key Metrics at top
    st.markdown("### 🎯 Key Results")
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "Mean DBH (Final)",
            f"{growth['final_mean_dbh']:.2f}\"",
            delta=f"+{growth['mean_dbh_growth']:.2f}\""
        )
    
    with col2:
        st.metric(
            "Mean Height (Final)",
            f"{growth['final_mean_height']:.2f}'",
            delta=f"+{growth['mean_height_growth']:.2f}'"
        )
    
    with col3:
        st.metric(
            "Volume Growth",
            f"{growth.get('growth_in_volume', 0):.0f} ft³"
        )
    
    with col4:
        st.metric(
            "BA Removed",
            f"{thin['ba_removal_pct']:.1f}%",
            delta=f"-{thin['trees_removed']:,} trees"
        )
    
    with col5:
        st.metric(
            "Survival",
            f"{growth['final_survival_rate']:.1f}%"
        )
    
    # Tabs for different views
    result_tab1, result_tab2, result_tab3, result_tab4 = st.tabs([
        "📊 Statistics", "🗺️ Maps", "📈 Growth Data", "📁 Files"
    ])
    
    # TAB 1: Statistics
    with result_tab1:
        st.markdown("### Thinning Statistics")
        
        thin_col1, thin_col2 = st.columns(2)
        
        with thin_col1:
            st.markdown("**Trees:**")
            st.write(f"• Before: {thin['trees_before']:,}")
            st.write(f"• After: {thin['trees_after']:,}")
            st.write(f"• Removed: {thin['trees_removed']:,} ({thin['pct_trees_removed']:.1f}%)")
            
            st.markdown("**Basal Area:**")
            st.write(f"• Before: {thin['ba_before_sqft']:.2f} ft²")
            st.write(f"• After: {thin['ba_after_sqft']:.2f} ft²")
            st.write(f"• Removed: {thin['ba_removed_sqft']:.2f} ft²")
        
        with thin_col2:
            st.markdown("**DBH:**")
            st.write(f"• Before: {thin['mean_dbh_before']:.2f}\"")
            st.write(f"• After: {thin['mean_dbh_after']:.2f}\"")
            st.write(f"• QMD Before: {thin['qmd_before']:.2f}\"")
            st.write(f"• QMD After: {thin['qmd_after']:.2f}\"")
        
        st.markdown("---")
        st.markdown("### Growth Projection")
        
        growth_col1, growth_col2 = st.columns(2)
        
        with growth_col1:
            st.markdown(f"**Final Size (Age {growth['final_age']}):**")
            st.write(f"• Mean DBH: {growth['final_mean_dbh']:.2f}\"")
            st.write(f"• Mean Height: {growth['final_mean_height']:.2f}'")
            st.write(f"• Total Volume: {growth.get('total_volume_final', 0):.2f} ft³")
        
        with growth_col2:
            st.markdown("**Growth:**")
            st.write(f"• DBH: +{growth['mean_dbh_growth']:.2f}\"")
            st.write(f"• Height: +{growth['mean_height_growth']:.2f}'")
            st.write(f"• Volume: +{growth.get('growth_in_volume', 0):.2f} ft³")
            st.write(f"• Survival: {growth['final_survival_rate']:.1f}%")
        
        # Per-acre metrics (if stand area was provided)
        per_acre = growth.get('per_acre_metrics', {})
        if per_acre:
            st.markdown("---")
            st.markdown("### Per-Acre Metrics")
            
            acre_col1, acre_col2, acre_col3 = st.columns(3)
            
            with acre_col1:
                st.metric("Trees/Acre", f"{per_acre['trees_per_acre']:.0f}")
            
            with acre_col2:
                st.metric("Volume/Acre", f"{per_acre['volume_per_acre']:.1f} ft³")
            
            with acre_col3:
                st.metric("Volume Growth/Acre", f"{per_acre['volume_growth_per_acre']:.1f} ft³")
    
    # TAB 2: Maps
    with result_tab2:
        st.markdown("### Spatial Visualization")
        
        # Find the run directory
        run_id = summary['run_id']
        output_dir = summary['configuration']['output']['directory']
        run_dir = os.path.join(output_dir, f"run_{run_id}")
        
        # First row: Primary and Secondary
        map_col1, map_col2 = st.columns(2)
        
        with map_col1:
            primary_map = os.path.join(run_dir, "01_primary_thinning_map.png")
            if os.path.exists(primary_map):
                st.markdown("**Primary Thinning:**")
                img = Image.open(primary_map)
                st.image(img, use_container_width=True)
        
        with map_col2:
            secondary_map = os.path.join(run_dir, "02_secondary_thinning_map.png")
            if os.path.exists(secondary_map):
                st.markdown("**After Secondary:**")
                img = Image.open(secondary_map)
                st.image(img, use_container_width=True)
        
        # Second row: Mortality map (full width)
        st.markdown("---")
        mortality_map = os.path.join(run_dir, "06_final_stand_mortality_map.png")
        if os.path.exists(mortality_map):
            st.markdown("**Final Stand - Mortality Visualization:**")
            img = Image.open(mortality_map)
            st.image(img, use_container_width=True)
    
    # TAB 3: Growth Data
    with result_tab3:
        st.markdown("### Year-by-Year Growth")
        
        run_id = summary['run_id']
        output_dir = summary['configuration']['output']['directory']
        run_dir = os.path.join(output_dir, f"run_{run_id}")
        growth_csv = os.path.join(run_dir, "05_growth_projections.csv")
        
        if os.path.exists(growth_csv):
            growth_df = pd.read_csv(growth_csv)
            st.dataframe(growth_df.head(20), use_container_width=True)
            
            # Growth chart
            dbh_cols = [col for col in growth_df.columns if col.startswith('DBH')]
            if len(dbh_cols) > 1:
                years = [0] + [int(col.split('+')[1]) for col in dbh_cols if '+' in col]
                mean_dbhs = [growth_df[col].mean() for col in dbh_cols]
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=years, y=mean_dbhs,
                    mode='lines+markers',
                    name='Mean DBH',
                    line=dict(color='#2E7D32', width=3)
                ))
                fig.update_layout(
                    title="Mean DBH Growth Over Time",
                    xaxis_title="Years After Thinning",
                    yaxis_title="Mean DBH (inches)",
                    height=400
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # DBH Distribution Histograms
            st.markdown("---")
            st.markdown("### DBH Distribution (2-inch Classes)")
            
            # Get initial and final DBH columns
            initial_dbh_col = 'DBH'
            if len(dbh_cols) > 1:
                final_dbh_col = [col for col in dbh_cols if '+' in col][-1]  # Last projection year
                
                # Create 2-inch bins
                max_dbh = max(growth_df[initial_dbh_col].max(), growth_df[final_dbh_col].max())
                bins = list(range(0, int(max_dbh) + 4, 2))  # 0, 2, 4, 6, 8, ...
                
                # Initial DBH distribution (all trees after thinning)
                initial_dbh = growth_df[initial_dbh_col].dropna()
                
                # Final DBH distribution (only alive trees)
                final_dbh = growth_df[final_dbh_col].dropna()
                
                # Create side-by-side histograms
                hist_col1, hist_col2 = st.columns(2)
                
                with hist_col1:
                    st.markdown("**Initial DBH (After Thinning):**")
                    fig1 = go.Figure()
                    fig1.add_trace(go.Histogram(
                        x=initial_dbh,
                        xbins=dict(start=0, end=max_dbh+2, size=2),
                        marker_color='steelblue',
                        name='Initial'
                    ))
                    fig1.update_layout(
                        xaxis_title="DBH Class (inches)",
                        yaxis_title="Number of Trees",
                        height=350,
                        bargap=0.1,
                        showlegend=False
                    )
                    st.plotly_chart(fig1, use_container_width=True)
                    st.caption(f"Total: {len(initial_dbh):,} trees")
                
                with hist_col2:
                    st.markdown(f"**Final DBH (Age {growth['final_age']}):**")
                    fig2 = go.Figure()
                    fig2.add_trace(go.Histogram(
                        x=final_dbh,
                        xbins=dict(start=0, end=max_dbh+2, size=2),
                        marker_color='forestgreen',
                        name='Final'
                    ))
                    fig2.update_layout(
                        xaxis_title="DBH Class (inches)",
                        yaxis_title="Number of Trees",
                        height=350,
                        bargap=0.1,
                        showlegend=False
                    )
                    st.plotly_chart(fig2, use_container_width=True)
                    mortality = len(initial_dbh) - len(final_dbh)
                    st.caption(f"Total: {len(final_dbh):,} trees (Mortality: {mortality:,})")
                
                # Trees per acre by size class (if stand area provided)
                per_acre = growth.get('per_acre_metrics', {})
                if per_acre and 'tpa_by_dbh_class' in per_acre:
                    st.markdown("---")
                    st.markdown("### Trees Per Acre by DBH Class")
                    
                    tpa_data = per_acre['tpa_by_dbh_class']
                    bins = tpa_data['bins']
                    counts = tpa_data['counts']
                    
                    # Create labels for x-axis
                    labels = [f"{b}-{b+2}\"" for b in bins]
                    
                    fig_tpa = go.Figure()
                    fig_tpa.add_trace(go.Bar(
                        x=labels,
                        y=counts,
                        marker_color='steelblue',
                        name='TPA'
                    ))
                    fig_tpa.update_layout(
                        xaxis_title="DBH Class (inches)",
                        yaxis_title="Trees Per Acre",
                        height=400,
                        bargap=0.1,
                        showlegend=False
                    )
                    st.plotly_chart(fig_tpa, use_container_width=True)
                    st.caption(f"Total: {per_acre['trees_per_acre']:.0f} trees/acre")
    
    # TAB 4: Files
    with result_tab4:
        st.markdown("### Download Files")
        
        run_id = summary['run_id']
        output_dir = summary['configuration']['output']['directory']
        run_dir = os.path.join(output_dir, f"run_{run_id}")
        
        if os.path.exists(run_dir):
            for filename in sorted(os.listdir(run_dir)):
                filepath = os.path.join(run_dir, filename)
                file_size = os.path.getsize(filepath) / 1024
                
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"📁 **{filename}** ({file_size:.1f} KB)")
                with col2:
                    with open(filepath, 'rb') as f:
                        st.download_button(
                            "Download",
                            f,
                            file_name=filename,
                            key=filename
                        )

def create_comparison_chart(df, metric='final_mean_dbh', group_by='secondary_strategy'):
    """Create comparison bar chart"""
    
    fig = px.bar(
        df, x=group_by, y=metric,
        color='primary_strategy',
        barmode='group',
        title=f"{metric.replace('_', ' ').title()} by Strategy"
    )
    fig.update_layout(height=500)
    return fig

def create_scatter_plot(df):
    """Create DBH vs Height scatter"""
    
    fig = px.scatter(
        df,
        x='final_mean_dbh',
        y='final_mean_height',
        color='primary_strategy',
        symbol='secondary_strategy',
        hover_data=['run_id', 'ba_removal_pct'],
        title="Final DBH vs Height"
    )
    fig.update_layout(height=500)
    return fig
