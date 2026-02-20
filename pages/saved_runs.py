"""
Saved Runs Page
"""

import streamlit as st
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.db_manager import get_all_runs, get_summary_stats, delete_run

def show():
    st.header("📁 Saved Runs")
    
    stats = get_summary_stats()
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Runs", stats['total_runs'])
    with col2:
        st.metric("Unique Stands", stats['unique_stands'])
    with col3:
        if stats['avg_final_dbh']:
            st.metric("Avg DBH", f"{stats['avg_final_dbh']:.2f}\"")
    
    df = get_all_runs()
    
    if len(df) == 0:
        st.info("No runs yet")
        return
    
    st.dataframe(df, use_container_width=True, height=500)
    
    # Delete
    st.markdown("### Manage")
    run_ids = df['run_id'].tolist()
    selected = st.selectbox("Select run to delete:", run_ids)
    
    if st.button("🗑️ Delete", type="secondary"):
        delete_run(selected)
        st.success("Deleted!")
        st.rerun()

if __name__ == "__main__":
    show()
