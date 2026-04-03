"""
Random Forest Volume Predictor
Wrapper for R-based Random Forest model using rpy2
"""

import pandas as pd
import numpy as np
import os

try:
    import rpy2.robjects as ro
    from rpy2.robjects import pandas2ri
    from rpy2.robjects.conversion import localconverter
    RPY2_AVAILABLE = True
except ImportError:
    RPY2_AVAILABLE = False
    print("Warning: rpy2 not available. RF model will not work.")


# Required features for RF model
RF_REQUIRED_FEATURES = [
    # Basic metrics (reduced from 8 to 4)
    'Z', 'HTLC_x', 'Carea', 'mCDst',  # Changed HTLC.x → HTLC_x
    # Volumetric features (all 5 present)
    'vol1', 'vol2', 'vol3', 'vol4', 'vol5',
    # Surface area features (all 5 present)
    'sfa1', 'sfa2', 'sfa3', 'sfa4', 'sfa5',
    # Competition indices (reduced from 20 to 14)
    'CI_Carea', 'CI_Z', 'CI_mCDst', 'CI_HTLC',
    'CI_vol1', 'CI_vol2', 'CI_vol3', 'CI_vol4', 'CI_vol5',
    'CI_sfa1', 'CI_sfa2', 'CI_sfa3', 'CI_sfa4', 'CI_sfa5',
    # SILVA indices (both present)
    'SILVA1', 'SILVA2'
]

def validate_rf_dataset(df):
    """
    Validate that dataset has all required features for RF model
    
    Args:
        df: Input DataFrame
        
    Returns:
        tuple: (is_valid, message)
    """
    missing_features = [f for f in RF_REQUIRED_FEATURES if f not in df.columns]
    
    if missing_features:
        return False, f"Missing {len(missing_features)} required features: {', '.join(missing_features[:5])}..."
    
    # Try to convert columns to numeric and check for issues
    non_numeric_cols = []
    for col in RF_REQUIRED_FEATURES:
        # Try converting to numeric
        try:
            # Convert column to numeric, coercing errors to NaN
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # Check if conversion resulted in all NaN (completely non-numeric)
            if df[col].isna().all():
                non_numeric_cols.append(col)
        except Exception as e:
            non_numeric_cols.append(f"{col} (error: {str(e)})")
    
    if non_numeric_cols:
        return False, f"These columns could not be converted to numeric: {', '.join(non_numeric_cols[:3])}..."
    
    # Check for valid data
    valid_rows = df[RF_REQUIRED_FEATURES].notna().all(axis=1).sum()
    total_rows = len(df)
    
    if valid_rows == 0:
        return False, "No valid rows found (all features must be non-null)"
    
    if valid_rows < total_rows:
        return True, f"✅ Valid dataset ({valid_rows}/{total_rows} trees have complete data)"
    
    return True, f"✅ Valid dataset ({valid_rows} trees)"


