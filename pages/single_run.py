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

def validate_csv(df):
    """Validate CSV has required columns"""
    required = ['NL', 'X1', 'Y1', 'pDBH_RF', 'Z_ft', 'pStV_RF']
    missing = [col for col in required if col not in df.columns]
    
    if missing:
        return False, f"Missing: {', '.join(missing)}"
    
    alive = len(df[(df['Z_ft'].notna()) & (df['Z_ft'] > 0)])
    if alive == 0:
        return False, "No alive trees"
    
    return True, f"✅ {alive:,} alive trees"

def show():
    st.header("🏠 Single Run Analysis")
    
    tab1, tab2, tab3 = st.tabs(["📁 Upload", "⚙️ Configure", "🚀 Run"])
    
    # TAB 1: Upload
    with tab1:
        st.subheader("Upload Stand Data")
        
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
            
            st.markdown("---")
            st.subheader("Stand Parameters")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                current_age = st.number_input("Current Age", 6, 50, 16, key="current_age_input")
            with col2:
                thin_age = st.number_input("Thin Age", 6, 50, 16, key="thin_age_input")
            with col3:
                proj_age = st.number_input("Project To", current_age+1, 60, 20, key="proj_age_input")
            
            baf = st.number_input("BAF", 5, 40, 10, key="baf_input")
            
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
            st.write(f"**Primary:** {config['primary']}")
            if config['secondary_enabled']:
                st.write(f"**Secondary:** {config['secondary']} ({config['removal_pct']}%)")
            st.write(f"**Ages:** {config['current_age']} → {config['proj_age']}")
            if config['stand_area']:
                st.write(f"**Area:** {config['stand_area']} acres")
            
            years = config['proj_age'] - config['current_age']
            est_min = (years * 0.3)
            st.info(f"⏱️ Estimated: ~{est_min} minutes")
            
            if st.button("🚀 RUN ANALYSIS", type="primary", key="run_button"):
                
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
        st.header("📊 Results")
        display_results(st.session_state['current_results'])

if __name__ == "__main__":
    show()
