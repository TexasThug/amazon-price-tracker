import keepa
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

DOMAINS = {
    "Amazon.co.uk (UK)": "GB",
    "Amazon.de (DE)":    "DE",
    "Amazon.fr (FR)":    "FR",
    "Amazon.it (IT)":    "IT",
    "Amazon.es (ES)":    "ES",
}

def get_api():
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        raise ValueError("KEEPA_API_KEY not found in .env file")
    return keepa.Keepa(api_key)

def keepa_time_to_datetime(keepa_minutes):
    KEEPA_EPOCH = datetime(2011, 1, 1)
    return [KEEPA_EPOCH + timedelta(minutes=int(m)) for m in keepa_minutes]

def extract_series(series_data, value_divisor=100):
    if not series_data or len(series_data) < 2:
        return pd.Series(dtype=float)
    times  = series_data[0::2]
    values = series_data[1::2]
    min_len = min(len(times), len(values))
    times   = times[:min_len]
    values  = values[:min_len]
    dates   = keepa_time_to_datetime(times)
    s = pd.Series(
        [v / value_divisor if v > 0 else None for v in values],
        index=dates
    )
    # Remove duplicates and sort index
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s

def fetch_products(asins: list, domain_name: str) -> pd.DataFrame:
    api = get_api()
    domain_id = DOMAINS[domain_name]
    products = api.query(asins, domain=domain_id, history=True, buybox=True)

    rows = []
    for product in products:
        asin  = product.get("asin", "N/A")
        title = product.get("title", "Unknown product")
        csv   = product.get("csv") or []

        def get_csv(idx):
            try:
                return csv[idx]
            except IndexError:
                return None

        amazon_prices = extract_series(get_csv(0))
        new_prices    = extract_series(get_csv(1))
        buybox_prices = extract_series(get_csv(18))
        sales_rank    = extract_series(get_csv(3), value_divisor=1)

        all_dates = pd.date_range(
            start=datetime.now() - timedelta(days=180),
            end=datetime.now(),
            freq="D"
        )
        df = pd.DataFrame(index=all_dates)
        df.index.name = "date"

        for col, series in [
            ("amazon_price",  amazon_prices),
            ("new_price",     new_prices),
            ("buy_box_price", buybox_prices),
            ("sales_rank",    sales_rank),
        ]:
            if not series.empty:
                df[col] = series.reindex(df.index, method="ffill")
            else:
                df[col] = None

        df = df.reset_index()
        df["asin"]   = asin
        df["title"]  = title[:60] + "..." if len(title) > 60 else title
        df["domain"] = domain_name
        rows.append(df)

    if not rows:
        return pd.DataFrame()

    result = pd.concat(rows, ignore_index=True)
    result["date"] = pd.to_datetime(result["date"])
    return result


def get_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    summary = []
    for asin, group in df.groupby("asin"):
        title  = group["title"].iloc[0]
        domain = group["domain"].iloc[0]

        bb = group["buy_box_price"].dropna()
        am = group["amazon_price"].dropna()
        price_series = bb if not bb.empty else am

        if price_series.empty:
            continue

        current  = price_series.iloc[-1]
        min_p    = price_series.min()
        max_p    = price_series.max()
        avg_p    = round(price_series.mean(), 2)
        last_30  = price_series.iloc[-30:]
        avg_30   = last_30.mean() if not last_30.empty else current
        drop_pct = round((avg_30 - current) / avg_30 * 100, 1) if avg_30 else 0

        summary.append({
            "ASIN":          asin,
            "Product":       title,
            "Marketplace":   domain,
            "Current (£/€)": round(current, 2),
            "Min (£/€)":     round(min_p, 2),
            "Max (£/€)":     round(max_p, 2),
            "Avg (£/€)":     avg_p,
            "30d change %":  drop_pct,
            "Alert":         "🔻 DROP" if drop_pct > 5 else ("🔺 UP" if drop_pct < -5 else "➡ STABLE"),
        })

    return pd.DataFrame(summary)
