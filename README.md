# 🦐 Aquaculture Harvest Prediction Dashboard

A professional Streamlit dashboard for visualizing and analyzing aquaculture pond harvest predictions.

## Features

- 📊 **Real-time Metrics**: Total ponds, successful predictions, biomass, and seed counts
- 📈 **Interactive Charts**: 
  - Prediction status distribution
  - Pond status breakdown
  - Biomass analysis by pond
  - DOC vs ABW correlation
  - Seed variety distribution
- 🔍 **Advanced Filtering**: Filter by pond status and prediction status
- 📋 **Detailed Data Table**: View and download complete pond information
- 📥 **Export Functionality**: Download filtered data as CSV

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Or install individually:
```bash
pip install streamlit pandas numpy plotly
```

### 2. Run the Dashboard

```bash
streamlit run dashboard_app.py
```

The dashboard will open automatically in your browser at `http://localhost:8501`

### 3. Upload Your Data

- The dashboard automatically loads `runningPonds.csv` if present
- You can also upload a custom CSV file using the sidebar

## Dashboard Sections

### 📈 Key Metrics
- **Total Ponds**: Number of active ponds being tracked
- **Successful Predictions**: Ponds with valid DOC within reference range
- **Total Biomass**: Current estimated biomass in kilograms
- **Total Seeds**: Aggregate seed count across all ponds

### 🎯 Prediction Status
Shows distribution of prediction outcomes:
- Success
- DOC outside reference range
- Invalid data

### 📊 Biomass Analysis
- Top 15 ponds by current biomass
- Visual comparison of harvest potential

### 📉 DOC vs ABW Correlation
Interactive scatter plot showing the relationship between Days of Culture and Average Body Weight

### 🌱 Seed Variety Analysis
Breakdown of seed varieties used across all ponds

## Data Requirements

Your CSV file should contain these columns:
- `farmId`: Farm identifier
- `name`: Pond name
- `area`: Pond area
- `units`: Area units (e.g., Acres)
- `totalSeed`: Number of seeds stocked
- `cultureType`: Type of culture (e.g., L. Vannamei)
- `daysOfCulture`: Initial days of culture
- `pondStatus`: Current pond status
- `createdOn`: Installation date (milliseconds timestamp)
- `pondId`: Unique pond identifier
- `seedVariety`: Seed variety name

## Sharing Options

### Option 1: Streamlit Cloud (FREE) ⭐

1. **Push to GitHub**:
   ```bash
   git init
   git add dashboard_app.py requirements.txt runningPonds.csv
   git commit -m "Add harvest prediction dashboard"
   git push origin main
   ```

2. **Deploy to Streamlit Cloud**:
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub
   - Click "New app"
   - Select your repository
   - Set main file: `dashboard_app.py`
   - Click "Deploy"

3. **Share the URL** with your manager!

### Option 2: Local Network

Run on your machine and share with colleagues on the same network:

```bash
streamlit run dashboard_app.py --server.address=0.0.0.0
```

Then share: `http://YOUR_IP:8501`

### Option 3: Email as HTML

To generate a static report:
```bash
# Install additional package
pip install streamlit-book

# Generate static HTML (view-only)
```

## Configuration

### Prediction Parameters

Edit these in `dashboard_app.py`:

```python
SURVIVAL_RATE = 0.80      # 80% survival rate
DAILY_GROWTH = 0.25       # Grams per day
FORECAST_DAYS = 10        # Days to forecast
```

### DOC to ABW Lookup

The dashboard uses a reference table to estimate Average Body Weight based on Days of Culture:

| DOC | ABW (g) |
|-----|---------|
| 10  | 0.40    |
| 20  | 1.60    |
| ...  | ...    |
| 140 | 37.50   |

## Troubleshooting

### Port Already in Use
```bash
streamlit run dashboard_app.py --server.port=8502
```

### File Not Found
Make sure `runningPonds.csv` is in the same directory as `dashboard_app.py`, or upload via the sidebar.

### Missing Dependencies
```bash
pip install --upgrade streamlit pandas plotly numpy
```

## Support

For issues or questions, contact your development team.

---

**Last Updated**: November 2026
**Version**: 1.0.0
