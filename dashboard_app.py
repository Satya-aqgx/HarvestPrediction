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
    initial_sidebar_state="collapsed"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 1rem;
    }
    .sub-header {
        text-align: center;
        color: #666;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
        text-align: center;
    }
    .big-metric {
        font-size: 3rem;
        font-weight: bold;
        color: #1f77b4;
    }
    .section-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #333;
        margin-top: 2rem;
        margin-bottom: 1rem;
        border-bottom: 2px solid #1f77b4;
        padding-bottom: 0.5rem;
    }
    .methodology-box {
        background-color: #f8f9fa;
        padding: 1.5rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
        margin: 1rem 0;
    }
    .formula {
        font-family: 'Courier New', monospace;
        background-color: #e9ecef;
        padding: 0.5rem;
        border-radius: 0.25rem;
        margin: 0.25rem 0;
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

def calculate_10_day_forecast(valid_ponds_df):
    """Calculate 10-day forecast for valid ponds"""
    forecast_records = []
    
    for _, pond in valid_ponds_df.iterrows():
        # Calculate 10th-day DOC
        future_doc = pond["currentDOC"] + FORECAST_DAYS
        current_abw = pond["estimatedABW"]
        
        # Calculate 10th-day ABW
        future_abw = current_abw + (DAILY_GROWTH * FORECAST_DAYS)
        
        # Calculate 10th-day biomass
        harvest_kg = (pond["survivingCount"] * future_abw) / 1000
        
        # Calculate shrimp per kg
        current_shrimp_per_kg = 1000 / current_abw
        estimated_shrimp_per_kg = 1000 / future_abw
        
        forecast_records.append({
            "pondId": pond["pondId"],
            "name": pond["name"],
            "area": pond["area"],
            "totalSeed": pond["totalSeed"],
            "currentDoc": pond["currentDOC"],
            "currentABW": current_abw,
            "currentBiomassKG": pond["currentBiomassKG"],
            "forecastDOC": future_doc,
            "estimatedABW": future_abw,
            "estimatedHarvestKG": harvest_kg,
            "currentShrimpPerKG": round(current_shrimp_per_kg, 2),
            "estimatedShrimpPerKG": round(estimated_shrimp_per_kg, 2)
        })
    
    # Create DataFrame
    forecast_df = pd.DataFrame(forecast_records)
    forecast_df = forecast_df.sort_values(by="forecastDOC", ascending=True).reset_index(drop=True)
    
    return forecast_df

def create_count_per_kg_grouping(forecast_df):
    """Group forecast by shrimp count per kg"""
    # Round shrimp per kg to nearest integer for grouping
    forecast_df_copy = forecast_df.copy()
    forecast_df_copy["estimatedShrimpPerKG_rounded"] = forecast_df_copy["estimatedShrimpPerKG"].round().astype(int)
    
    # Group by count per kg
    grouped = (
        forecast_df_copy
        .groupby("estimatedShrimpPerKG_rounded")
        .agg(
            pondCount=("pondId", "count"),
            currentBiomassKG=("currentBiomassKG", "sum"),
            estimatedHarvestKG=("estimatedHarvestKG", "sum")
        )
        .reset_index()
        .sort_values("estimatedShrimpPerKG_rounded")
    )
    
    grouped.columns = ['estimatedShrimpPerKG', 'pondCount', 'currentBiomassKG', 'estimatedHarvestKG']
    
    return grouped

# Main Dashboard
def main():
    # Header
    st.markdown('<div class="main-header">🦐 Aquaculture Harvest Prediction Dashboard</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-header">Generated on {datetime.now().strftime("%B %d, %Y at %H:%M:%S")}</div>', unsafe_allow_html=True)
    
    # Load data
    default_file = Path("runningPonds.csv")
    
    if not default_file.exists():
        st.error("❌ Data file 'runningPonds.csv' not found. Please ensure the file is in the same directory.")
        return
    
    df = load_and_process_data(default_file)
    
    if df is None or len(df) == 0:
        st.warning("⚠️ No data available to display.")
        return
    
    # Calculate biomass for current state
    df[["estimatedABW", "survivingCount", "currentBiomassKG", "predictionStatus"]] = df.apply(
        calculate_pond_biomass, axis=1
    )
    
    # Filter successful predictions for forecast
    valid_ponds = df[df["predictionStatus"] == "Success"].copy()
    
    # Calculate 10-day forecast
    forecast_df = calculate_10_day_forecast(valid_ponds)
    
    # === SECTION 1: KEY METRICS ===
    st.markdown("## 📊 Overview")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="Total Ponds",
            value=len(df),
            delta=None
        )
    
    with col2:
        vannamei_count = len(df[df["cultureType"] == "L. Vannamei"])
        st.metric(
            label="L. Vannamei Ponds",
            value=vannamei_count,
            delta=f"{vannamei_count/len(df)*100:.0f}%" if len(df) > 0 else "0%"
        )
    
    with col3:
        successful = len(df[df["predictionStatus"] == "Success"])
        st.metric(
            label="Successful Predictions",
            value=successful,
            delta=f"{successful/len(df)*100:.0f}% success rate" if len(df) > 0 else "0%"
        )
    
    with col4:
        failed = len(df[df["predictionStatus"] != "Success"])
        st.metric(
            label="Failed Predictions",
            value=failed,
            delta=f"DOC out of range" if failed > 0 else "All valid"
        )
    
    st.markdown("---")
    
    # === SECTION 2: BIOMASS COMPARISON ===
    st.markdown("## 🎯 Current vs 10-Day Forecast")
    
    current_total = df["currentBiomassKG"].sum()
    forecast_total = forecast_df["estimatedHarvestKG"].sum()
    growth = forecast_total - current_total
    growth_pct = (growth / current_total * 100) if current_total > 0 else 0
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.markdown("### Current Total Biomass")
        st.markdown(f'<div class="big-metric">{current_total:,.0f} KG</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.markdown("### Estimated in 10 Days")
        st.markdown(f'<div class="big-metric">{forecast_total:,.0f} KG</div>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: #2ca02c; font-size: 1.2rem; font-weight: bold;">↑ +{growth:,.0f} KG (+{growth_pct:.1f}%)</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Comparison chart
    comparison_data = pd.DataFrame({
        'Period': ['Current', '10-Day Forecast'],
        'Biomass (KG)': [current_total, forecast_total]
    })
    
    fig_comparison = px.bar(
        comparison_data,
        x='Period',
        y='Biomass (KG)',
        text='Biomass (KG)',
        color='Period',
        color_discrete_map={'Current': '#1f77b4', '10-Day Forecast': '#2ca02c'}
    )
    fig_comparison.update_traces(texttemplate='%{text:,.0f} KG', textposition='outside')
    fig_comparison.update_layout(
        showlegend=False,
        height=400,
        yaxis_title="Total Biomass (KG)"
    )
    st.plotly_chart(fig_comparison, use_container_width=True)
    
    st.markdown("---")
    
    # === SECTION 3: METHODOLOGY ===
    st.markdown("## 📋 Prediction Methodology & Assumptions")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown('<div class="methodology-box">', unsafe_allow_html=True)
        st.markdown("### 🔧 Prediction Parameters")
        st.markdown(f"""
        - **Survival Rate:** {SURVIVAL_RATE * 100:.0f}%
        - **Daily Growth Rate:** {DAILY_GROWTH} grams/day
        - **Forecast Period:** {FORECAST_DAYS} days
        """)
        st.markdown('</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="methodology-box">', unsafe_allow_html=True)
        st.markdown("### 📐 Key Formulas")
        st.markdown('<div class="formula">Current DOC = daysOfCulture + elapsedDays</div>', unsafe_allow_html=True)
        st.markdown('<div class="formula">Surviving Count = totalSeed × survivalRate</div>', unsafe_allow_html=True)
        st.markdown('<div class="formula">Current Biomass = survivingCount × ABW ÷ 1000</div>', unsafe_allow_html=True)
        st.markdown('<div class="formula">Future ABW = currentABW + (dailyGrowth × 10)</div>', unsafe_allow_html=True)
        st.markdown('<div class="formula">Shrimp per KG = 1000 ÷ ABW</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="methodology-box">', unsafe_allow_html=True)
        st.markdown("### 📈 DOC to ABW Lookup Table")
        lookup_df = pd.DataFrame(list(DOC_ABW_LOOKUP.items()), columns=['DOC (Days)', 'ABW (grams)'])
        st.dataframe(lookup_df, use_container_width=True, height=400)
        st.markdown("*Interpolation used for values between reference points*")
        st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # === SECTION 4: PREDICTION SUCCESS RATE ===
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🎯 Prediction Success Rate")
        success_data = df["predictionStatus"].value_counts()
        fig_success = px.pie(
            values=success_data.values,
            names=success_data.index,
            color_discrete_map={'Success': '#2ca02c', 'DOC outside reference range': '#ff7f0e'}
        )
        fig_success.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_success, use_container_width=True)
    
    with col2:
        st.markdown("### 📊 Prediction Statistics")
        st.markdown(f"""
        - **Total Ponds Analyzed:** {len(df)}
        - **Successful Predictions:** {successful}
        - **Out of Range:** {failed}
        - **Success Rate:** {successful/len(df)*100:.1f}%
        
        *Ponds with DOC outside 10-140 days cannot be predicted using the reference table.*
        """)
    
    st.markdown("---")
    
    # === SECTION 5: SHRIMP COUNT PER KG ===
    st.markdown("## 🦐 Shrimp Count per KG Distribution (10-Day Forecast)")
    
    grouped_forecast = create_count_per_kg_grouping(forecast_df)
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        fig_count = px.bar(
            grouped_forecast,
            x='estimatedShrimpPerKG',
            y='estimatedHarvestKG',
            text='pondCount',
            labels={
                'estimatedShrimpPerKG': 'Estimated Count per KG',
                'estimatedHarvestKG': 'Total Biomass (KG)',
                'pondCount': 'Pond Count'
            },
            color='estimatedHarvestKG',
            color_continuous_scale='Teal'
        )
        fig_count.update_traces(texttemplate='%{text} ponds', textposition='outside')
        fig_count.update_layout(
            height=400,
            showlegend=False,
            xaxis_title="Shrimp Count per KG (Estimated)",
            yaxis_title="Total Forecast Biomass (KG)"
        )
        st.plotly_chart(fig_count, use_container_width=True)
    
    with col2:
        st.markdown("### Summary by Count/KG")
        display_grouped = grouped_forecast.copy()
        display_grouped['estimatedHarvestKG'] = display_grouped['estimatedHarvestKG'].apply(lambda x: f"{x:,.0f}")
        display_grouped['currentBiomassKG'] = display_grouped['currentBiomassKG'].apply(lambda x: f"{x:,.0f}")
        display_grouped.columns = ['Count/KG', 'Ponds', 'Current (KG)', 'Forecast (KG)']
        st.dataframe(display_grouped, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # === SECTION 6: TOP PERFORMERS ===
    st.markdown("## 🏆 Top 10 Ponds by Forecast Harvest")
    
    top_ponds = forecast_df.nlargest(10, 'estimatedHarvestKG')
    
    fig_top = px.bar(
        top_ponds,
        y='name',
        x='estimatedHarvestKG',
        orientation='h',
        text='estimatedHarvestKG',
        color='estimatedHarvestKG',
        color_continuous_scale='Viridis',
        labels={
            'estimatedHarvestKG': 'Estimated Harvest (KG)',
            'name': 'Pond Name'
        }
    )
    fig_top.update_traces(texttemplate='%{text:,.0f} KG', textposition='outside')
    fig_top.update_layout(
        height=500,
        showlegend=False,
        yaxis={'categoryorder': 'total ascending'}
    )
    st.plotly_chart(fig_top, use_container_width=True)
    
    st.markdown("---")
    
    # === SECTION 7: DOC VS ABW ANALYSIS ===
    st.markdown("## � Days of Culture (DOC) vs Average Body Weight (ABW)")
    
    fig_scatter = px.scatter(
        valid_ponds,
        x='currentDOC',
        y='estimatedABW',
        size='currentBiomassKG',
        color='currentBiomassKG',
        hover_data=['name', 'totalSeed', 'area'],
        labels={
            'currentDOC': 'Current DOC (Days)',
            'estimatedABW': 'Current ABW (grams)',
            'currentBiomassKG': 'Biomass (KG)'
        },
        color_continuous_scale='RdYlGn'
    )
    
    # Add reference line from lookup table
    lookup_x = list(DOC_ABW_LOOKUP.keys())
    lookup_y = list(DOC_ABW_LOOKUP.values())
    fig_scatter.add_trace(
        go.Scatter(
            x=lookup_x,
            y=lookup_y,
            mode='lines',
            name='Reference Curve',
            line=dict(color='red', width=2, dash='dash')
        )
    )
    
    fig_scatter.update_layout(height=500)
    st.plotly_chart(fig_scatter, use_container_width=True)
    
    st.markdown("---")
    
    # === SECTION 8: SUMMARY STATISTICS ===
    st.markdown("## 📋 Summary Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_seeds = df["totalSeed"].sum()
        st.metric("Total Seeds Stocked", f"{total_seeds:,.0f}")
    
    with col2:
        estimated_surviving = total_seeds * SURVIVAL_RATE
        st.metric("Estimated Surviving", f"{estimated_surviving:,.0f}")
    
    with col3:
        avg_abw = valid_ponds["estimatedABW"].mean()
        st.metric("Average Current ABW", f"{avg_abw:.2f}g")
    
    with col4:
        avg_doc = valid_ponds["currentDOC"].mean()
        st.metric("Average DOC", f"{avg_doc:.0f} days")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_future_abw = forecast_df["estimatedABW"].mean()
        st.metric("Average Day-10 ABW", f"{avg_future_abw:.2f}g")
    
    with col2:
        avg_current_per_kg = (1000 / valid_ponds["estimatedABW"]).mean()
        st.metric("Avg Shrimp/KG (Now)", f"{avg_current_per_kg:.0f}")
    
    with col3:
        avg_future_per_kg = (1000 / forecast_df["estimatedABW"]).mean()
        st.metric("Avg Shrimp/KG (Day 10)", f"{avg_future_per_kg:.0f}")
    
    with col4:
        total_area = df["area"].sum()
        st.metric("Total Area", f"{total_area:.0f} Acres")
    
    st.markdown("---")
    
    # === SECTION 9: DETAILED FORECAST TABLE ===
    st.markdown("## � Detailed 10-Day Forecast by Pond")
    
    # Prepare display dataframe
    display_forecast = forecast_df[[
        'pondId', 'name', 'area', 'totalSeed', 'currentDoc', 'currentABW',
        'currentBiomassKG', 'forecastDOC', 'estimatedABW', 'estimatedHarvestKG',
        'currentShrimpPerKG', 'estimatedShrimpPerKG'
    ]].copy()
    
    # Format columns
    display_forecast['totalSeed'] = display_forecast['totalSeed'].apply(lambda x: f"{x:,.0f}")
    display_forecast['currentABW'] = display_forecast['currentABW'].apply(lambda x: f"{x:.2f}g")
    display_forecast['currentBiomassKG'] = display_forecast['currentBiomassKG'].apply(lambda x: f"{x:,.2f}")
    display_forecast['estimatedABW'] = display_forecast['estimatedABW'].apply(lambda x: f"{x:.2f}g")
    display_forecast['estimatedHarvestKG'] = display_forecast['estimatedHarvestKG'].apply(lambda x: f"{x:,.2f}")
    
    # Rename columns
    display_forecast.columns = [
        'Pond ID', 'Pond Name', 'Area (Acres)', 'Seeds', 'Current DOC',
        'Current ABW', 'Current Biomass (KG)', 'Day-10 DOC', 'Day-10 ABW',
        'Day-10 Harvest (KG)', 'Current Count/KG', 'Day-10 Count/KG'
    ]
    
    st.dataframe(display_forecast, use_container_width=True, height=400)
    
    # Download button
    csv = forecast_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Detailed Forecast as CSV",
        data=csv,
        file_name=f"harvest_forecast_10days_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )
    
    # === FOOTER ===
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; padding: 1rem;'>
            <p><strong>ℹ️ Data Source:</strong> runningPonds.csv | 
            <strong>📅 Generated:</strong> {} | 
            <strong>🔄 Methodology:</strong> 80% survival rate, 0.25g/day growth, 10-day forecast</p>
        </div>
        """.format(datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
