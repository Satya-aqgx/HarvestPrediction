import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Aquaculture Harvest Prediction Dashboard",
    page_icon="🦐",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    </style>
    """, unsafe_allow_html=True)

# DOC to ABW lookup table
DOC_ABW_LOOKUP = {
    10: 0.40, 20: 1.60, 30: 4.20, 40: 7.00,
    50: 10.00, 60: 13.00, 70: 17.00, 80: 21.00,
    90: 25.50, 100: 28.50, 110: 31.00, 120: 33.50,
    130: 35.50, 140: 37.50
}

# Prediction parameters
SURVIVAL_RATE = 0.80
DAILY_GROWTH = 0.25
FORECAST_DAYS = 10

@st.cache_data
def load_and_process_data(file_path):
    """Load and process the pond data"""
    try:
        df = pd.read_csv(file_path)
        
        # Filter for L. Vannamei only
        df = df[df["cultureType"] == "L. Vannamei"].copy()
        
        # Remove ponds with zero seeds
        df = df[df["totalSeed"] != 0].copy()
        
        # Convert numeric columns
        numeric_columns = ["pondId", "totalSeed", "daysOfCulture", "createdOn", "area"]
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # Remove duplicates
        df = df.dropna(subset=["pondId"]).copy()
        df = df.drop_duplicates(subset=["pondId"]).copy()
        
        # Calculate current DOC
        today_utc = pd.Timestamp.now(tz="UTC").normalize()
        df["installationDate"] = pd.to_datetime(df["createdOn"], unit="ms", utc=True, errors="coerce")
        df["elapsedDays"] = (today_utc - df["installationDate"].dt.normalize()).dt.days
        df["currentDOC"] = df["daysOfCulture"] + df["elapsedDays"]
        
        return df
    except Exception as e:
        st.error(f"Error loading data: {e}")
        return None

def get_estimated_abw(doc):
    """Interpolate ABW from DOC"""
    if pd.isna(doc):
        return None
    
    docs = sorted(DOC_ABW_LOOKUP.keys())
    
    if doc < docs[0] or doc > docs[-1]:
        return None
    
    for i in range(len(docs) - 1):
        lower_doc = docs[i]
        upper_doc = docs[i + 1]
        
        if lower_doc <= doc <= upper_doc:
            lower_abw = DOC_ABW_LOOKUP[lower_doc]
            upper_abw = DOC_ABW_LOOKUP[upper_doc]
            estimated_abw = lower_abw + ((doc - lower_doc) / (upper_doc - lower_doc)) * (upper_abw - lower_abw)
            return estimated_abw
    
    return None

def calculate_pond_biomass(row):
    """Calculate biomass for a pond"""
    total_seed = row["totalSeed"]
    current_doc = row["currentDOC"]
    
    if pd.isna(total_seed) or total_seed <= 0:
        return pd.Series({
            "estimatedABW": np.nan,
            "survivingCount": np.nan,
            "currentBiomassKG": np.nan,
            "predictionStatus": "Invalid totalSeed"
        })
    
    if pd.isna(current_doc) or current_doc < 0:
        return pd.Series({
            "estimatedABW": np.nan,
            "survivingCount": np.nan,
            "currentBiomassKG": np.nan,
            "predictionStatus": "Invalid DOC"
        })
    
    current_abw = get_estimated_abw(current_doc)
    
    if current_abw is None:
        return pd.Series({
            "estimatedABW": np.nan,
            "survivingCount": np.nan,
            "currentBiomassKG": np.nan,
            "predictionStatus": "DOC outside reference range"
        })
    
    surviving_count = total_seed * SURVIVAL_RATE
    current_biomass = (surviving_count * current_abw) / 1000
    
    return pd.Series({
        "estimatedABW": current_abw,
        "survivingCount": surviving_count,
        "currentBiomassKG": current_biomass,
        "predictionStatus": "Success"
    })

# Main Dashboard
def main():
    st.markdown('<div class="main-header">🦐 Aquaculture Harvest Prediction Dashboard</div>', unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("📊 Dashboard Controls")
    st.sidebar.markdown("---")
    
    # File upload
    uploaded_file = st.sidebar.file_uploader("Upload CSV File", type=['csv'])
    
    # Default file path
    default_file = Path("runningPonds.csv")
    
    if uploaded_file is not None:
        df = load_and_process_data(uploaded_file)
    elif default_file.exists():
        df = load_and_process_data(default_file)
    else:
        st.error("❌ No data file found. Please upload a CSV file.")
        return
    
    if df is None or len(df) == 0:
        st.warning("⚠️ No data available to display.")
        return
    
    # Calculate biomass
    df[["estimatedABW", "survivingCount", "currentBiomassKG", "predictionStatus"]] = df.apply(
        calculate_pond_biomass, axis=1
    )
    
    # Filter options in sidebar
    st.sidebar.markdown("### Filters")
    
    # Pond status filter
    status_options = ["All"] + df["pondStatus"].unique().tolist()
    selected_status = st.sidebar.selectbox("Pond Status", status_options)
    
    # Prediction status filter
    pred_status_options = ["All"] + df["predictionStatus"].unique().tolist()
    selected_pred_status = st.sidebar.selectbox("Prediction Status", pred_status_options)
    
    # Apply filters
    filtered_df = df.copy()
    if selected_status != "All":
        filtered_df = filtered_df[filtered_df["pondStatus"] == selected_status]
    if selected_pred_status != "All":
        filtered_df = filtered_df[filtered_df["predictionStatus"] == selected_pred_status]
    
    # Key Metrics
    st.markdown("## 📈 Key Metrics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Ponds",
            len(filtered_df),
            delta=None
        )
    
    with col2:
        successful_preds = len(filtered_df[filtered_df["predictionStatus"] == "Success"])
        st.metric(
            "Successful Predictions",
            successful_preds,
            delta=f"{successful_preds/len(filtered_df)*100:.1f}%" if len(filtered_df) > 0 else "0%"
        )
    
    with col3:
        total_biomass = filtered_df["currentBiomassKG"].sum()
        st.metric(
            "Total Biomass (KG)",
            f"{total_biomass:,.0f}" if not pd.isna(total_biomass) else "N/A"
        )
    
    with col4:
        total_seed = filtered_df["totalSeed"].sum()
        st.metric(
            "Total Seeds",
            f"{total_seed:,.0f}"
        )
    
    st.markdown("---")
    
    # Two column layout for charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎯 Prediction Status Distribution")
        pred_status_counts = filtered_df["predictionStatus"].value_counts()
        fig1 = px.pie(
            values=pred_status_counts.values,
            names=pred_status_counts.index,
            color_discrete_sequence=px.colors.qualitative.Set3
        )
        fig1.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.markdown("### 🏊 Pond Status Distribution")
        pond_status_counts = filtered_df["pondStatus"].value_counts()
        fig2 = px.bar(
            x=pond_status_counts.index,
            y=pond_status_counts.values,
            labels={'x': 'Status', 'y': 'Count'},
            color=pond_status_counts.values,
            color_continuous_scale='Blues'
        )
        fig2.update_layout(showlegend=False)
        st.plotly_chart(fig2, use_container_width=True)
    
    # Biomass analysis
    st.markdown("### 📊 Biomass Analysis by Pond")
    
    # Filter successful predictions for biomass chart
    success_df = filtered_df[filtered_df["predictionStatus"] == "Success"].copy()
    
    if len(success_df) > 0:
        # Sort by biomass
        success_df_sorted = success_df.sort_values("currentBiomassKG", ascending=True).tail(15)
        
        fig3 = px.bar(
            success_df_sorted,
            x="currentBiomassKG",
            y="name",
            orientation='h',
            labels={'currentBiomassKG': 'Biomass (KG)', 'name': 'Pond Name'},
            color='currentBiomassKG',
            color_continuous_scale='Viridis',
            title="Top 15 Ponds by Current Biomass"
        )
        fig3.update_layout(height=500)
        st.plotly_chart(fig3, use_container_width=True)
        
        # DOC vs ABW scatter
        st.markdown("### 📉 DOC vs Average Body Weight (ABW)")
        fig4 = px.scatter(
            success_df,
            x="currentDOC",
            y="estimatedABW",
            size="currentBiomassKG",
            hover_data=["name", "totalSeed"],
            labels={'currentDOC': 'Days of Culture (DOC)', 'estimatedABW': 'ABW (grams)'},
            color='currentBiomassKG',
            color_continuous_scale='RdYlGn'
        )
        st.plotly_chart(fig4, use_container_width=True)
    else:
        st.info("ℹ️ No successful predictions available for biomass analysis.")
    
    # Seed variety analysis
    st.markdown("### 🌱 Seed Variety Distribution")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        variety_counts = filtered_df["seedVariety"].value_counts().head(10)
        fig5 = px.bar(
            x=variety_counts.index,
            y=variety_counts.values,
            labels={'x': 'Seed Variety', 'y': 'Count'},
            color=variety_counts.values,
            color_continuous_scale='Teal'
        )
        fig5.update_layout(showlegend=False, xaxis_tickangle=-45)
        st.plotly_chart(fig5, use_container_width=True)
    
    with col2:
        st.markdown("#### Variety Stats")
        total_varieties = filtered_df["seedVariety"].nunique()
        most_common = filtered_df["seedVariety"].mode()[0] if len(filtered_df["seedVariety"].mode()) > 0 else "N/A"
        st.metric("Total Varieties", total_varieties)
        st.metric("Most Common", most_common)
    
    # Detailed data table
    st.markdown("---")
    st.markdown("## 📋 Detailed Pond Data")
    
    # Select columns to display
    display_columns = [
        "pondId", "name", "area", "totalSeed", "currentDOC",
        "estimatedABW", "survivingCount", "currentBiomassKG",
        "pondStatus", "predictionStatus", "seedVariety"
    ]
    
    display_df = filtered_df[display_columns].copy()
    
    # Format numeric columns
    display_df["currentBiomassKG"] = display_df["currentBiomassKG"].apply(
        lambda x: f"{x:,.2f}" if pd.notna(x) else "N/A"
    )
    display_df["survivingCount"] = display_df["survivingCount"].apply(
        lambda x: f"{x:,.0f}" if pd.notna(x) else "N/A"
    )
    display_df["estimatedABW"] = display_df["estimatedABW"].apply(
        lambda x: f"{x:.2f}g" if pd.notna(x) else "N/A"
    )
    
    st.dataframe(
        display_df,
        use_container_width=True,
        height=400
    )
    
    # Download button
    csv = filtered_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Full Data as CSV",
        data=csv,
        file_name=f"harvest_prediction_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; padding: 1rem;'>
            <p>🦐 Aquaculture Harvest Prediction Dashboard | Updated: {}</p>
        </div>
        """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
