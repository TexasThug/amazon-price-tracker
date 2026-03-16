import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import json
import os
from datetime import datetime, timedelta
from keepa_api import fetch_products, get_summary, get_alerts, load_asins_from_excel, DOMAINS, MARKETPLACE_LABELS

st.set_page_config(
    page_title="Amazon Price Tracker — Edgard & Cooper",
    page_icon="📦",
    layout="wide",
)

# ── Cache helpers ─────────────────────────────────────────────────────────────
CACHE_FILE = "price_cache.json"
CACHE_TTL_HOURS = 24

def load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    with open(CACHE_FILE, "r") as f:
        return json.load(f)

def save_cache(cache):
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

def cache_key(asins, country):
    return f"{country}__{'_'.join(sorted(asins))}"

def get_cached_df(asins, country):
    cache = load_cache()
    key = cache_key(asins, country)
    if key not in cache:
        return None
    entry = cache[key]
    cached_at = datetime.fromisoformat(entry["cached_at"])
    if datetime.now() - cached_at > timedelta(hours=CACHE_TTL_HOURS):
        return None
    return pd.read_json(entry["data"])

def set_cached_df(asins, country, df):
    cache = load_cache()
    key = cache_key(asins, country)
    cache[key] = {
        "cached_at": datetime.now().isoformat(),
        "data": df.to_json()
    }
    save_cache(cache)

# ── Header ────────────────────────────────────────────────────────────────────
st.title("📦 Amazon Price Tracker")
st.caption("Edgard & Cooper — Multi-marketplace monitoring dashboard")
st.divider()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")

    mode = st.radio(
        "Input mode",
        options=["📂 Upload listing Excel", "✏️ Manual ASINs"],
        index=0,
    )

    country = st.selectbox(
        "Country",
        options=list(DOMAINS.keys()),
        index=0,
    )

    asins_list = []
    sku_map = {}

    if mode == "📂 Upload listing Excel":
        uploaded_file = st.file_uploader(
            "Upload your listing file (.xlsx)",
            type=["xlsx"],
        )
        if uploaded_file:
            try:
                listing_df = load_asins_from_excel(uploaded_file, country)
                asins_list = listing_df["asin"].tolist()
                sku_map = dict(zip(listing_df["asin"], listing_df["sku"]))
                st.success(f"✅ {len(asins_list)} ASINs loaded for {country}")
                with st.expander("Preview ASINs"):
                    st.dataframe(listing_df[["asin", "sku", "availability"]], hide_index=True)
            except Exception as e:
                st.error(f"Error reading file: {e}")
    else:
        asins_input = st.text_area(
            "ASINs (one per line)",
            placeholder="B08N5WRWNW\nB07XJ8C8F5",
            height=160,
        )
        asins_list = [a.strip().upper() for a in asins_input.strip().splitlines() if a.strip()]

    days_range = st.slider("Price history (days)", 7, 180, 90, 7)

    price_type = st.multiselect(
        "Price types",
        options=["amazon_price", "buy_box_price", "new_price"],
        default=["buy_box_price", "amazon_price"],
        format_func=lambda x: {
            "amazon_price":  "Amazon price",
            "buy_box_price": "Buy Box price",
            "new_price":     "New (3rd party)",
        }[x],
    )

    col1, col2 = st.columns(2)
    with col1:
        fetch_btn = st.button("🔍 Fetch", type="primary", use_container_width=True)
    with col2:
        force_refresh = st.button("🔄 Refresh", use_container_width=True)

    st.divider()
    st.caption("Built with Keepa API · Streamlit · Plotly")

# ── Main ──────────────────────────────────────────────────────────────────────
if not fetch_btn and not force_refresh:
    st.info("👈 Upload your listing Excel or enter ASINs manually, then click **Fetch**.")
    st.stop()

if not asins_list:
    st.warning("No ASINs to fetch. Upload a file or enter ASINs manually.")
    st.stop()

# Batch size — Keepa recommends max 100 per request
BATCH_SIZE = 20
cached = None if force_refresh else get_cached_df(asins_list, country)

if cached is not None:
    df = cached
    st.success(f"✅ Loaded from cache — last updated less than {CACHE_TTL_HOURS}h ago. Click 🔄 Refresh to force reload.")
else:
    progress = st.progress(0, text=f"Fetching {len(asins_list)} products...")
    all_dfs = []
    batches = [asins_list[i:i+BATCH_SIZE] for i in range(0, len(asins_list), BATCH_SIZE)]

    for i, batch in enumerate(batches):
        try:
            batch_df = fetch_products(batch, country)
            all_dfs.append(batch_df)
        except Exception as e:
            st.warning(f"Batch {i+1} error: {e}")
        progress.progress((i+1)/len(batches), text=f"Fetching batch {i+1}/{len(batches)}...")

    progress.empty()

    if not all_dfs:
        st.error("No data returned. Check your ASINs or API key.")
        st.stop()

    df = pd.concat(all_dfs, ignore_index=True)
    set_cached_df(asins_list, country, df)

if df.empty:
    st.error("No data returned.")
    st.stop()

cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_range)
df = df[df["date"] >= cutoff]

summary_df = get_summary(df)
alerts_df  = get_alerts(summary_df)

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_alerts, tab_overview, tab_detail = st.tabs([
    f"🚨 Alerts ({len(alerts_df)})",
    "📊 Overview",
    "📈 Product detail",
])

