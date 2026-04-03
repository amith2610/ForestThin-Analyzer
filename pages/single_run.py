"""
Single Run Page - Main Analysis Interface
v2.0: Added stand area input for per-acre metrics
"""

import streamlit as st
import pandas as pd
import os
import sys

# Add paths
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

from utils.pipeline_runner import run_pipeline
from utils.db_manager import save_run_to_db
from utils.visualizer import display_results

# Import RF predictor components (only used when RF model selected)
try:
    from rf_predictor import RF_REQUIRED_FEATURES
except ImportError:
    RF_REQUIRED_FEATURES = []  # Fallback if rf_predictor not available

def validate_csv(df):
    """Validate CSV has required columns"""
    required = ['NL', 'X1', 'Y1', 'pDBH_RF', 'Z', 'treeID']
    missing = [col for col in required if col not in df.columns]
    
    if missing:
        return False, f"Missing required columns: {', '.join(missing)}"
    
    # Check for Z_ft column or create it from Z
    if 'Z_ft' not in df.columns:
        df['Z_ft'] = df['Z']
    
    # Check for volume column or create placeholder
    if 'pStV_RF' not in df.columns:
        df['pStV_RF'] = 0.0  # Will be calculated by pipeline
    
    alive = len(df[(df['Z_ft'].notna()) & (df['Z_ft'] > 0)])
    if alive == 0:
        return False, "No alive trees found"
    
    return True, f"✅ {alive:,} alive trees detected"

