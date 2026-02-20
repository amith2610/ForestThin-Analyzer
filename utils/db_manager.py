"""
Database Manager - SQLite operations for storing and querying runs
"""

import sqlite3
import pandas as pd
import json
from datetime import datetime
import os

DB_PATH = "data/results.db"

def init_database():
    """Initialize the database schema"""
    
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            timestamp DATETIME,
            stand_name TEXT,
            stand_file TEXT,
            primary_strategy TEXT,
            secondary_strategy TEXT,
            current_age INTEGER,
            projection_age INTEGER,
            projection_years INTEGER,
            
            -- Thinning results
            trees_before INTEGER,
            trees_after INTEGER,
            trees_removed INTEGER,
            pct_trees_removed REAL,
            ba_before_sqft REAL,
            ba_after_sqft REAL,
            ba_removed_sqft REAL,
            ba_removal_pct REAL,
            thinning_intensity REAL,
            mean_dbh_before REAL,
            mean_dbh_after REAL,
            qmd_before REAL,
            qmd_after REAL,
            
            -- Growth results (FIXED: renamed to match pipeline)
            final_mean_dbh REAL,
            final_mean_height REAL,
            final_dbh_sum REAL,
            final_height_sum REAL,
            mean_dbh_growth REAL,
            mean_height_growth REAL,
            survival_rate REAL,
            
            -- Volume results
            total_volume_final REAL,
            volume_after_thinning REAL,
            growth_in_volume REAL,
            
            -- File paths
            summary_json_path TEXT,
            growth_csv_path TEXT,
            thinning_map_path TEXT,
            
            -- Metadata
            runtime_seconds REAL,
            notes TEXT
        )
    """)
    
    conn.commit()
    conn.close()

def save_run_to_db(summary):
    """Save a run summary to the database"""
    
    init_database()
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Extract data from summary
    thin = summary['thinning_results']
    growth = summary['growth_projection']
    config = summary['configuration']
    
    # Determine stand name
    stand_file = config['input']['stand_file']
    stand_name = os.path.basename(stand_file).replace('.csv', '')
    
    # Get volume data if available
    total_volume = growth.get('total_volume_final', 0)
    volume_after = growth.get('volume_after_thinning', 0)
    volume_growth = growth.get('growth_in_volume', 0)
    
    # Insert data
    c.execute("""
        INSERT OR REPLACE INTO runs VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?,
            ?, ?
        )
    """, (
        summary['run_id'],
        datetime.now(),
        stand_name,
        stand_file,
        thin['primary_strategy'],
        thin['secondary_strategy'],
        growth['start_age'],
        growth['final_age'],
        growth['projection_years'],
        
        thin['trees_before'],
        thin['trees_after'],
        thin['trees_removed'],
        thin['pct_trees_removed'],
        thin['ba_before_sqft'],
        thin['ba_after_sqft'],
        thin['ba_removed_sqft'],
        thin['ba_removal_pct'],
        thin['thinning_intensity'],
        thin['mean_dbh_before'],
        thin['mean_dbh_after'],
        thin['qmd_before'],
        thin['qmd_after'],
        
        growth['final_mean_dbh'],  # FIXED: was 'mean_dbh_final'
        growth['final_mean_height'],  # FIXED: was 'mean_height_final'
        growth.get('final_dbh_sum', 0),  # FIXED: was 'sum_final_dbh'
        growth.get('final_height_sum', 0),  # FIXED: was 'sum_final_height'
        growth['mean_dbh_growth'],
        growth['mean_height_growth'],
        growth['final_survival_rate'],
        
        total_volume,
        volume_after,
        volume_growth,
        
        summary['output_files'].get('summary', ''),
        summary['output_files'].get('growth_projections', ''),
        summary['output_files'].get('primary_map', ''),
        
        0,  # runtime_seconds
        ''  # notes
    ))
    
    conn.commit()
    conn.close()

def get_all_runs():
    """Get all runs from database as DataFrame"""
    
    init_database()
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM runs ORDER BY timestamp DESC", conn)
    conn.close()
    
    return df

def get_runs_by_stand(stand_name):
    """Get all runs for a specific stand"""
    
    init_database()
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM runs WHERE stand_name = ? ORDER BY final_mean_dbh DESC",
        conn,
        params=(stand_name,)
    )
    conn.close()
    
    return df

def get_run_by_id(run_id):
    """Get a specific run by ID"""
    
    init_database()
    
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(
        "SELECT * FROM runs WHERE run_id = ?",
        conn,
        params=(run_id,)
    )
    conn.close()
    
    return df.iloc[0] if len(df) > 0 else None

def delete_run(run_id):
    """Delete a run from database"""
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM runs WHERE run_id = ?", (run_id,))
    conn.commit()
    conn.close()

def get_summary_stats():
    """Get summary statistics across all runs"""
    
    init_database()
    
    conn = sqlite3.connect(DB_PATH)
    
    stats = {
        'total_runs': pd.read_sql_query("SELECT COUNT(*) as count FROM runs", conn).iloc[0]['count'],
        'unique_stands': pd.read_sql_query("SELECT COUNT(DISTINCT stand_name) as count FROM runs", conn).iloc[0]['count'],
        'avg_final_dbh': pd.read_sql_query("SELECT AVG(final_mean_dbh) as avg FROM runs", conn).iloc[0]['avg'],
        'best_strategy': pd.read_sql_query("""
            SELECT primary_strategy, secondary_strategy, AVG(final_mean_dbh) as avg_dbh 
            FROM runs 
            GROUP BY primary_strategy, secondary_strategy 
            ORDER BY avg_dbh DESC 
            LIMIT 1
        """, conn).iloc[0] if pd.read_sql_query("SELECT COUNT(*) as count FROM runs", conn).iloc[0]['count'] > 0 else None
    }
    
    conn.close()
    
    return stats
