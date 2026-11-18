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
    initial_sidebar_state="expanded"
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

# DOC to ABW lookup table - Default values
DEFAULT_DOC_ABW_LOOKUP = {
    10: 0.40, 20: 1.60, 30: 4.20, 40: 7.00,
    50: 10.00, 60: 13.00, 70: 17.00, 80: 21.00,
    90: 25.50, 100: 28.50, 110: 31.00, 120: 33.50,
    130: 35.50, 140: 37.50
}

# Default prediction parameters
DEFAULT_SURVIVAL_RATE = 0.80
DEFAULT_DAILY_GROWTH = 0.25
DEFAULT_FORECAST_DAYS = 10

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

def get_estimated_abw(doc, doc_abw_lookup):
    """Interpolate ABW from DOC"""
    if pd.isna(doc):
        return None
    
    docs = sorted(doc_abw_lookup.keys())
    
    if doc < docs[0] or doc > docs[-1]:
        return None
    
    for i in range(len(docs) - 1):
        lower_doc = docs[i]
        upper_doc = docs[i + 1]
        
        if lower_doc <= doc <= upper_doc:
            lower_abw = doc_abw_lookup[lower_doc]
            upper_abw = doc_abw_lookup[upper_doc]
            estimated_abw = lower_abw + ((doc - lower_doc) / (upper_doc - lower_doc)) * (upper_abw - lower_abw)
            return estimated_abw
    
    return None

def calculate_pond_biomass(row, survival_rate, doc_abw_lookup):
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
    
    current_abw = get_estimated_abw(current_doc, doc_abw_lookup)
    
    if current_abw is None:
        return pd.Series({
            "estimatedABW": np.nan,
            "survivingCount": np.nan,
            "currentBiomassKG": np.nan,
            "predictionStatus": "DOC outside reference range"
        })
    
    surviving_count = total_seed * survival_rate
    current_biomass = (surviving_count * current_abw) / 1000
    
    return pd.Series({
        "estimatedABW": current_abw,
        "survivingCount": surviving_count,
        "currentBiomassKG": current_biomass,
        "predictionStatus": "Success"
    })

