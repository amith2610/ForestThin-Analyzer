"""
About Page - User Guide with Strategy and Metric Descriptions
"""

import streamlit as st

def show():
    st.header("ℹ️ About ForestThin Analyzer")
    
    st.markdown("""
    Professional forestry analysis tool for loblolly pine thinning strategies
    
    This application helps forest managers evaluate different thinning approaches by simulating 
    tree growth and comparing outcomes across multiple strategies.
    """)
    
    # ========================================================================
    # DATASET REQUIREMENTS
    # ========================================================================
    
    st.markdown("---")
    st.markdown("## 📋 Dataset Requirements")
    
    st.markdown("""
    To run analysis on ForestThin Analyzer, your dataset must meet the following requirements:
    """)
    
    with st.expander("**File Format and Required Columns**", expanded=True):
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
    
    # ========================================================================
    # PRIMARY THINNING STRATEGIES
    # ========================================================================
    
    st.markdown("---")
    st.markdown("## 🌲 Primary Thinning Strategies")
    
    st.markdown("""
    Primary thinning is the first operation applied to the stand. These strategies 
    determine the initial spatial pattern of tree removal.
    """)
    
    with st.expander("**3-Row Thinning (Remove Every 3rd Row)**"):
        st.markdown("""
        Removes every third row of trees in a systematic pattern. This is one of the most 
        common mechanical thinning approaches in plantation forestry.
        
        **How it works:**
        - Trees are organized by planting rows
        - Every 3rd row is completely removed
        - Remaining trees stay in 2 consecutive rows
        
        **Typical removal:** 30-35% of trees

        """)
    
    with st.expander("**4-Row Thinning (Remove Every 4th Row)**"):
        st.markdown("""
        Similar to 3-row thinning but removes every fourth row instead, this results in 
        lighter thinning intensity.
        
        **How it works:**
        - Every 4th row is completely removed
        - Remaining trees stay in 3 consecutive rows
        - Creates wider spacing between harvest corridors

        
        **Typical removal:** 20-25% of trees

        """)
    
    with st.expander("**5-Row Thinning (Remove Every 5th Row)**"):
        st.markdown("""
        The lightest of the systematic row thinning approaches. Removes every fifth row 
        while keeping four rows between harvest corridors.
        
        **How it works:**
        - Every 5th row is completely removed
        - Remaining trees stay in 4 consecutive rows
        - Minimal disruption to stand structure
        
        
        **Typical removal:** 15-20% of trees
        

        """)
    
    with st.expander("**Variable Row Thinning (3/4/5-row equivalents)**"):
        st.markdown("""
        These strategies remove trees to achieve the same reduction as systematic 
        row thinning, but allow for more flexible row selection.
        
        **How it works:**
        - Target the same removal intensity as 3-row, 4-row, or 5-row
        - Rows are selected more strategically
        - Removes poorly formed or suppressed rows preferentially
        - Maintains overall spacing pattern
        
        **Typical removal:**
        - 3-row equivalent: 30-35%
        - 4-row equivalent: 20-25%
        - 5-row equivalent: 15-20%
        
        """)
    
    # ========================================================================
    # SECONDARY THINNING STRATEGIES
    # ========================================================================
    
    st.markdown("---")
    st.markdown("## 🎯 Secondary Thinning Strategies")
    
    st.markdown("""
    Secondary thinning is applied *after* primary thinning to further refine stand density 
    and improve growing conditions for remaining trees. These strategies use tree measurements 
    and competition metrics to make removal decisions.
    """)
    
    with st.expander("**Thin from Below**"):
        st.markdown("""
        Removes the smallest trees in the stand, keeping the largest and most dominant individuals.
        
        **How it works:**
        - Trees are ranked by diameter (DBH)
        - Smallest trees are removed first
        - Continues until target removal percentage is met
        - Large, dominant trees remain
        
        **Advantages:**
        - Concentrates growth on best trees
        - Increases average tree size on the stand level quickly
        - Favors trees with established dominance
        
        **Disadvantages:**
        - May leave dense patches of large trees
        - Doesn't account for spatial competition
        - Can result in high mortality in tight clusters
        
        """)
    
    with st.expander("**Thin from Above-1 (Neighbors)**"):
        st.markdown("""
        A sophisticated approach that identifies the best "anchor" trees(large dominant trees) and removes their 
        competitors along the same row as the anchors. This maintains dominants while giving them more growing space.
        
        **How it works:**
        - Largest trees(by DBH) are designated as "anchors" (top 10-20%)
        - For each anchor, nearest neighbor trees are identified
        - Neighbors are removed to reduce competition around anchors
        - Process continues until removal target is met
        
        **Advantages:**
        - Protects and releases the best trees
        - Creates growing space around anchors
        - More strategic than simple diameter thinning
        
        **Typical settings:**
        - Anchor fraction: 10-15% (the best trees to keep)
        - Removal fraction: 20-30% (additional thinning)
        
        """)
    
    with st.expander("**Thin from Above-2 (Anchor)**"):
        st.markdown("""
        Similar to Thin from Above-1 but uses spatial distance to identify and remove immediate competitors 
        around anchor trees. Focuses on the 5 nearest neighbors specifically.
        
        **How it works:**
        - Best trees designated as anchors
        - 5 nearest neighbors to each anchor are identified
        - These immediate competitors are strategically removed
        - Creates circular spacing around each anchor
        
        **Advantages:**
        - Very targeted competition reduction
        - Clear spatial pattern around best trees
        - Removes trees most directly impacting anchors
        - Predictable spacing outcomes
        
        **Different from Thin from Above-1:**
        - Thin from Above-1 removes neighbors along the same row
        - Thin from Above-2 removes 5 nearest neighbors surrounding each anchor, regardless of row

        """)
    
    with st.expander("**Thin by CI_Z (Height Competition)**"):
        st.markdown("""
        Removes trees based on height-related competition. Trees that are causing the most 
        crown competition for neighbors are removed first.
        
        **How it works:**
        - CI_Z measures competition based on relative tree heights
        - Trees with high CI_Z are suppressing many neighbors
        - Highest CI_Z trees are removed first
        - Reduces crown competition across the stand
        
        **Advantages:**
        - Addresses above-ground competition directly
        - Helps improve light conditions throughout stand
        - Can identify unexpected competition patterns
        
        """)
    
    with st.expander("**Thin by CI1 (Distance-Dependent Competition)**"):
        st.markdown("""
        The most sophisticated competition-based approach. Considers both tree size and distance 
        to quantify how much each tree is competing with its neighbors.
        
        **How it works:**
        - CI1 = Σ (neighbor DBH / focal tree DBH) / distance
        - Calculated for each tree based on nearby neighbors
        - High CI1 = tree is under heavy competitive pressure
        - Trees with highest CI1 are removed
        
        **Advantages:**
        - Accounts for both size and spacing
        - Removes trees in most competitive situations

        
        **Results:**
        - Spatially heterogeneous pattern
        - Dense clusters get thinned heavily
        - Well-spaced areas thinned lightly
        
        """)
    
    # ========================================================================
    # METRICS EXPLAINED
    # ========================================================================
    
    st.markdown("---")
    st.markdown("## 📊 Output Metrics Explained")
    
    st.markdown("### Thinning Statistics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        with st.expander("**Trees Removed / BA Removed**"):
            st.markdown("""
            **Trees Removed:** Count of trees cut during thinning operations
            
            **BA Removed (%):** Percentage of basal area removed

            """)
        
        with st.expander("**Mean DBH (Diameter at Breast Height)**"):
            st.markdown("""
            **Definition:** Average tree diameter at about 4.5 feet above ground
            
            **Units:** Inches
            
            """)
    
    with col2:
        with st.expander("**QMD (Quadratic Mean Diameter)**"):
            st.markdown("""
            **Definition:** Diameter of the tree with average basal area
            
            **Formula:** QMD = √(mean of DBH²)
            
            **Why different:**
            - QMD weights larger trees more heavily
            - Always slightly larger than mean DBH

            """)
        
        with st.expander("**Thinning Intensity**"):
            st.markdown("""
            **Definition:** Proportion of basal area removed
            
            **Formula:** BA removed / BA before thinning
            

            """)
    
    st.markdown("### Growth Projection Metrics")
    
    col3, col4 = st.columns(2)
    
    with col3:
        with st.expander("**Volume Growth**"):
            st.markdown("""
            **Definition:** Change in total cubic foot volume from after-thinning to final age
            
            **Units:** Cubic feet (ft³)
            
            **How it's calculated:**
            - Uses Tasissa volume equations for loblolly pine
            - Based on DBH and height measurements
            - Only surviving trees included in final volume

            """)
        
        with st.expander("**Survival Rate**"):
            st.markdown("""
            **Definition:** Percentage of post-thinning trees alive at final age
            
            **Formula:** (Alive trees at final age / Trees after thinning) × 100
            
            **Mortality factors:**
            - Competition (CI2 index)
            - Live crown ratio
            - Stand density
            
            **Typical ranges:**
            - Well-thinned stands: 75-90% survival
            - Moderately thinned: 65-80% survival
            - Lightly thinned: 50-70% survival (high competition)

            """)
    
    with col4:
        with st.expander("**Mean Height (Final)**"):
            st.markdown("""
            **Definition:** Average total tree height at final age
            
            **Units:** Feet

            """)
        
        with st.expander("**DBH/Height Growth**"):
            st.markdown("""
            **Definition:** Average increase in DBH or height over projection period
            
            **Units:** Inches (DBH) or feet (height)

            """)
    
    st.markdown("### Per-Acre Metrics")
    
    with st.expander("**Trees Per Acre (TPA)**"):
        st.markdown("""
        **Definition:** Number of trees per acre after accounting for stand area
        
        **Formula:** Total trees / Stand area (acres)

        """)
    
    with st.expander("**Volume Per Acre**"):
        st.markdown("""
        **Definition:** Total cubic foot volume per acre
        
        **Formula:** Total volume / Stand area (acres)

        """)
    
    with st.expander("**Volume Growth Per Acre**"):
        st.markdown("""
        **Definition:** Volume increment per acre over projection period
        
        **Units:** Cubic feet per acre (ft³/acre)
        

        """)
    
    # ========================================================================
    # VERSION INFO
    # ========================================================================
    
    st.markdown("---")


if __name__ == "__main__":
    show()