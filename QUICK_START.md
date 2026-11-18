# 🚀 Quick Start Guide

## Running the Dashboard (3 Simple Steps!)

### Step 1: Open Terminal
Navigate to the project folder:
```bash
cd /Users/count366/Documents/Development/HarvestPrediction
```

### Step 2: Run the Dashboard
Simply execute:
```bash
./run_dashboard.sh
```

Or manually:
```bash
source .venv/bin/activate
streamlit run dashboard_app.py
```

### Step 3: View in Browser
The dashboard will automatically open at: **http://localhost:8501**

---

## 📤 Sharing with Your Manager

### Option A: Streamlit Cloud (Recommended - FREE)

1. **Create GitHub Account** (if you don't have one)
   - Go to github.com and sign up

2. **Create New Repository**
   ```bash
   cd /Users/count366/Documents/Development/HarvestPrediction
   git init
   git add dashboard_app.py requirements.txt runningPonds.csv README.md
   git commit -m "Add harvest prediction dashboard"
   ```

3. **Push to GitHub**
   - Create a new repository on github.com
   - Follow GitHub's instructions to push your code

4. **Deploy on Streamlit Cloud**
   - Go to [share.streamlit.io](https://share.streamlit.io)
   - Sign in with GitHub
   - Click "New app"
   - Select your repository
   - Main file: `dashboard_app.py`
   - Click "Deploy"
   - **Share the generated URL with your manager!**

### Option B: Share on Local Network (Same Office)

1. Find your IP address:
   ```bash
   ipconfig getifaddr en0
   ```

2. Run dashboard with network access:
   ```bash
   source .venv/bin/activate
   streamlit run dashboard_app.py --server.address=0.0.0.0
   ```

3. Share this URL with your manager:
   ```
   http://YOUR_IP_ADDRESS:8501
   ```

---

## 🎥 What Your Manager Will See

✅ **Overview Dashboard with Key Metrics**
- Total ponds being monitored
- Success rate of predictions
- Total biomass estimates
- Total seed count

✅ **Interactive Charts**
- Prediction status breakdown
- Pond status distribution
- Top performing ponds
- Growth analysis (DOC vs ABW)
- Seed variety distribution

✅ **Detailed Data Table**
- Complete pond information
- Sortable and filterable
- Download as CSV option

✅ **Professional Look**
- Clean, modern interface
- Color-coded metrics
- Mobile-friendly (works on phones/tablets)

---

## 📝 Updating Data

To refresh with new data:

1. **Replace the CSV file**:
   ```bash
   cp /path/to/new/runningPonds.csv /Users/count366/Documents/Development/HarvestPrediction/
   ```

2. **Refresh the browser** - Streamlit auto-updates!

Or use the **Upload CSV** feature in the dashboard sidebar.

---

## ⚙️ Customization

### Change Prediction Parameters

Edit `dashboard_app.py` (lines 29-31):

```python
SURVIVAL_RATE = 0.80    # Change survival rate
DAILY_GROWTH = 0.25     # Change growth rate
FORECAST_DAYS = 10      # Change forecast period
```

### Change Colors/Theme

Edit the CSS in `dashboard_app.py` (lines 17-30) or use Streamlit's theme settings.

---

## 🐛 Troubleshooting

### Dashboard won't start
```bash
# Reinstall packages
source .venv/bin/activate
pip install --upgrade streamlit pandas plotly numpy
```

### Port 8501 already in use
```bash
streamlit run dashboard_app.py --server.port=8502
```

### CSV file not found
Make sure `runningPonds.csv` is in the same folder as `dashboard_app.py`

---

## 💡 Pro Tips

1. **Bookmark the URL** for quick access
2. **Use filters** in the sidebar to focus on specific ponds
3. **Download data** for offline analysis using the download button
4. **Share screenshots** for presentations (charts are high-quality)
5. **Update automatically** - new data appears on page refresh

---

## 📞 Need Help?

- Check `README.md` for detailed documentation
- Streamlit docs: https://docs.streamlit.io
- Python issues: Check your Python version with `python3 --version`

---

**Happy Analyzing! 🦐📊**