def show():
    st.header("🏠 Single Run Analysis")
    
    tab1, tab2, tab3 = st.tabs(["📁 Upload", "⚙️ Configure", "🚀 Run"])
    
    # TAB 1: Upload
    with tab1:
        st.subheader("Upload Stand Data")
        
        # Dataset Requirements
        with st.expander("📋 Dataset Requirements", expanded=False):
            st.markdown("""
            **File Format:** CSV file
            
            **Required Columns (specific column names):**
            - `X1` - X coordinate (UTM meters)
            - `Y1` - Y coordinate (UTM meters)
            - `pDBH_RF` - Diameter at breast height (inches)
            - `Z` - Tree height (feet)
            - `NL` - Row identifier
            - `treeID` - Unique tree identifier
            
            **Data Requirements:**
            - One row per tree
            - All measurements must be numeric
            - Trees with missing DBH or height values will be excluded
            - Coordinates should use consistent projection
            """)
        
        uploaded_file = st.file_uploader("CSV file", type=['csv'], key="csv_uploader_main")
        
        if uploaded_file:
            upload_path = f"data/uploads/{uploaded_file.name}"
            os.makedirs(os.path.dirname(upload_path), exist_ok=True)
            
            with open(upload_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            df = pd.read_csv(upload_path)
            valid, msg = validate_csv(df)
            
            if valid:
                st.success(msg)
                st.dataframe(df.head(10), use_container_width=True)
                st.session_state['uploaded_file'] = upload_path
                st.session_state['stand_name'] = uploaded_file.name.replace('.csv', '')
            else:
                st.error(msg)
    
    # TAB 2: Configure
    with tab2:
        if 'uploaded_file' not in st.session_state:
            st.warning("⚠️ Upload a file first")
        else:
            st.subheader("Primary Thinning")
            
            # Strategy mapping: display name -> pipeline key
            primary_map = {
                "3-row thinning (remove every 3rd row)": "3-row",
                "4-row thinning (remove every 4th row)": "4-row",
                "5-row thinning (remove every 5th row)": "5-row",
                "variable-3_row_eqv": "variable-3_row_eqv",
                "variable-4_row_eqv": "variable-4_row_eqv",
                "variable-5_row_eqv": "variable-5_row_eqv"
            }
            
            primary_display = st.selectbox(
                "Strategy", 
                list(primary_map.keys()),
                key="primary_strategy_select"
            )
            primary_strategy = primary_map[primary_display]
            
            if primary_strategy in ["3-row", "4-row", "5-row"]:
                start_row = st.number_input("Start Row", 1, 5, 1, key="start_row_input")
            else:
                start_row = 1
            
            st.markdown("---")
            st.subheader("Thinning Mode")
            
            # No-thin checkbox
            no_thinning = st.checkbox("☑ Skip Thinning (No-Thin Mode)", key="no_thin_check",
                                      help="Growth projection without any thinning operations")
            
            if not no_thinning:
                # Regular thinning workflow
                st.markdown("---")
                st.subheader("Secondary Thinning")
                
                enable_secondary = st.checkbox("Enable Secondary Thinning", key="enable_secondary_check")
                
                if enable_secondary:
                    secondary_strategy = st.selectbox(
                        "Secondary Strategy",
                        [
                            "Thin from Below",
                            "Thin from Above-1 (Neighbors)",
                            "Thin from Above-2 (Anchor)",
                            "Thin by CI_Z (Height Competition)",
                            "Thin by CI1 (Distance-Dependent Competition)"
                        ],
                        key="secondary_strategy_select"
                    )
                    
                    removal_pct = st.slider("Removal %", 10, 60, 20, key="removal_slider")
                    
                    if 'Above' in secondary_strategy:
                        anchor_pct = st.slider("Anchor %", 5, 25, 10, key="anchor_slider")
                    else:
                        anchor_pct = 10
                else:
                    secondary_strategy = None
                    removal_pct = 0
                    anchor_pct = 10
            else:
                # No-thin mode: disable secondary thinning
                enable_secondary = False
                secondary_strategy = None
                removal_pct = 0
                anchor_pct = 10
            
            st.markdown("---")
            st.subheader("Growth Model")
            
            # Growth model selection
            if no_thinning:
                st.info("ℹ️ No-Thin Mode: Select growth prediction model")
                growth_model = st.radio(
                    "Model",
                    ["PTAEDA4", "Random Forest"],
                    key="growth_model_select",
                    help="PTAEDA4: Year-by-year simulation | Random Forest: 4-year volume prediction"
                )
                
                if growth_model == "Random Forest":
                    st.warning("⚠️ RF Model predicts volume 4 years from data collection date")
                    st.caption("Dataset must include ITC metrics and competition indices from LiDAR processing")
            else:
                growth_model = "PTAEDA4"
                st.caption("Using PTAEDA4 growth model (default for thinning scenarios)")
            
            st.markdown("---")
            st.subheader("Stand Parameters")
            
            # Only show age inputs for PTAEDA4
            if growth_model == "PTAEDA4":
                col1, col2, col3 = st.columns(3)
                with col1:
                    current_age = st.number_input("Current Age", 6, 50, 16, key="current_age_input")
                with col2:
                    thin_age = st.number_input("Thin Age", 6, 50, 16, key="thin_age_input")
                with col3:
                    proj_age = st.number_input("Project To", current_age+1, 60, 20, key="proj_age_input")
                
                baf = st.number_input("BAF", 5, 40, 10, key="baf_input")
            else:
                # RF model doesn't need age inputs
                st.caption("Random Forest model does not require age parameters")
                current_age = 0  # Placeholder
                thin_age = 0
                proj_age = 0
                baf = 10
            
            st.markdown("---")
            st.subheader("Stand Area (Optional)")
            st.caption("Enter stand area to calculate per-acre metrics (TPA, Volume/acre, etc.)")
            
            use_area = st.checkbox("Enter Stand Area", key="use_area_check")
            if use_area:
                stand_area = st.number_input("Area (acres)", 0.1, 1000.0, 1.0, 0.1, key="area_input")
            else:
                stand_area = None
            
            # Save config
            st.session_state['config'] = {
                'no_thinning': no_thinning,
                'growth_model': growth_model,
                'primary': primary_strategy,
                'start_row': start_row,
                'secondary_enabled': enable_secondary,
                'secondary': secondary_strategy,
                'removal_pct': removal_pct,
                'anchor_pct': anchor_pct,
                'current_age': current_age,
                'thin_age': thin_age,
                'proj_age': proj_age,
                'baf': baf,
                'stand_area': stand_area
            }
            
            st.success("✅ Configuration saved")
    
    # TAB 3: Run
    with tab3:
        if 'config' not in st.session_state:
            st.warning("⚠️ Configure settings first")
        else:
            config = st.session_state['config']
            
            st.subheader("Run Configuration")
            st.write(f"**File:** {st.session_state.get('stand_name', 'N/A')}")
            st.write(f"**Mode:** {'No-Thin' if config['no_thinning'] else 'Thinning'}")
            st.write(f"**Growth Model:** {config['growth_model']}")
            
            if not config['no_thinning']:
                st.write(f"**Primary:** {config['primary']}")
                if config['secondary_enabled']:
                    st.write(f"**Secondary:** {config['secondary']} ({config['removal_pct']}%)")
            
            if config['growth_model'] == 'PTAEDA4':
                st.write(f"**Ages:** {config['current_age']} → {config['proj_age']}")
            else:
                st.write(f"**Prediction:** 4-year volume forecast")
            
            if config['stand_area']:
                st.write(f"**Area:** {config['stand_area']} acres")
            
            if config['growth_model'] == 'PTAEDA4':
                years = config['proj_age'] - config['current_age']
                est_min = (years * 0.3)
                st.info(f"⏱️ Estimated: ~{est_min} minutes")
            else:
                st.info(f"⏱️ Estimated: ~30 seconds (RF prediction)")
            
            if st.button("🚀 RUN ANALYSIS", type="primary", key="run_button"):
                
                # Check if RF model selected
                if config['growth_model'] == 'Random Forest':
                    # RF MODEL PATHWAY
                    from rf_predictor import validate_rf_dataset, run_rf_prediction, get_rf_summary_stats
                    
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    try:
                        status_text.info("🌲 Loading dataset...")
                        progress_bar.progress(10)
                        
                        df = pd.read_csv(st.session_state['uploaded_file'])
                        
                        # Validate RF requirements
                        status_text.info("🔍 Validating dataset for RF model...")
                        progress_bar.progress(20)
                        
                        is_valid, msg = validate_rf_dataset(df)
                        if not is_valid:
                            st.error(f"❌ Dataset validation failed: {msg}")
                            st.info("💡 RF model requires LiDAR-processed CSV with ITC metrics and competition indices")
                            
                            # Show debugging info
                            with st.expander("🔍 Debug: Column Data Types"):
                                debug_info = []
                                for col in RF_REQUIRED_FEATURES:
                                    if col in df.columns:
                                        dtype = df[col].dtype
                                        sample = df[col].iloc[0] if len(df) > 0 else 'N/A'
                                        debug_info.append(f"{col}: {dtype} (sample: {sample})")
                                st.code('\n'.join(debug_info))
                            
                            progress_bar.empty()
                            status_text.empty()
                        else:
                            st.success(msg)
                            
                            # Run RF prediction
                            status_text.info("🤖 Running Random Forest prediction...")
                            progress_bar.progress(40)
                            
                            model_path = "models/random_forest_model.rds"
                            r_script_path = "models/gny_model_application.R"
                            
                            predictions = run_rf_prediction(
                                df, 
                                model_path=model_path,
                                r_script_path=r_script_path,
                                verbose=True
                            )
                            
                            progress_bar.progress(80)
                            
                            # Get summary stats
                            status_text.info("📊 Calculating summary statistics...")
                            stats = get_rf_summary_stats(predictions)
                            
                            progress_bar.progress(100)
                            
                            # Store results
                            st.session_state['rf_results'] = {
                                'predictions': predictions,
                                'stats': stats,
                                'model_type': 'Random Forest'
                            }
                            
                            st.success("✅ RF Prediction complete!")
                            progress_bar.empty()
                            status_text.empty()
                            
                    except Exception as e:
                        st.error(f"❌ RF Error: {str(e)}")
                        import traceback
                        with st.expander("Show traceback"):
                            st.code(traceback.format_exc())
                        progress_bar.empty()
                        status_text.empty()
                
                else:
                    # PTAEDA4 PATHWAY (existing code)
                    # Build pipeline config
                    pipeline_config = {
                        'input': {
                            'stand_file': st.session_state['uploaded_file'],
                            'columns': {
                                'row': 'NL', 'x_coord': 'X1', 'y_coord': 'Y1',
                                'dbh': 'pDBH_RF', 'height': 'Z_ft', 'volume': 'pStV_RF'
                            }
                        },
                        'primary_thinning': {
                            'strategy': config['primary'],
                            'start_row': config['start_row']
                        },
                        'secondary_thinning': {
                            'enabled': config['secondary_enabled'],
                            'strategy': config.get('secondary', 'Thin from Below'),
                            'removal_fraction': config['removal_pct'] / 100,
                            'anchor_fraction': config['anchor_pct'] / 100
                        },
                        'stand_parameters': {
                            'current_age': config['current_age'],
                            'thinning_age': config['thin_age'],
                            'projection_age': config['proj_age'],
                            'stand_area_acres': config['stand_area']
                        },
                        'growth_model': {
                            'basal_area_factor': config['baf']
                        },
                        'output': {
                            'directory': 'data/runs',
                            'create_maps': True,
                            'save_intermediate': True
                        }
                    }
                    
                    # Progress tracking
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    def progress_callback(stage, pct):
                        # Handle both parameter orders
                        if isinstance(stage, (int, float)):
                            # Swapped parameters
                            stage, pct = pct, stage
                        
                        if isinstance(pct, (int, float)):
                            progress_bar.progress(int(pct))
                        status_text.info(f"🌲 {stage}")
                    
                    try:
                        results = run_pipeline(pipeline_config, progress_callback)
                        
                        # Save to database
                        save_run_to_db(results)
                        
                        # Store in session
                        st.session_state['current_results'] = results
                        
                        st.success("✅ Analysis complete!")
                        progress_bar.empty()
                        status_text.empty()
                        
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        import traceback
                        with st.expander("Show traceback"):
                            st.code(traceback.format_exc())
    
    # Display results
    if 'current_results' in st.session_state:
        st.markdown("---")
        st.header("📊 PTAEDA4 Results")
        display_results(st.session_state['current_results'])
    
    # Display RF results
    if 'rf_results' in st.session_state:
        st.markdown("---")
        st.header("📊 Random Forest Prediction Results")
        
        rf_data = st.session_state['rf_results']
        stats = rf_data['stats']
        
        # Summary metrics
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Volume", f"{stats['total_volume_m3']:.2f} m³")
        
        with col2:
            st.metric("Mean Volume/Tree", f"{stats['mean_volume_m3']:.4f} m³")
        
        with col3:
            st.metric("Number of Trees", f"{stats['n_trees']:,}")
        
        # Additional stats
        st.subheader("Statistical Summary")
        summary_df = pd.DataFrame({
            'Metric': ['Total Volume', 'Mean Volume', 'Median Volume', 'Std Dev', 'Min Volume', 'Max Volume'],
            'Value': [
                f"{stats['total_volume_m3']:.2f} m³",
                f"{stats['mean_volume_m3']:.4f} m³",
                f"{stats['median_volume_m3']:.4f} m³",
                f"{stats['std_volume_m3']:.4f} m³",
                f"{stats['min_volume_m3']:.4f} m³",
                f"{stats['max_volume_m3']:.4f} m³"
            ]
        })
        st.table(summary_df)
        
        st.info(f"ℹ️ Prediction timeframe: {stats['prediction_timeframe']}")
        
        # Optional: Show sample predictions
        with st.expander("View Tree-Level Predictions (Sample)"):
            predictions = rf_data['predictions']
            display_cols = ['treeID', 'Predicted_volume_m']
            
            # Add coords if available
            for coord_col in ['X1', 'Y1', 'geom_x', 'geom_y']:
                if coord_col in predictions.columns:
                    display_cols.append(coord_col)
            
            available_cols = [c for c in display_cols if c in predictions.columns]
            st.dataframe(predictions[available_cols].head(20), use_container_width=True)
        
        # Download button
        csv = rf_data['predictions'][['treeID', 'Predicted_volume_m']].to_csv(index=False)
        st.download_button(
            label="📥 Download Predictions CSV",
            data=csv,
            file_name="rf_volume_predictions.csv",
            mime="text/csv"
        )

if __name__ == "__main__":
    show()