"""
Pipeline Runner - Wraps bug-fixed complete_pipeline.py for Streamlit
"""

import sys
import os
import yaml
import tempfile
from datetime import datetime

# Import the bug-fixed pipeline from current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from complete_pipeline import run_complete_workflow

def run_pipeline(config_dict, progress_callback=None):
    """
    Run the complete pipeline with a config dictionary
    
    Args:
        config_dict: Configuration dictionary
        progress_callback: Optional function(progress_pct, message) for progress updates
    
    Returns:
        dict: Summary results from pipeline
    """
    
    # Create temporary config file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config_dict, f)
        temp_config_path = f.name
    
    try:
        # Update progress
        if progress_callback:
            progress_callback(10, "Starting pipeline...")
        
        # Run the pipeline
        summary = run_complete_workflow(temp_config_path)
        
        # Update progress
        if progress_callback:
            progress_callback(90, "Processing results...")
        
        # Clean up temp file
        os.unlink(temp_config_path)
        
        if progress_callback:
            progress_callback(100, "Complete!")
        
        return summary
        
    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(temp_config_path):
            os.unlink(temp_config_path)
        raise e

def run_batch_pipeline(stand_file, primary_strategies, secondary_strategies, 
                       stand_params, growth_params, output_dir, progress_callback=None):
    """
    Run multiple strategy combinations in batch
    
    Args:
        stand_file: Path to stand CSV
        primary_strategies: List of primary strategy names
        secondary_strategies: List of secondary strategy names
        stand_params: Dict with age parameters
        growth_params: Dict with growth model parameters
        output_dir: Where to save results
        progress_callback: Optional function(progress_pct, message, run_info)
    
    Returns:
        list: List of summary results
    """
    
    results = []
    total_combos = len(primary_strategies) * len(secondary_strategies)
    current = 0
    
    for primary in primary_strategies:
        for secondary in secondary_strategies:
            current += 1
            
            # Build config
            config = {
                'input': {
                    'stand_file': stand_file,
                    'columns': {
                        'row': 'NL',
                        'x_coord': 'X1',
                        'y_coord': 'Y1',
                        'dbh': 'pDBH_RF',
                        'height': 'Z_ft',
                        'volume': 'pStV_RF'
                    }
                },
                'primary_thinning': {
                    'strategy': primary,
                    'start_row': 1
                },
                'secondary_thinning': {
                    'enabled': secondary != 'None',
                    'strategy': secondary if secondary != 'None' else 'Thin from Below',
                    'removal_fraction': 0.33,
                    'anchor_fraction': 0.10
                },
                'stand_parameters': stand_params,
                'growth_model': growth_params,
                'output': {
                    'directory': output_dir,
                    'save_intermediate': True,
                    'create_maps': True,
                    'verbose': False
                }
            }
            
            # Update progress
            if progress_callback:
                progress_pct = int((current / total_combos) * 100)
                message = f"Running {current}/{total_combos}: {primary} + {secondary}"
                progress_callback(progress_pct, message, {
                    'current': current,
                    'total': total_combos,
                    'primary': primary,
                    'secondary': secondary
                })
            
            try:
                # Run pipeline
                summary = run_pipeline(config)
                results.append(summary)
            except Exception as e:
                print(f"Error in {primary} + {secondary}: {str(e)}")
                continue
    
    return results
