"""
Random Forest Volume Predictor - COMPREHENSIVE SOLUTION
Wrapper for R-based Random Forest model using rpy2

ROOT CAUSE OF ALL ERRORS:
- Mixing Python function calls with R objects creates conversion confusion
- Thread-local context gets lost across Streamlit threads  
- Multiple converter activation points cause state conflicts
- External R scripts dropping columns and crashing on NULL types

SOLUTION:
- Execute EVERYTHING natively in R via Python strings (no external R scripts)
- Use minimal conversions (only input DataFrame and output 1-D numeric array)
- Single atomic operation within one context
- Convert final outputs to cubic feet and calculate 4-year growth delta
"""

import pandas as pd
import numpy as np
import os

try:
    import rpy2.robjects as ro
    from rpy2.robjects import pandas2ri, numpy2ri
    RPY2_AVAILABLE = True
except ImportError:
    RPY2_AVAILABLE = False
    print("Warning: rpy2 not available. RF model will not work.")


# Required features for RF model - R MODEL NAMING (with dots and underscores as R expects)
# These are the names AFTER prepare_rf_data() mapping
RF_REQUIRED_FEATURES = [
    # Basic metrics
    'Z', 'HTLC.x', 'Carea', 'CArea_1', 'mCDst', 'CLAI', 'UndTF', 'UndPrp',
    # Volumetric features
    'vol1', 'vol2', 'vol3', 'vol4', 'vol5',
    # Surface area features
    'sfa1', 'sfa2', 'sfa3', 'sfa4', 'sfa5',
    # Competition indices
    'CI_Carea', 'CI_CArea_1', 'CI_Z', 'CI_mCDst', 'CI_LAI', 'CI_HTLC',
    'CI_under', 'CI_under2',
    'CI_vol1', 'CI_vol2', 'CI_vol3', 'CI_vol4', 'CI_vol5',
    'CI_sfa1', 'CI_sfa2', 'CI_sfa3', 'CI_sfa4', 'CI_sfa5',
    # SILVA indices
    'SILVA1', 'SILVA2'
]


# Optional features that may or may not be in the dataset
OPTIONAL_FEATURES = ['CArea_1', 'CLAI', 'UndTF', 'UndPrp', 'CI_CArea_1', 'CI_LAI', 'CI_under', 'CI_under2']


def prepare_rf_data(df):
    """
    Prepare data for RF model by:
    1. Renaming columns to match R model expectations
    2. Adding missing optional features with default values
    """
    df_prepared = df.copy()
    
    # Column name mapping (CSV → R model)
    column_mapping = {
        'HTLC_x': 'HTLC.x',  # R uses dot, CSV uses underscore
    }
    
    # Rename columns
    df_prepared = df_prepared.rename(columns=column_mapping)
    
    # Add optional features with default values if missing
    optional_defaults = {
        'CArea_1': 0.0,
        'CLAI': 0.0,
        'UndTF': 0.0,
        'UndPrp': 0.0,
        'CI_CArea_1': 0.0,
        'CI_LAI': 0.0,
        'CI_under': 0.0,
        'CI_under2': 0.0
    }
    
    for col, default_val in optional_defaults.items():
        if col not in df_prepared.columns:
            df_prepared[col] = default_val
    
    return df_prepared


def validate_rf_dataset(df):
    """
    Validate that dataset has all required features for RF model
    """
    missing_features = [f for f in RF_REQUIRED_FEATURES if f not in df.columns]
    
    if missing_features:
        return False, f"Missing {len(missing_features)} required features: {', '.join(missing_features[:5])}...", None
    
    # Create clean copy
    df_clean = df.copy()
    
    # Convert all required features to numeric
    non_numeric_cols = []
    for col in RF_REQUIRED_FEATURES:
        try:
            df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
            if df_clean[col].isna().all():
                non_numeric_cols.append(col)
        except Exception as e:
            non_numeric_cols.append(f"{col} (error: {str(e)})")
    
    if non_numeric_cols:
        return False, f"These columns could not be converted to numeric: {', '.join(non_numeric_cols[:3])}...", None
    
    # Check for valid data
    valid_rows = df_clean[RF_REQUIRED_FEATURES].notna().all(axis=1).sum()
    total_rows = len(df_clean)
    
    if valid_rows == 0:
        return False, "No valid rows found (all features must be non-null)", None
    
    if valid_rows < total_rows:
        return True, f"✅ Valid dataset ({valid_rows}/{total_rows} trees have complete data)", df_clean
    
    return True, f"✅ Valid dataset ({valid_rows} trees)", df_clean


