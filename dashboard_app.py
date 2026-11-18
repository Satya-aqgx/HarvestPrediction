import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

# Page configuration
st.set_page_config(
    page_title="Count 366 - Vannamei Biomass Prediction",
    page_icon="🦐",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom CSS
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
        font-size: 0.9rem;
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
    st.markdown('<div class="main-header">Count 366 - Vannamei Biomass Prediction</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-header">10-Day harvest forecast based on current pond data | Generated: {datetime.now().strftime("%B %d, %Y at %H:%M")}</div>', unsafe_allow_html=True)
    
    # Description
    st.markdown("""
    This dashboard predicts the estimated biomass for L. Vannamei ponds in the Count 366 system. 
    Predictions are based on current pond conditions and key assumptions including survival rate, 
    daily growth rate, and days of culture.
    """)
    st.markdown("---")
    
    # Load data
    default_file = Path("runningPonds.csv")
    
    if not default_file.exists():
        st.error("❌ Data file 'runningPonds.csv' not found.")
        return
    
    df = load_and_process_data(default_file)
    
    if df is None or len(df) == 0:
        st.warning("⚠️ No data available.")
        return
    
    # Calculate biomass
    df[["estimatedABW", "survivingCount", "currentBiomassKG", "predictionStatus"]] = df.apply(
        calculate_pond_biomass, axis=1
    )
    
    # Filter successful predictions
    valid_ponds = df[df["predictionStatus"] == "Success"].copy()
    
    # Calculate 10-day forecast
    forecast_df = calculate_10_day_forecast(valid_ponds)
    
    # === SECTION 1: METHODOLOGY ===
    st.markdown("## Methodology")
    
    with st.expander("View Assumptions & Calculation Methods", expanded=False):
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown('<div class="methodology-box">', unsafe_allow_html=True)
            st.markdown("### Key Assumptions")
            st.markdown(f"""
            - **Survival Rate:** {SURVIVAL_RATE * 100:.0f}% ({SURVIVAL_RATE})
            - **Daily Growth Rate:** {DAILY_GROWTH} grams/day
            - **Forecast Period:** {FORECAST_DAYS} days
            
            *These assumptions are used to calculate biomass projections for all ponds in the Count 366 system.*
            """)
            st.markdown('</div>', unsafe_allow_html=True)
            
            st.markdown('<div class="methodology-box">', unsafe_allow_html=True)
            st.markdown("### Calculation Formulas")
            st.markdown('<div class="formula">Surviving Count = totalSeed × survivalRate</div>', unsafe_allow_html=True)
            st.markdown('<div class="formula">Current Biomass (KG) = (survivingCount × currentABW) ÷ 1000</div>', unsafe_allow_html=True)
            st.markdown('<div class="formula">Future DOC = currentDOC + forecastPeriod</div>', unsafe_allow_html=True)
            st.markdown('<div class="formula">Future ABW = currentABW + (dailyGrowth × forecastPeriod)</div>', unsafe_allow_html=True)
            st.markdown('<div class="formula">Future Biomass (KG) = (survivingCount × futureABW) ÷ 1000</div>', unsafe_allow_html=True)
            st.markdown('<div class="formula">Shrimp Count per KG = 1000 ÷ ABW</div>', unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col2:
            st.markdown('<div class="methodology-box">', unsafe_allow_html=True)
            st.markdown("### DOC to ABW Reference Table")
            st.markdown("*Days of Culture (DOC) to Average Body Weight (ABW)*")
            lookup_df = pd.DataFrame(list(DOC_ABW_LOOKUP.items()), columns=['DOC (Days)', 'ABW (grams)'])
            st.dataframe(lookup_df, use_container_width=True, height=400, hide_index=True)
            st.markdown("*Linear interpolation applied for values between reference points*")
            st.markdown('</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # === SECTION 2: KEY INSIGHTS ===
    st.markdown("## Key Insights")
    
    # Calculate totals
    vannamei_count = len(df)
    total_seeds = df["totalSeed"].sum()
    current_total_biomass = valid_ponds["currentBiomassKG"].sum()
    forecast_total_biomass = forecast_df["estimatedHarvestKG"].sum()
    growth = forecast_total_biomass - current_total_biomass
    growth_pct = (growth / current_total_biomass * 100) if current_total_biomass > 0 else 0
    successful = len(valid_ponds)
    
    # Row 1: Basic counts
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="Total Ponds",
            value=vannamei_count
        )
    
    with col2:
        st.metric(
            label="Total Seeds",
            value=f"{total_seeds:,.0f}"
        )
    
    with col3:
        st.metric(
            label="Successful Predictions",
            value=successful
        )
    
    st.markdown("---")
    
    # Row 2: Biomass comparison - BIG NUMBERS
    st.markdown("### Biomass Comparison")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.markdown("#### Current Total Biomass")
        st.markdown(f'<div class="big-metric">{current_total_biomass:,.0f} KG</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        st.markdown('<div class="metric-card">', unsafe_allow_html=True)
        st.markdown("#### Estimated Biomass (After 10 Days)")
        st.markdown(f'<div class="big-metric">{forecast_total_biomass:,.0f} KG</div>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: #2ca02c; font-size: 1.5rem; font-weight: bold;">↑ +{growth:,.0f} KG (+{growth_pct:.1f}%)</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Comparison chart
    comparison_data = pd.DataFrame({
        'Period': ['Current', 'After 10 Days'],
        'Biomass (KG)': [current_total_biomass, forecast_total_biomass]
    })
    
    fig_comparison = px.bar(
        comparison_data,
        x='Period',
        y='Biomass (KG)',
        text='Biomass (KG)',
        color='Period',
        color_discrete_map={'Current': '#1f77b4', 'After 10 Days': '#2ca02c'}
    )
    fig_comparison.update_traces(texttemplate='%{text:,.0f} KG', textposition='outside')
    fig_comparison.update_layout(
        showlegend=False,
        height=400,
        yaxis_title="Total Biomass (KG)",
        xaxis_title=""
    )
    st.plotly_chart(fig_comparison, use_container_width=True)
    
    st.markdown("---")
    
    # === SECTION 3: SHRIMP COUNT PER KG ===
    st.markdown("## Shrimp Count per KG Distribution (After 10 Days)")
    
    grouped_forecast = create_count_per_kg_grouping(forecast_df)
    
    # Create grouped bar chart
    fig_count = go.Figure()
    
    fig_count.add_trace(go.Bar(
        x=grouped_forecast['estimatedShrimpPerKG'],
        y=grouped_forecast['currentBiomassKG'],
        name='Current Biomass',
        text=grouped_forecast['currentBiomassKG'].apply(lambda x: f'{x:,.0f} KG'),
        textposition='auto',
        marker_color='#1f77b4',
        hovertemplate='Count/KG: %{x}<br>Current: %{y:,.0f} KG<extra></extra>'
    ))
    
    fig_count.add_trace(go.Bar(
        x=grouped_forecast['estimatedShrimpPerKG'],
        y=grouped_forecast['estimatedHarvestKG'],
        name='10-Day Forecast',
        text=grouped_forecast['estimatedHarvestKG'].apply(lambda x: f'{x:,.0f} KG'),
        textposition='auto',
        marker_color='#2ca02c',
        hovertemplate='Count/KG: %{x}<br>Forecast: %{y:,.0f} KG<extra></extra>'
    ))
    
    fig_count.update_layout(
        barmode='group',
        height=450,
        xaxis_title="Shrimp Count per KG",
        yaxis_title="Total Biomass (KG)",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        hovermode='x unified'
    )
    
    st.plotly_chart(fig_count, use_container_width=True)
    
    # Summary table
    st.markdown("### Summary by Count per KG")
    display_grouped = grouped_forecast.copy()
    display_grouped['currentBiomassKG'] = display_grouped['currentBiomassKG'].apply(lambda x: f"{x:,.2f}")
    display_grouped['estimatedHarvestKG'] = display_grouped['estimatedHarvestKG'].apply(lambda x: f"{x:,.2f}")
    display_grouped.columns = ['Count/KG', 'Number of Ponds', 'Current Biomass (KG)', '10-Day Forecast (KG)']
    st.dataframe(display_grouped, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # === SECTION 4: TOP 10 PONDS ===
    st.markdown("## Top 10 Ponds by Estimated Harvest (After 10 Days)")
    
    top_ponds = forecast_df.nlargest(10, 'estimatedHarvestKG')
    top_ponds['label'] = top_ponds.apply(lambda x: f"Pond {int(x['pondId'])}", axis=1)
    
    fig_top = px.bar(
        top_ponds,
        y='label',
        x='estimatedHarvestKG',
        orientation='h',
        text='estimatedHarvestKG',
        color='estimatedHarvestKG',
        color_continuous_scale='Viridis',
        labels={
            'estimatedHarvestKG': 'Estimated Harvest (KG)',
            'label': 'Pond ID'
        }
    )
    fig_top.update_traces(texttemplate='%{text:,.0f} KG', textposition='outside')
    fig_top.update_layout(
        height=500,
        showlegend=False,
        yaxis={'categoryorder': 'total ascending'},
        xaxis_title="Estimated Harvest after 10 Days (KG)",
        yaxis_title=""
    )
    st.plotly_chart(fig_top, use_container_width=True)
    
    st.markdown("---")
    
    # === SECTION 5: PREDICTION BREAKDOWN ===
    st.markdown("## Prediction Success Breakdown")
    
    col1, col2 = st.columns(2)
    
    with col1:
        success_data = df["predictionStatus"].value_counts()
        fig_success = px.pie(
            values=success_data.values,
            names=success_data.index,
            color_discrete_map={
                'Success': '#2ca02c',
                'DOC outside reference range': '#ff7f0e',
                'Invalid DOC': '#d62728',
                'Invalid totalSeed': '#d62728'
            }
        )
        fig_success.update_traces(textposition='inside', textinfo='percent+label')
        fig_success.update_layout(height=400)
        st.plotly_chart(fig_success, use_container_width=True)
    
    with col2:
        st.markdown("### Prediction Details")
        st.markdown(f"""
        **Total Ponds:** {len(df)}
        
        **Successful Predictions:** {successful}
        - Ponds with DOC within reference range (10-140 days)
        - Complete prediction data available
        
        **Failed Predictions:** {len(df) - successful}
        - Ponds with DOC outside 10-140 day range
        - Cannot interpolate ABW from reference table
        
        **Success Rate:** {successful/len(df)*100:.1f}%
        """)
    
    st.markdown("---")
    
    # === SECTION 6: DETAILED TABLE ===
    st.markdown("## Detailed 10-Day Forecast by Pond")
    
    display_forecast = forecast_df[[
        'pondId', 'name', 'area', 'totalSeed', 'currentDoc', 'currentABW',
        'currentBiomassKG', 'forecastDOC', 'estimatedABW', 'estimatedHarvestKG',
        'currentShrimpPerKG', 'estimatedShrimpPerKG'
    ]].copy()
    
    # Format columns
    display_forecast['totalSeed'] = display_forecast['totalSeed'].apply(lambda x: f"{x:,.0f}")
    display_forecast['currentABW'] = display_forecast['currentABW'].apply(lambda x: f"{x:.2f}")
    display_forecast['currentBiomassKG'] = display_forecast['currentBiomassKG'].apply(lambda x: f"{x:,.2f}")
    display_forecast['estimatedABW'] = display_forecast['estimatedABW'].apply(lambda x: f"{x:.2f}")
    display_forecast['estimatedHarvestKG'] = display_forecast['estimatedHarvestKG'].apply(lambda x: f"{x:,.2f}")
    display_forecast['currentShrimpPerKG'] = display_forecast['currentShrimpPerKG'].apply(lambda x: f"{x:.0f}")
    display_forecast['estimatedShrimpPerKG'] = display_forecast['estimatedShrimpPerKG'].apply(lambda x: f"{x:.0f}")
    
    display_forecast.columns = [
        'Pond ID', 'Pond Name', 'Area (Acres)', 'Seeds', 'Current DOC',
        'Current ABW (g)', 'Current Biomass (KG)', 'Day-10 DOC', 'Day-10 ABW (g)',
        'Day-10 Forecast (KG)', 'Current Count/KG', 'Day-10 Count/KG'
    ]
    
    st.dataframe(display_forecast, use_container_width=True, height=500)

if __name__ == "__main__":
    main()
