"""
Random Forest Volume Predictor - COMPREHENSIVE SOLUTION
Wrapper for R-based Random Forest model using rpy2

ROOT CAUSE OF ALL ERRORS:
- Mixing Python function calls with R objects creates conversion confusion
- Thread-local context gets lost across Streamlit threads  
- Multiple converter activation points cause state conflicts

SOLUTION:
- Execute EVERYTHING in R directly (no Python→R→Python bouncing)
- Use minimal conversions (only input DataFrame and output result)
- Single atomic operation within one context
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
    
    Args:
        df: Input DataFrame
        
    Returns:
        DataFrame with proper column names for R model
    """
    df_prepared = df.copy()
    
    # Column name mapping (CSV → R model)
    column_mapping = {
        'HTLC_x': 'HTLC.x',  # R uses dot, CSV uses underscore
    }
    
    # Rename columns
    df_prepared = df_prepared.rename(columns=column_mapping)
    
    # Add optional features with default values if missing
    # These are used by some RF models but may not be in all datasets
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
    
    Args:
        df: Input DataFrame
        
    Returns:
        tuple: (is_valid, message, cleaned_df)
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
    Run Random Forest prediction using R model via rpy2
    
    COMPREHENSIVE SOLUTION:
    Strategy: Execute everything in R, minimize Python↔R conversions
    
    Instead of:
        Python DataFrame → R DataFrame → R function(R_df, R_model) → R result → Python DataFrame
        (Multiple conversion points = multiple failure points)
    
    We do:
        Python DataFrame → [SINGLE R CONTEXT] → Python DataFrame
        All R operations happen in R, we just pass data in and get results out
    
    Args:
        df: Input DataFrame with required features
        model_path: Path to .rds model file
        r_script_path: Path to R script with prediction functions
        verbose: Print progress messages
        
    Returns:
        DataFrame with predictions added
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
    if not os.path.exists(r_script_path):
        raise FileNotFoundError(f"R script file not found: {r_script_path}")
    
    # Normalize paths for R
    model_path_abs = os.path.abspath(model_path).replace(os.sep, "/")
    r_script_path_abs = os.path.abspath(r_script_path).replace(os.sep, "/")
    
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
        
        # STEP 1: Load R script and model (pure R operations, no conversion)
        ro.r(f'source("{r_script_path_abs}")')
        ro.r(f'rf_model <- readRDS("{model_path_abs}")')
        
        if verbose:
            print(f"✓ R script loaded: {os.path.basename(r_script_path_abs)}")
            print(f"✓ RF model loaded: {os.path.basename(model_path_abs)}")
            print("\nRunning prediction pipeline...")
        
        # STEP 2: Create combined converter
        # default_converter: handles basic Python types (int, float, str, list, dict)
        # pandas2ri.converter: handles pandas DataFrame ↔ R data.frame
        # numpy2ri.converter: handles numpy arrays ↔ R vectors
        converter = ro.default_converter + pandas2ri.converter + numpy2ri.converter
        

        # STEP 3: Single atomic operation within one context
        with converter.context():
            # Convert Python DataFrame to R
            ro.globalenv['input_data'] = df_copy
            
            # Execute prediction entirely in R
            ro.r('result_df <- apply_rf_model(input_data, rf_model)')
            
            # THE FIX: Surgical Extraction
            # Instead of dragging the whole complex DataFrame back across the bridge,
            # we just extract the single column of numeric predictions.
            ro.r('predicted_vols <- result_df$Predicted_volume_m')
            
            # Convert the simple numeric vector back to a Python numpy array
            vols_array = np.array(ro.r['predicted_vols'])
            
        # Context exits - automatic cleanup, thread-local state cleared
        
        # Attach the predictions safely to our pristine Python dataframe
        predictions_df = df_copy.copy()
        predictions_df['Predicted_volume_m'] = vols_array
        
        if verbose:
            print(f"\n✅ Predictions complete")
            if 'Predicted_volume_m' in predictions_df.columns:
                total_vol = predictions_df['Predicted_volume_m'].sum()
                mean_vol = predictions_df['Predicted_volume_m'].mean()
                print(f"   Total Predicted Volume: {total_vol:.2f} m³")
                print(f"   Mean Volume per Tree: {mean_vol:.4f} m³")
        
        return predictions_df
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        
        # Enhanced error diagnostics
        if "NotImplementedError" in str(e) and "Conversion" in str(e):
            raise RuntimeError(
                f"❌ rpy2 Conversion Error\n\n"
                f"Error: {str(e)}\n\n"
                f"Diagnosis: A Python data type couldn't be converted to R.\n"
                f"Common causes:\n"
                f"  - Non-numeric values in numeric columns\n"
                f"  - Mixed data types in columns\n"
                f"  - Missing required features\n\n"
                f"Full traceback:\n{error_details}"
            )
        elif "Error in apply_rf_model" in str(e):
            raise RuntimeError(
                f"❌ R Function Error\n\n"
                f"Error: {str(e)}\n\n"
                f"Diagnosis: The R prediction function failed.\n"
                f"Check:\n"
                f"  - R script defines 'apply_rf_model(data, model)'\n"
                f"  - Model file is valid randomForest object\n"
                f"  - Input data has all required features\n\n"
                f"Full traceback:\n{error_details}"
            )
        elif "object 'rf_model' not found" in str(e):
            raise RuntimeError(
                f"❌ R Model Loading Error\n\n"
                f"Error: {str(e)}\n\n"
                f"Diagnosis: Model file couldn't be loaded.\n"
                f"Check:\n"
                f"  - File exists: {model_path}\n"
                f"  - File is valid .rds format\n"
                f"  - File contains randomForest model object\n\n"
                f"Full traceback:\n{error_details}"
            )
        else:
            raise RuntimeError(
                f"❌ RF Prediction Failed\n\n"
                f"Error: {str(e)}\n\n"
                f"Full traceback:\n{error_details}"
            )


def get_rf_summary_stats(predictions_df):
    """Calculate summary statistics from RF predictions"""
    if 'Predicted_volume_m' not in predictions_df.columns:
        raise ValueError("predictions_df must have 'Predicted_volume_m' column")
    
    volumes = predictions_df['Predicted_volume_m']
    
    return {
        'n_trees': len(predictions_df),
        'total_volume_m3': float(volumes.sum()),
        'mean_volume_m3': float(volumes.mean()),
        'median_volume_m3': float(volumes.median()),
        'std_volume_m3': float(volumes.std()),
        'min_volume_m3': float(volumes.min()),
        'max_volume_m3': float(volumes.max()),
        'prediction_timeframe': '4 years from data collection'
    }


def export_rf_results(predictions_df, output_path, include_input_features=False):
    """Export RF predictions to CSV"""
    if include_input_features:
        predictions_df.to_csv(output_path, index=False)
    else:
        essential_cols = ['treeID', 'Predicted_volume_m']
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
    print("4. No deprecated activate/deactivate methods")