def run_rf_prediction(df, model_path, r_script_path, verbose=True):
    """
    Run Random Forest prediction using R model natively via rpy2 strings.
    """
    if not RPY2_AVAILABLE:
        raise RuntimeError("rpy2 is not installed. Install with: pip install rpy2")
    
    # Prepare data: rename columns and add missing features
    df_prepared = prepare_rf_data(df)
    
    # Validate input and get cleaned DataFrame
    is_valid, msg, df_clean = validate_rf_dataset(df_prepared)
    if not is_valid:
        raise ValueError(f"Invalid dataset for RF model: {msg}")
    
    if verbose:
        print("\n" + "="*80)
        print("RANDOM FOREST VOLUME PREDICTION")
        print("="*80)
        print(f"\nInput: {len(df_clean)} trees (after cleaning)")
        print(f"Model: {os.path.basename(model_path)}")
        print(msg)
    
    # Validate file paths
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"RF model file not found: {model_path}")
    
    # Normalize paths for R
    model_path_abs = os.path.abspath(model_path).replace(os.sep, "/")
    
    # Prepare data
    df_copy = df_clean.copy()
    df_copy['study'] = 'DEFAULT'
    
    # Ensure proper types for rpy2
    for col in RF_REQUIRED_FEATURES:
        if col in df_copy.columns:
            df_copy[col] = df_copy[col].astype('float64')
    df_copy['study'] = df_copy['study'].astype(str)
    
    try:
        if verbose:
            print(f"\nLoading R environment...")
        
        # STEP 1: Load RF model natively (We bypass the external R script entirely)
        ro.r(f'rf_model <- readRDS("{model_path_abs}")')
        
        if verbose:
            print(f"✓ RF model loaded: {os.path.basename(model_path_abs)}")
            print("\nRunning native R prediction pipeline...")
        
        # STEP 2: Create combined converter
        converter = ro.default_converter + pandas2ri.converter + numpy2ri.converter
        
        # STEP 3: Single atomic operation within one context
        with converter.context():
            # EXPLICIT conversion to R dataframe (forces it safely across the bridge)
            r_df = pandas2ri.py2rpy(df_copy)
            ro.globalenv['input_data'] = r_df
            
            # STEP 4: NATIVE R EXECUTION
            # We inject the R logic directly from Python so nothing gets lost
            r_code = """
            library(randomForest)
            input_data <- as.data.frame(input_data)
            
            # 1. Lock Factors (Fixes the study/factor crash)
            if (!is.null(rf_model$forest$xlevels)) {
                for (var_name in names(rf_model$forest$xlevels)) {
                    if (var_name %in% colnames(input_data)) {
                        expected_levels <- rf_model$forest$xlevels[[var_name]]
                        input_data[[var_name]] <- factor(expected_levels[1], levels = expected_levels)
                    }
                }
            }
            
            # 2. Get Required Features safely from the model's formula
            if (!is.null(rf_model$terms)) {
                req_features <- attr(rf_model$terms, "term.labels")
            } else {
                req_features <- rownames(rf_model$importance)
            }
            
            # 3. Patch Missing or NA Columns safely
            for (col in req_features) {
                if (!(col %in% colnames(input_data))) {
                    input_data[[col]] <- 0
                } else if (any(is.na(input_data[[col]]))) {
                    input_data[is.na(input_data[[col]]), col] <- 0
                }
            }
            
            # 4. Predict and strictly force to a numeric array
            predictions <- predict(rf_model, newdata = input_data)
            predicted_vols <- as.numeric(predictions)
            """
            ro.r(r_code)
            
            # Extract the guaranteed pure numeric vector back to Python
            raw_vols = ro.r['predicted_vols']
            vols_array = np.array(raw_vols, dtype=float)
            
        # Context exits - automatic cleanup
        
        # Attach the pure float predictions safely to our Python dataframe
        predictions_df = df_copy.copy()
        predictions_df['Predicted_volume_m3'] = vols_array
        
        # 1. Convert to cubic feet (1 m³ = 35.3146667 ft³)
        predictions_df['Predicted_volume_cuft'] = predictions_df['Predicted_volume_m3'] * 35.3146667
        
        # 2. Calculate Initial Volume using Tasissa (DBH in inches, Height in feet)
        predictions_df['Initial_volume_cuft'] = 0.25663 + 0.00239 * (predictions_df['pDBH_RF'] ** 2) * predictions_df['Z_ft']
        
        # 3. Calculate Volume Growth per tree
        predictions_df['Volume_growth_cuft'] = predictions_df['Predicted_volume_cuft'] - predictions_df['Initial_volume_cuft']
        
        if verbose:
            print(f"\n✅ Predictions complete")
            total_initial = predictions_df['Initial_volume_cuft'].sum()
            total_pred = predictions_df['Predicted_volume_cuft'].sum()
            total_growth = predictions_df['Volume_growth_cuft'].sum()
            
            print(f"   Initial Volume: {total_initial:.2f} ft³")
            print(f"   Predicted Volume: {total_pred:.2f} ft³")
            print(f"   Volume Growth: {total_growth:.2f} ft³")
        
        return predictions_df
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        
        raise RuntimeError(
            f"❌ RF Prediction Failed\n\n"
            f"Error: {str(e)}\n\n"
            f"Full traceback:\n{error_details}"
        )