# ── ALERTS TAB ────────────────────────────────────────────────────────────────
with tab_alerts:
    if alerts_df.empty:
        st.success("✅ All products are stable — no alerts!")
    else:
        oos     = alerts_df[alerts_df["Alert"] == "🔴 OOS"]
        drops   = alerts_df[alerts_df["Alert"] == "🟡 PRICE DROP"]
        ups     = alerts_df[alerts_df["Alert"] == "🔺 PRICE UP"]
        nodata  = alerts_df[alerts_df["Alert"] == "⚫ NO DATA"]

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🔴 Out of stock",  len(oos))
        col2.metric("🟡 Price drops",   len(drops))
        col3.metric("🔺 Price increases", len(ups))
        col4.metric("⚫ No data",        len(nodata))

        st.divider()

        if not oos.empty:
            st.subheader("🔴 Out of stock")
            st.dataframe(oos[["ASIN", "Product", "Alert"]], hide_index=True, use_container_width=True)

        if not drops.empty:
            st.subheader("🟡 Significant price drops (>10%)")
            st.dataframe(
                drops[["ASIN", "Product", "Current (£/€)", "Avg (£/€)", "30d change %", "Alert"]],
                hide_index=True, use_container_width=True
            )

        if not ups.empty:
            st.subheader("🔺 Significant price increases (>10%)")
            st.dataframe(
                ups[["ASIN", "Product", "Current (£/€)", "Avg (£/€)", "30d change %", "Alert"]],
                hide_index=True, use_container_width=True
            )

        csv = alerts_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Download alerts CSV", csv, f"alerts_{country}.csv", "text/csv")

# ── OVERVIEW TAB ──────────────────────────────────────────────────────────────
with tab_overview:
    st.subheader(f"All products — {country} ({len(summary_df)} total)")

    display_df = summary_df.copy()
    for col in ["Current (£/€)", "Min (£/€)", "Max (£/€)", "Avg (£/€)"]:
        display_df[col] = display_df[col].apply(
            lambda x: f"£/€ {x:.2f}" if isinstance(x, float) else x
        )
    display_df["30d change %"] = display_df["30d change %"].apply(lambda x: f"{x:+.1f}%")

    st.dataframe(display_df.drop(columns=["OOS"]), hide_index=True, use_container_width=True)

    csv = summary_df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Download full CSV", csv, f"summary_{country}.csv", "text/csv")

# ── DETAIL TAB ────────────────────────────────────────────────────────────────
with tab_detail:
    COLOR_MAP = {
        "amazon_price":  "#FF9900",
        "buy_box_price": "#146EB4",
        "new_price":     "#2ECC71",
    }
    LABEL_MAP = {
        "amazon_price":  "Amazon price",
        "buy_box_price": "Buy Box price",
        "new_price":     "New (3rd party)",
    }

    selected_asin = st.selectbox(
        "Select a product",
        options=summary_df["ASIN"].tolist(),
        format_func=lambda x: f"{x} — {summary_df[summary_df['ASIN']==x]['Product'].values[0]}"
    )

    if selected_asin:
        product_df = df[df["asin"] == selected_asin]
        title = product_df["title"].iloc[0]

        row = summary_df[summary_df["ASIN"] == selected_asin].iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Current", f"£/€ {row['Current (£/€)']:.2f}" if isinstance(row['Current (£/€)'], float) else "N/A")
        c2.metric("Min", f"£/€ {row['Min (£/€)']:.2f}" if isinstance(row['Min (£/€)'], float) else "N/A")
        c3.metric("Max", f"£/€ {row['Max (£/€)']:.2f}" if isinstance(row['Max (£/€)'], float) else "N/A")
        c4.metric("30d change", f"{row['30d change %']:+.1f}%" if isinstance(row['30d change %'], float) else "N/A")

        fig = go.Figure()
        for pt in price_type:
            series = product_df[["date", pt]].dropna(subset=[pt])
            if series.empty:
                continue
            fig.add_trace(go.Scatter(
                x=series["date"], y=series[pt],
                name=LABEL_MAP.get(pt, pt),
                mode="lines",
                line=dict(color=COLOR_MAP.get(pt, "#888"), width=2),
                hovertemplate="%{y:.2f} £/€<br>%{x|%d %b %Y}<extra>" + LABEL_MAP.get(pt, pt) + "</extra>",
            ))

        fig.update_layout(
            title=title,
            xaxis_title="Date", yaxis_title="Price (£/€)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=400, margin=dict(l=0, r=0, t=50, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)

        sr = product_df[["date", "sales_rank"]].dropna(subset=["sales_rank"])
        if not sr.empty:
            fig_sr = px.line(
                sr, x="date", y="sales_rank",
                title="Sales Rank (BSR) — lower is better",
                color_discrete_sequence=["#FF9900"],
                height=220,
            )
            fig_sr.update_yaxes(autorange="reversed", title="Rank (lower = better)")
            fig_sr.update_xaxes(title="Date")
            fig_sr.add_annotation(
                text="Best rank ↑", xref="paper", yref="paper",
                x=0.01, y=0.05, showarrow=False,
                font=dict(size=11, color="green")
            )
            fig_sr.update_layout(margin=dict(l=0, r=0, t=40, b=0), yaxis=dict(tickformat=","))
            st.plotly_chart(fig_sr, use_container_width=True)
