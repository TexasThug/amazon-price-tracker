import keepa
import pandas as pd
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

DOMAINS = {
    "UK": "GB",
    "DE": "DE",
    "FR": "FR",
    "IT": "IT",
    "ES": "ES",
}

MARKETPLACE_LABELS = {
    "UK": "Amazon.co.uk (UK)",
    "DE": "Amazon.de (DE)",
    "FR": "Amazon.fr (FR)",
    "IT": "Amazon.it (IT)",
    "ES": "Amazon.es (ES)",
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
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s

def load_asins_from_excel(file, country: str) -> pd.DataFrame:
    try:
        df = pd.read_excel(file, sheet_name=country, header=1, engine='calamine')
    except Exception as e:
        raise ValueError(f"Could not read sheet '{country}': {e}")

    # Normalize column names to uppercase
    df.columns = [str(c).strip().upper() for c in df.columns]

    asin_col  = next((c for c in df.columns if "ASIN" in c and "AMAZON" not in c), None)
    sku_col   = next((c for c in df.columns if "SKU" in c), None)
    avail_col = next((c for c in df.columns if "AVAIL" in c), None)

    if not asin_col:
        raise ValueError(f"No ASIN column found in sheet '{country}'")

    result = pd.DataFrame()
    result["asin"]         = df[asin_col].astype(str).str.strip()
    result["sku"]          = df[sku_col].astype(str).str.strip() if sku_col else "N/A"
    result["availability"] = df[avail_col].astype(str).str.strip() if avail_col else "N/A"

    result = result[result["asin"].str.match(r'^[A-Z0-9]{10}$')]
    result = result.drop_duplicates(subset="asin").reset_index(drop=True)

    return result


def fetch_products(asins: list, country: str) -> pd.DataFrame:
    api = get_api()
    domain_id = DOMAINS[country]
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

        # OOS detection — check if stock available (csv index 11)
        stock_data = get_csv(11)
        is_oos = False
        if stock_data and len(stock_data) >= 2:
            last_stock = stock_data[-1]
            is_oos = last_stock == 0
        elif buybox_prices.empty and amazon_prices.empty:
            is_oos = True

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
        df["asin"]    = asin
        df["title"]   = title[:60] + "..." if len(title) > 60 else title
        df["country"] = country
        df["is_oos"]  = is_oos
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
        title   = group["title"].iloc[0]
        country = group["country"].iloc[0]
        is_oos  = group["is_oos"].iloc[0]

        bb = group["buy_box_price"].dropna()
        am = group["amazon_price"].dropna()
        price_series = bb if not bb.empty else am

        if price_series.empty:
            current = None
            min_p = max_p = avg_p = drop_pct = None
            alert = "⚫ NO DATA"
        else:
            current  = price_series.iloc[-1]
            min_p    = price_series.min()
            max_p    = price_series.max()
            avg_p    = round(price_series.mean(), 2)
            last_30  = price_series.iloc[-30:]
            avg_30   = last_30.mean() if not last_30.empty else current
            drop_pct = round((avg_30 - current) / avg_30 * 100, 1) if avg_30 else 0

            if is_oos:
                alert = "🔴 OOS"
            elif drop_pct > 10:
                alert = "🟡 PRICE DROP"
            elif drop_pct < -10:
                alert = "🔺 PRICE UP"
            else:
                alert = "🟢 STABLE"

        summary.append({
            "ASIN":          asin,
            "Product":       title,
            "Country":       country,
            "Current (£/€)": round(current, 2) if current else "N/A",
            "Min (£/€)":     round(min_p, 2) if min_p else "N/A",
            "Max (£/€)":     round(max_p, 2) if max_p else "N/A",
            "Avg (£/€)":     avg_p if avg_p else "N/A",
            "30d change %":  drop_pct if drop_pct else 0,
            "OOS":           is_oos,
            "Alert":         alert,
        })

    return pd.DataFrame(summary)


def get_alerts(summary_df: pd.DataFrame) -> pd.DataFrame:
    """Return only products that need attention."""
    if summary_df.empty:
        return pd.DataFrame()
    alerts = summary_df[summary_df["Alert"] != "🟢 STABLE"]
    return alerts.sort_values("Alert")
