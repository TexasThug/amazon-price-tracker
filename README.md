# 📦 Amazon Price Tracker

> Multi-marketplace Amazon price monitoring dashboard — built for Edgard & Cooper

![Python](https://img.shields.io/badge/Python-3.11+-blue?style=flat-square&logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32-red?style=flat-square&logo=streamlit)
![Keepa](https://img.shields.io/badge/Keepa-API-orange?style=flat-square)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## 🎯 What it does

A real-time price monitoring dashboard that tracks Amazon product prices across 5 European marketplaces (UK, DE, FR, ES, IT). Built to replace manual ASIN-by-ASIN checking with an automated alert system.

**Key capabilities:**
- 🔴 **OOS detection** — flags out-of-stock products instantly
- 🟡 **Price drop alerts** — notifies when prices fall more than 10% vs 30-day average
- 📈 **Buy Box tracking** — monitors who holds the Buy Box over time
- 📊 **Sales Rank (BSR)** — correlates price movements with sales performance
- 📂 **Excel import** — load your full product catalogue in one click
- 💾 **24h cache** — avoids redundant API calls, preserves Keepa tokens

---

## 🖥️ Demo

> Live app: [amazon-price-tracker.streamlit.app](https://amazon-price-tracker-t5hpoozdwphudwdr4t3stt.streamlit.app)

---

## 🏗️ Architecture

```
listing.xlsx (product catalogue)
        ↓
    app.py (Streamlit UI)
        ↓
  keepa_api.py (data layer)
        ↓
   Keepa API → price history, BSR, Buy Box
        ↓
  price_cache.json (24h local cache)
```

---

## 🚀 Getting started

### 1. Clone the repo

```bash
git clone https://github.com/TexasThug/amazon-price-tracker.git
cd amazon-price-tracker
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Set up your API key

Create a `.env` file at the root:

```
KEEPA_API_KEY=your_keepa_api_key_here
```

> Get your Keepa API key at [keepa.com/#!api](https://keepa.com/#!api)

### 4. Run the app

```bash
streamlit run app.py
```

Open your browser at `http://localhost:8501`

---

## 📁 Project structure

```
amazon-price-tracker/
├── app.py              # Streamlit dashboard (UI + tabs)
├── keepa_api.py        # Keepa API wrapper + data processing
├── requirements.txt    # Python dependencies
├── .env                # API key (never committed)
├── .gitignore
└── README.md
```

---

## 📊 Dashboard tabs

| Tab | Description |
|-----|-------------|
| 🚨 **Alerts** | Products needing attention — OOS, price drops, price increases |
| 📊 **Overview** | Full product table with current price, min/max, 30d trend |
| 📈 **Product detail** | Price history chart + BSR chart for any selected product |

---

## ⚙️ How to use

**Option 1 — Upload your listing Excel:**
1. Upload your product catalogue (`.xlsx`) with one tab per country
2. Select the target marketplace
3. Click **Fetch** — the app loads all ASINs automatically

**Option 2 — Manual ASINs:**
1. Switch to "Manual ASINs" mode in the sidebar
2. Paste ASINs one per line
3. Click **Fetch**

> **Tip:** Use **Refresh** to force a new API call, bypassing the 24h cache.

---

## 🛠️ Tech stack

| Tool | Role |
|------|------|
| **Python 3.11+** | Core language |
| **Keepa API** | Amazon price history data |
| **pandas** | Data manipulation |
| **Streamlit** | Dashboard UI |
| **Plotly** | Interactive charts |
| **openpyxl / calamine** | Excel file parsing |
| **python-dotenv** | Environment variables |

---

## 🗺️ Roadmap

- [ ] FastAPI backend for n8n integration
- [ ] Automated daily alerts via Slack/email
- [ ] Price/BSR correlation analysis
- [ ] Anomaly detection with Isolation Forest
- [ ] Multi-country comparison view

---

## 👤 Author

**Joffray DeAlberto** — [@TexasThug](https://github.com/TexasThug)

Data Analyst · E-commerce & Amazon · MSc AI/Data & Business

---

> Built with 🐍 Python · Powered by [Keepa API](https://keepa.com)