def run_rf_prediction(df, model_path, r_script_path, verbose=True):
    """
    Run Random Forest prediction using R model via rpy2
    
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
    
    # Validate input
    is_valid, msg = validate_rf_dataset(df)
    if not is_valid:
        raise ValueError(f"Invalid dataset for RF model: {msg}")
    
    if verbose:
        print("\n" + "="*80)
        print("RANDOM FOREST VOLUME PREDICTION")
        print("="*80)
        print(f"\nInput: {len(df)} trees")
        print(f"Model: {os.path.basename(model_path)}")
    
    # Validate file paths exist
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"RF model file not found: {model_path}")
    
    if not os.path.exists(r_script_path):
        raise FileNotFoundError(f"R script file not found: {r_script_path}")
    
    # Get absolute paths and normalize for R
    model_path_abs = os.path.abspath(model_path).replace(os.sep, "/")
    r_script_path_abs = os.path.abspath(r_script_path).replace(os.sep, "/")
    
    # Add required 'study' column (metadata, hardcoded)
    df_copy = df.copy()
    df_copy['study'] = 'DEFAULT'
    
    # Convert all numeric columns to float to avoid numpy dtype issues
    for col in df_copy.columns:
        if df_copy[col].dtype != 'object':
            df_copy[col] = df_copy[col].astype(float)
    
    try:
        # Activate necessary converters
        from rpy2.robjects import numpy2ri
        numpy2ri.activate()
        
        # Load R script
        if verbose:
            print(f"\nLoading R script: {r_script_path_abs}")
        ro.r(f'source("{r_script_path_abs}")')
        
        # Load RF model
        if verbose:
            print(f"Loading RF model: {model_path_abs}")
        ro.r(f'rf_model <- readRDS("{model_path_abs}")')
        
        # Convert pandas DataFrame to R DataFrame
        if verbose:
            print("\nConverting data to R format...")
        
        # Use simpler conversion approach
        with localconverter(ro.default_converter + pandas2ri.converter):
            r_df = pandas2ri.py2rpy(df_copy)
        
        if verbose:
            print("Running predictions...")
        
        # Run prediction function
        result = ro.r['apply_rf_model'](r_df, ro.r['rf_model'])
        
        # Convert back to pandas
        with localconverter(ro.default_converter + pandas2ri.converter):
            predictions_df = pandas2ri.rpy2py(result)
        
        # Deactivate converters
        numpy2ri.deactivate()
        
        if verbose:
            print(f"\n✅ Predictions complete")
            if 'Predicted_volume_m' in predictions_df.columns:
                total_vol = predictions_df['Predicted_volume_m'].sum()
                mean_vol = predictions_df['Predicted_volume_m'].mean()
                print(f"   Total Predicted Volume: {total_vol:.2f} m³")
                print(f"   Mean Volume per Tree: {mean_vol:.4f} m³")
        
        return predictions_df
        
    except Exception as e:
        # Deactivate converters on error
        try:
            numpy2ri.deactivate()
        except:
            pass
        raise RuntimeError(f"RF prediction failed: {str(e)}")


def get_rf_summary_stats(predictions_df):
    """
    Calculate summary statistics from RF predictions
    
    Args:
        predictions_df: DataFrame with Predicted_volume_m column
        
    Returns:
        dict: Summary statistics
    """
    if 'Predicted_volume_m' not in predictions_df.columns:
        raise ValueError("predictions_df must have 'Predicted_volume_m' column")
    
    volumes = predictions_df['Predicted_volume_m']
    
    stats = {
        'n_trees': len(predictions_df),
        'total_volume_m3': float(volumes.sum()),
        'mean_volume_m3': float(volumes.mean()),
        'median_volume_m3': float(volumes.median()),
        'std_volume_m3': float(volumes.std()),
        'min_volume_m3': float(volumes.min()),
        'max_volume_m3': float(volumes.max()),
        'prediction_timeframe': '4 years from data collection'
    }
    
    return stats


def export_rf_results(predictions_df, output_path, include_input_features=False):
    """
    Export RF predictions to CSV
    
    Args:
        predictions_df: DataFrame with predictions
        output_path: Path to save CSV
        include_input_features: Whether to include all input features
        
    Returns:
        str: Path to exported file
    """
    if include_input_features:
        # Export everything
        predictions_df.to_csv(output_path, index=False)
    else:
        # Export only essential columns
        essential_cols = ['treeID', 'Predicted_volume_m']
        
        # Add coordinate columns if available
        for col in ['X1', 'Y1', 'geom_x', 'geom_y']:
            if col in predictions_df.columns:
                essential_cols.insert(1, col)
        
        # Filter to available columns
        export_cols = [c for c in essential_cols if c in predictions_df.columns]
        predictions_df[export_cols].to_csv(output_path, index=False)
    
    return output_path


# Self-test function
if __name__ == "__main__":
    print("RF Predictor Module")
    print(f"RPY2 Available: {RPY2_AVAILABLE}")
    print(f"Required Features: {len(RF_REQUIRED_FEATURES)}")
    
    # Create dummy data for testing
    dummy_data = pd.DataFrame({
        col: np.random.randn(10) for col in RF_REQUIRED_FEATURES
    })
    dummy_data['treeID'] = range(1, 11)
    
    is_valid, msg = validate_rf_dataset(dummy_data)
    print(f"\nValidation Test: {msg}")