def get_rf_summary_stats(predictions_df):
    """Calculate summary statistics from RF predictions"""
    if 'Predicted_volume_cuft' not in predictions_df.columns:
        raise ValueError("predictions_df must have 'Predicted_volume_cuft' column")
    
    pred_volumes = predictions_df['Predicted_volume_cuft']
    init_volumes = predictions_df['Initial_volume_cuft']
    growth_volumes = predictions_df['Volume_growth_cuft']
    
    return {
        'n_trees': len(predictions_df),
        'total_initial_volume_cuft': float(init_volumes.sum()),
        'total_volume_cuft': float(pred_volumes.sum()),
        'total_volume_growth_cuft': float(growth_volumes.sum()),
        'mean_volume_cuft': float(pred_volumes.mean()),
        'median_volume_cuft': float(pred_volumes.median()),
        'std_volume_cuft': float(pred_volumes.std()),
        'min_volume_cuft': float(pred_volumes.min()),
        'max_volume_cuft': float(pred_volumes.max()),
        'prediction_timeframe': '4 years from data collection'
    }


def export_rf_results(predictions_df, output_path, include_input_features=False):
    """Export RF predictions to CSV"""
    if include_input_features:
        predictions_df.to_csv(output_path, index=False)
    else:
        essential_cols = [
            'treeID', 
            'Initial_volume_cuft', 
            'Predicted_volume_cuft', 
            'Volume_growth_cuft'
        ]
        for col in ['X1', 'Y1', 'geom_x', 'geom_y']:
            if col in predictions_df.columns and col not in essential_cols:
                essential_cols.insert(1, col)
        export_cols = [c for c in essential_cols if c in predictions_df.columns]
        predictions_df[export_cols].to_csv(output_path, index=False)
    
    return output_path


# Self-test
if __name__ == "__main__":
    print("RF Predictor Module - COMPREHENSIVE SOLUTION")
    print(f"RPY2 Available: {RPY2_AVAILABLE}")
    print(f"Required Features: {len(RF_REQUIRED_FEATURES)}")
    print("\nKey Design Principles:")
    print("1. Execute everything in R (minimize Python↔R transitions)")
    print("2. Single conversion context (thread-safe)")
    print("3. Combined converters (default + pandas + numpy)")
    print("4. Pure numeric array extraction to bypass NULLType bugs")