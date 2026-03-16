import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from keepa_api import fetch_products, get_summary, DOMAINS
 
# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Amazon Price Tracker",
    page_icon="📦",
    layout="wide",
)
 
# ── Header ───────────────────────────────────────────────────────────────────
st.title("📦 Amazon Price Tracker")
st.caption("Multi-marketplace price history dashboard powered by Keepa API")
st.divider()
 
# ── Sidebar — inputs ─────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")
 
    marketplace = st.selectbox(
        "Marketplace",
        options=list(DOMAINS.keys()),
        index=0,
    )
 
    asins_input = st.text_area(
        "ASINs to track (one per line)",
        placeholder="B08N5WRWNW\nB07XJ8C8F5\nB09G9HD6PD",
        height=160,
    )
 
    days_range = st.slider(
        "Price history (days)",
        min_value=7,
        max_value=180,
        value=90,
        step=7,
    )
 
    price_type = st.multiselect(
        "Price types to display",
        options=["amazon_price", "buy_box_price", "new_price"],
        default=["buy_box_price", "amazon_price"],
        format_func=lambda x: {
            "amazon_price":  "Amazon price",
            "buy_box_price": "Buy Box price",
            "new_price":     "New (3rd party)",
        }[x],
    )
 
    fetch_btn = st.button("🔍 Fetch prices", type="primary", use_container_width=True)
 
    st.divider()
    st.caption("Built with Keepa API · Streamlit · Plotly")
 
# ── Main area ────────────────────────────────────────────────────────────────
if not fetch_btn:
    st.info("👈 Enter one or more ASINs in the sidebar and click **Fetch prices** to get started.")
    st.stop()
 
asins = [a.strip().upper() for a in asins_input.strip().splitlines() if a.strip()]
if not asins:
    st.warning("Please enter at least one ASIN.")
    st.stop()
 
# ── Fetch ────────────────────────────────────────────────────────────────────
with st.spinner(f"Fetching data for {len(asins)} product(s) on {marketplace}…"):
    try:
        df = fetch_products(asins, marketplace)
    except Exception as e:
        st.error(f"API error: {e}")
        st.stop()
 
if df.empty:
    st.error("No data returned. Check your ASINs or API key.")
    st.stop()
 
# Filter by date range
cutoff = pd.Timestamp.now() - pd.Timedelta(days=days_range)
df = df[df["date"] >= cutoff]
 
# ── Summary cards ────────────────────────────────────────────────────────────
summary_df = get_summary(df)
 
st.subheader("📊 Summary")
cols = st.columns(len(asins) if len(asins) <= 4 else 4)
 
for i, row in summary_df.iterrows():
    col = cols[i % len(cols)]
    with col:
        delta_color = "inverse" if row["30d change %"] > 0 else "normal"
        st.metric(
            label=row["Product"],
            value=f"£/€ {row['Current (£/€)']}",
            delta=f"{row['30d change %']}% vs 30d avg",
            delta_color=delta_color,
        )
        st.caption(row["Alert"])
 
st.divider()
 
# ── Price history chart ───────────────────────────────────────────────────────
st.subheader("📈 Price history")
 
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
 
products = df["asin"].unique()
tab_labels = [
    f"{row['Product'][:30]}… ({row['ASIN']})" if len(row["Product"]) > 30
    else f"{row['Product']} ({row['ASIN']})"
    for _, row in summary_df.iterrows()
]
 
tabs = st.tabs(tab_labels if tab_labels else ["Product"])
 
for i, (tab, asin) in enumerate(zip(tabs, products)):
    with tab:
        product_df = df[df["asin"] == asin]
        title = product_df["title"].iloc[0]
 
        fig = go.Figure()
        for pt in price_type:
            series = product_df[["date", pt]].dropna(subset=[pt])
            if series.empty:
                continue
            fig.add_trace(go.Scatter(
                x=series["date"],
                y=series[pt],
                name=LABEL_MAP.get(pt, pt),
                mode="lines",
                line=dict(color=COLOR_MAP.get(pt, "#888"), width=2),
                hovertemplate="%{y:.2f} £/€<br>%{x|%d %b %Y}<extra>" + LABEL_MAP.get(pt, pt) + "</extra>",
            ))
 
        fig.update_layout(
            title=title,
            xaxis_title="Date",
            yaxis_title="Price (£/€)",
            hovermode="x unified",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=400,
            margin=dict(l=0, r=0, t=50, b=0),
        )
        st.plotly_chart(fig, use_container_width=True)
 
        # Sales rank sub-chart
        # Sales rank sub-chart
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
                text="Best rank",
                xref="paper", yref="paper",
                x=0.01, y=0.95,
                showarrow=False,
                font=dict(size=11, color="green")
            )
            fig_sr.update_layout(
                margin=dict(l=0, r=0, t=40, b=0),
                yaxis=dict(tickformat=",")
            )
            st.plotly_chart(fig_sr, use_container_width=True)
 
st.divider()
 
# ── Full data table ───────────────────────────────────────────────────────────
st.subheader("📋 Summary table")
st.dataframe(
    summary_df.style.applymap(
        lambda v: "color: green" if v == "🔻 DROP"
        else ("color: red" if v == "🔺 UP" else ""),
        subset=["Alert"]
    ),
    use_container_width=True,
    hide_index=True,
)
 
# Download button
csv = summary_df.to_csv(index=False).encode("utf-8")
st.download_button(
    label="⬇️ Download summary CSV",
    data=csv,
    file_name=f"price_summary_{marketplace.split()[0]}.csv",
    mime="text/csv",
)
