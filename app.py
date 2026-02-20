"""
🌲 ForestThin Analyzer - Streamlit App
"""

import streamlit as st
import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Page configuration
st.set_page_config(
    page_title="ForestThin Analyzer",
    page_icon="🌲",
    layout="wide"
)

# Custom CSS
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2E7D32;
        text-align: center;
        margin-bottom: 1rem;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown('<div class="main-header">🌲 ForestThin Analyzer</div>', unsafe_allow_html=True)

st.markdown("""

Features:
- 🎯 Test all 6 primary + 5 secondary strategies
- 📊 PTAEDA4 growth projections
- 📏 Per-acre metrics (TPA, Volume/acre)
- 🔍 Compare results across runs
- 💾 Auto-save to database
""")

# Navigation
st.sidebar.title("📋 Navigation")
page = st.sidebar.radio(
    "Select Page:",
    ["🏠 Single Run", "📊 Compare Results", "📁 Saved Runs", "ℹ️ About"],
    key="main_nav"
)

# Initialize session state
if 'runs' not in st.session_state:
    st.session_state.runs = []
if 'current_run' not in st.session_state:
    st.session_state.current_run = None

# Import pages
sys.path.append(os.path.join(os.path.dirname(__file__), 'pages'))

if page == "🏠 Single Run":
    from pages import single_run
    single_run.show()
elif page == "📊 Compare Results":
    from pages import compare
    compare.show()
elif page == "📁 Saved Runs":
    from pages import saved_runs
    saved_runs.show()
else:
    from pages import about
    about.show()

# Footer
st.sidebar.markdown("---")