def calculate_10_day_forecast(valid_ponds_df, survival_rate, daily_growth, forecast_days):
    """Calculate 10-day forecast for valid ponds"""
    forecast_records = []
    
    for _, pond in valid_ponds_df.iterrows():
        # Calculate future DOC
        future_doc = pond["currentDOC"] + forecast_days
        current_abw = pond["estimatedABW"]
        
        # Calculate future ABW
        future_abw = current_abw + (daily_growth * forecast_days)
        
        # Calculate future biomass
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
    # === SIDEBAR: PARAMETER INPUTS ===
    st.sidebar.title("Prediction Parameters")
    st.sidebar.markdown("Adjust the parameters below and click **'Apply Changes'** to update predictions.")
    st.sidebar.markdown("---")
    
    # Initialize session state for parameters if not exists
    if 'applied_survival_rate' not in st.session_state:
        st.session_state.applied_survival_rate = DEFAULT_SURVIVAL_RATE
        st.session_state.applied_daily_growth = DEFAULT_DAILY_GROWTH
        st.session_state.applied_forecast_days = DEFAULT_FORECAST_DAYS
        st.session_state.applied_doc_abw_lookup = DEFAULT_DOC_ABW_LOOKUP.copy()
    
    # Survival Rate
    survival_rate_input = st.sidebar.slider(
        "Survival Rate (%)",
        min_value=50,
        max_value=100,
        value=int(st.session_state.applied_survival_rate * 100),
        step=1,
        help="Expected survival rate of stocked seeds"
    ) / 100
    
    # Daily Growth
    daily_growth_input = st.sidebar.number_input(
        "Daily Growth (grams/day)",
        min_value=0.1,
        max_value=1.0,
        value=st.session_state.applied_daily_growth,
        step=0.05,
        help="Expected daily weight gain per shrimp"
    )
    
    # Forecast Days
    forecast_days_input = st.sidebar.number_input(
        "Forecast Period (days)",
        min_value=1,
        max_value=30,
        value=st.session_state.applied_forecast_days,
        step=1,
        help="Number of days to forecast ahead"
    )
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### DOC to ABW Lookup Table")
    st.sidebar.markdown("Edit the reference values below:")
    
    # DOC-ABW Lookup Table inputs
    doc_abw_lookup_input = {}
    
    # Create editable inputs for each DOC-ABW pair
    st.sidebar.markdown("**DOC (Days) : ABW (grams)**")
    
    col1, col2 = st.sidebar.columns(2)
    
    # First column (DOC 10-70)
    with col1:
        doc_abw_lookup_input[10] = st.number_input("10 days", value=st.session_state.applied_doc_abw_lookup[10], step=0.1, key="doc10")
        doc_abw_lookup_input[20] = st.number_input("20 days", value=st.session_state.applied_doc_abw_lookup[20], step=0.1, key="doc20")
        doc_abw_lookup_input[30] = st.number_input("30 days", value=st.session_state.applied_doc_abw_lookup[30], step=0.1, key="doc30")
        doc_abw_lookup_input[40] = st.number_input("40 days", value=st.session_state.applied_doc_abw_lookup[40], step=0.1, key="doc40")
        doc_abw_lookup_input[50] = st.number_input("50 days", value=st.session_state.applied_doc_abw_lookup[50], step=0.1, key="doc50")
        doc_abw_lookup_input[60] = st.number_input("60 days", value=st.session_state.applied_doc_abw_lookup[60], step=0.1, key="doc60")
        doc_abw_lookup_input[70] = st.number_input("70 days", value=st.session_state.applied_doc_abw_lookup[70], step=0.1, key="doc70")
    
    # Second column (DOC 80-140)
    with col2:
        doc_abw_lookup_input[80] = st.number_input("80 days", value=st.session_state.applied_doc_abw_lookup[80], step=0.1, key="doc80")
        doc_abw_lookup_input[90] = st.number_input("90 days", value=st.session_state.applied_doc_abw_lookup[90], step=0.1, key="doc90")
        doc_abw_lookup_input[100] = st.number_input("100 days", value=st.session_state.applied_doc_abw_lookup[100], step=0.1, key="doc100")
        doc_abw_lookup_input[110] = st.number_input("110 days", value=st.session_state.applied_doc_abw_lookup[110], step=0.1, key="doc110")
        doc_abw_lookup_input[120] = st.number_input("120 days", value=st.session_state.applied_doc_abw_lookup[120], step=0.1, key="doc120")
        doc_abw_lookup_input[130] = st.number_input("130 days", value=st.session_state.applied_doc_abw_lookup[130], step=0.1, key="doc130")
        doc_abw_lookup_input[140] = st.number_input("140 days", value=st.session_state.applied_doc_abw_lookup[140], step=0.1, key="doc140")
    
    st.sidebar.markdown("---")
    
    # Buttons in two columns
    btn_col1, btn_col2 = st.sidebar.columns(2)
    
    with btn_col1:
        apply_button = st.button("Apply Changes", type="primary", use_container_width=True)
    
    with btn_col2:
        reset_button = st.button("Reset to Defaults", use_container_width=True)
    
    # Handle button clicks
    if apply_button:
        st.session_state.applied_survival_rate = survival_rate_input
        st.session_state.applied_daily_growth = daily_growth_input
        st.session_state.applied_forecast_days = forecast_days_input
        st.session_state.applied_doc_abw_lookup = doc_abw_lookup_input.copy()
        st.rerun()
    
    if reset_button:
        st.session_state.applied_survival_rate = DEFAULT_SURVIVAL_RATE
        st.session_state.applied_daily_growth = DEFAULT_DAILY_GROWTH
        st.session_state.applied_forecast_days = DEFAULT_FORECAST_DAYS
        st.session_state.applied_doc_abw_lookup = DEFAULT_DOC_ABW_LOOKUP.copy()
        st.rerun()
    
    # Use applied parameters for calculations
    survival_rate = st.session_state.applied_survival_rate
    daily_growth = st.session_state.applied_daily_growth
    forecast_days = st.session_state.applied_forecast_days
    doc_abw_lookup = st.session_state.applied_doc_abw_lookup
    
    # === MAIN CONTENT ===
    # Header
    st.markdown('<div class="main-header">Count 366 - Vannamei Biomass Prediction</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="sub-header">{forecast_days}-Day harvest forecast based on current pond data | Generated: {datetime.now().strftime("%B %d, %Y at %H:%M")}</div>', unsafe_allow_html=True)
    
    # Description
    st.markdown("""
    This dashboard predicts the estimated biomass for L. Vannamei ponds in the Count 366 system. 
    Predictions are based on current pond conditions and key assumptions including survival rate, 
    daily growth rate, and days of culture.
    
    **Default values used:** Survival Rate = 80%, Daily Growth = 0.25 g/day, Forecast Period = 10 days
    
    You can customize these parameters and the DOC-ABW reference table using the sidebar (left panel). 
    Adjust the values and click **"Apply Changes"** to recalculate predictions with your custom parameters.
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
        lambda row: calculate_pond_biomass(row, survival_rate, doc_abw_lookup), axis=1
    )
    
    # Filter successful predictions
    valid_ponds = df[df["predictionStatus"] == "Success"].copy()
    
    # Calculate forecast
    forecast_df = calculate_10_day_forecast(valid_ponds, survival_rate, daily_growth, forecast_days)
    
    # === SECTION 1: METHODOLOGY ===
    st.markdown("## Methodology")
    
    with st.expander("View Assumptions & Calculation Methods", expanded=False):
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.markdown('<div class="methodology-box">', unsafe_allow_html=True)
            st.markdown("### Key Assumptions")
            st.markdown(f"""
            - **Survival Rate:** {survival_rate * 100:.0f}% ({survival_rate})
            - **Daily Growth Rate:** {daily_growth} grams/day
            - **Forecast Period:** {forecast_days} days
            
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
            lookup_df = pd.DataFrame(list(doc_abw_lookup.items()), columns=['DOC (Days)', 'ABW (grams)'])
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
            label="Total Vannamei Ponds",
            value="33"
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
        st.markdown(f"#### Estimated Biomass (After {forecast_days} Days)")
        st.markdown(f'<div class="big-metric">{forecast_total_biomass:,.0f} KG</div>', unsafe_allow_html=True)
        st.markdown(f'<p style="color: #2ca02c; font-size: 1.5rem; font-weight: bold;">↑ +{growth:,.0f} KG (+{growth_pct:.1f}%)</p>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Comparison chart
    comparison_data = pd.DataFrame({
        'Period': ['Current', f'After {forecast_days} Days'],
        'Biomass (KG)': [current_total_biomass, forecast_total_biomass]
    })
    
    fig_comparison = px.bar(
        comparison_data,
        x='Period',
        y='Biomass (KG)',
        text='Biomass (KG)',
        color='Period',
        color_discrete_map={'Current': '#1f77b4', f'After {forecast_days} Days': '#2ca02c'}
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
    st.markdown(f"## Shrimp Count per KG Distribution (After {forecast_days} Days)")
    
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
        name=f'{forecast_days}-Day Forecast',
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
    display_grouped.columns = ['Count/KG', 'Number of Ponds', 'Current Biomass (KG)', f'{forecast_days}-Day Forecast (KG)']
    st.dataframe(display_grouped, use_container_width=True, hide_index=True)
    
    st.markdown("---")
    
    # === SECTION 4: TOP 10 PONDS ===
    st.markdown(f"## Top 10 Ponds by Estimated Harvest (After {forecast_days} Days)")
    
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
        xaxis_title=f"Estimated Harvest after {forecast_days} Days (KG)",
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
    st.markdown(f"## Detailed {forecast_days}-Day Forecast by Pond")
    
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
        'Current ABW (g)', 'Current Biomass (KG)', f'Day-{forecast_days} DOC', f'Day-{forecast_days} ABW (g)',
        f'Day-{forecast_days} Forecast (KG)', 'Current Count/KG', f'Day-{forecast_days} Count/KG'
    ]
    
    st.dataframe(display_forecast, use_container_width=True, height=500)

if __name__ == "__main__":
    main()
