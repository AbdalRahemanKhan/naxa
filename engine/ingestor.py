# ============================================================
# NAXA Phase 2 — engine/ingestor.py
#
# The Data Ingestor
# ============================================================
#
# WHAT THIS MODULE DOES:
#   Fetches live market data (equities via yfinance, economic
#   series via FRED) and returns structured DataFrames.
#   It does NOT save files — that is analyze.py's decision.
#   It does NOT calculate moves — that is correlator.py's job.
#   It ONLY fetches and lightly cleans raw data.
#
# WHY SEPARATION MATTERS HERE:
#   Phase 1 pull scripts did three things in one file:
#     1. Fetch data
#     2. Calculate moves
#     3. Save files + draw charts
#   That's fine for exploration. It's brittle for a pipeline.
#   If the chart library breaks, your data fetch breaks too.
#   Separation means each function fails independently.
#
# QUANT CONCEPT — "Ingestor" in production data pipelines:
#   Every serious quant fund has an ingestion layer — a
#   dedicated service that only fetches and normalizes raw data.
#   It has no business logic. It doesn't know what "Panama Canal"
#   means. It just pulls prices and returns clean DataFrames.
#   Bloomberg's B-PIPE, Refinitiv Elektron — these are
#   enterprise-grade ingestors. Ours is simpler but same concept.
# ============================================================

import pandas as pd
import yfinance as yf
import requests
from datetime import datetime, timedelta
from typing import Optional

# Import from root config, not phase1/config.py
from config import (
    FRED_API_KEY,
    FRED_BASE_URL,
    SHIPPING_TICKERS,
    FRED_SERIES,
)


# ============================================================
# SECTION 1: EQUITY INGESTOR
# ============================================================
#
# Wraps Phase 1's pull_shipping_data.py core logic.
# Key changes from Phase 1:
#   - Returns DataFrame instead of saving to CSV
#   - Accepts tickers as parameter instead of hardcoded
#   - Adds proper error handling per ticker
#   - Logs clearly so pipeline output is readable

def fetch_equities(
    tickers: dict,
    start_date: str,
    end_date: str,
) -> Optional[pd.DataFrame]:
    """
    Fetches adjusted closing prices for a set of equity tickers.

    Args:
        tickers    (dict): {ticker: description} e.g. {"ZIM": "ZIM Shipping"}
        start_date (str):  "YYYY-MM-DD" format
        end_date   (str):  "YYYY-MM-DD" format

    Returns:
        pd.DataFrame: rows = dates, columns = ticker symbols
                      Adjusted closing prices, NaN where unavailable.
        None if the fetch fails entirely.

    WHY auto_adjust=True:
        Stock prices need to be adjusted for splits and dividends.
        If ZIM does a 2-for-1 split, the raw price halves overnight
        with no real economic change. Adjusted prices correct for this.
        Always use adjusted prices for historical analysis.
    """
    print(f"  [Ingestor] Fetching {len(tickers)} equity tickers...")
    print(f"  [Ingestor] Range: {start_date} → {end_date}")

    ticker_list = list(tickers.keys())

    try:
        # yf.download() with multiple tickers returns a MultiIndex DataFrame
        # We select ['Close'] to get a simple ticker → price table
        raw = yf.download(
            tickers=ticker_list,
            start=start_date,
            end=end_date,
            auto_adjust=True,    # adjusted for splits + dividends
            progress=False,      # suppress yfinance's download bar
        )["Close"] # type: ignore

        # If only one ticker was requested, yfinance returns a Series
        # Convert it back to a DataFrame for consistency
        if isinstance(raw, pd.Series):
            raw = raw.to_frame(name=ticker_list[0])

        # Report what we got vs. what we asked for
        available = [t for t in ticker_list if t in raw.columns]
        missing   = [t for t in ticker_list if t not in raw.columns]

        print(f"  [Ingestor] ✓ Equity data: {len(available)} tickers, "
              f"{len(raw)} trading days")
        if missing:
            print(f"  [Ingestor] ⚠ Missing tickers: {missing}")

        return raw

    except Exception as e:
        print(f"  [Ingestor] ERROR fetching equities: {e}")
        return None


# ============================================================
# SECTION 2: FRED INGESTOR
# ============================================================
#
# Wraps Phase 1's pull_fred_data.py core logic.
# Key changes from Phase 1:
#   - Returns (daily_df, monthly_df) tuple instead of saving CSVs
#   - Accepts series_dict as parameter
#   - Separates daily/monthly automatically
#   - Each series fetched independently — one failure doesn't
#     block the others (Phase 1 was all-or-nothing)
#
# QUANT CONCEPT — Why we separate daily and monthly:
#   Mixing frequencies creates "temporal aliasing" — a stats
#   term for measurement errors caused by mismatched time scales.
#   A daily oil price and a monthly corn price cannot be compared
#   on the same axis without explicit resampling decisions.
#   We keep them separate and let the correlator decide how
#   to align them for each specific signal.

def _fetch_single_fred_series(
    series_id: str,
    series_name: str,
    frequency: str,
    start_date: str,
    end_date: str,
) -> Optional[pd.DataFrame]:
    """
    Fetches one FRED series. Internal helper — not called directly.

    Returns:
        pd.DataFrame with DatetimeIndex and one column named series_id
        None if fetch fails
    """
    params = {
        "series_id":          series_id,
        "api_key":            FRED_API_KEY,
        "file_type":          "json",
        "observation_start":  start_date,
        "observation_end":    end_date,
        "frequency":          frequency,
        "aggregation_method": "avg",
    }

    try:
        response = requests.get(FRED_BASE_URL, params=params, timeout=15)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        # Log only series ID and status code — NEVER the full URL
        # Full URL contains the API key in query parameters
        status = (
            e.response.status_code
            if hasattr(e, "response") and e.response is not None
            else "network_error"
        )
        print(f"  [Ingestor] ERROR fetching {series_id}: HTTP {status}")
        return None

    observations = response.json().get("observations", [])

    if not observations:
        print(f"  [Ingestor] ⚠ No data returned for {series_id}")
        return None

    df = pd.DataFrame(observations)[["date", "value"]]
    df["date"]  = pd.to_datetime(df["date"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])
    df = df.set_index("date")
    df = df.rename(columns={"value": series_id})

    return df


def fetch_fred(
    series_dict: dict,
    start_date: str,
    end_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Fetches all FRED series and returns them split by frequency.

    Args:
        series_dict (dict): {series_id: (name, frequency)}
                            e.g. {"DCOILWTICO": ("WTI Crude", "d")}
        start_date  (str):  "YYYY-MM-DD"
        end_date    (str):  "YYYY-MM-DD"

    Returns:
        tuple: (daily_df, monthly_df)
               daily_df   — DatetimeIndex, one column per daily series
               monthly_df — DatetimeIndex, one column per monthly series
               Either can be an empty DataFrame if no series of that
               frequency were available.

    FREQUENCY HANDLING:
        Daily series:   forward-filled to handle weekends/holidays
        Monthly series: kept as-is (monthly point values)
    """
    print(f"  [Ingestor] Fetching {len(series_dict)} FRED series...")

    daily_frames   = []
    monthly_frames = []

    for series_id, (series_name, frequency) in series_dict.items():
        print(f"  [Ingestor]   {series_id} ({series_name[:35]})...")
        df = _fetch_single_fred_series(
            series_id, series_name, frequency, start_date, end_date
        )
        if df is None:
            continue

        print(f"  [Ingestor]   ✓ {len(df)} observations")

        if frequency == "d":
            daily_frames.append(df)
        elif frequency == "m":
            monthly_frames.append(df)

    # Combine all daily series into one DataFrame
    # pd.concat with axis=1 stacks DataFrames as columns (side by side)
    # join="outer" keeps all dates, filling gaps with NaN
    if daily_frames:
        daily_df = pd.concat(daily_frames, axis=1, join="outer", sort=False)
        # Forward-fill: if Tuesday is missing, use Monday's value
        # This handles weekends, bank holidays, data gaps
        daily_df = daily_df.ffill()
    else:
        daily_df = pd.DataFrame()

    if monthly_frames:
        monthly_df = pd.concat(monthly_frames, axis=1, join="outer")
    else:
        monthly_df = pd.DataFrame()

    print(f"  [Ingestor] ✓ FRED complete: "
          f"{daily_df.shape[1] if not daily_df.empty else 0} daily, "
          f"{monthly_df.shape[1] if not monthly_df.empty else 0} monthly series")

    return daily_df, monthly_df


# ============================================================
# SECTION 3: NORMALIZE UTILITY
# ============================================================
#
# Shared by ingestor — the correlator uses this when it
# needs to visualize or compare series on the same scale.
#
# QUANT CONCEPT — Why normalize to 100:
#   ZIM trades at ~$8. MATX trades at ~$90. Raw prices
#   are incomparable — an $82 gap tells you nothing.
#   Normalizing to 100 converts everything to "% change
#   from baseline." Now a 10-point move = 10% move for any
#   asset regardless of its absolute price level.
#   This is called "rebasing" — standard practice in quant
#   research and how Bloomberg charts work by default.

def normalize_to_100(df: pd.DataFrame) -> pd.DataFrame:
    """
    Rebases all columns to 100 at their first valid value.
    Handles NaN values at the start of series.

    Args:
        df (pd.DataFrame): price data with DatetimeIndex

    Returns:
        pd.DataFrame: same shape, values scaled to start at 100
    """
    result = pd.DataFrame(index=df.index)

    for col in df.columns:
        series = df[col].dropna()
        if len(series) == 0:
            continue
        first_val = series.iloc[0]
        if first_val == 0:
            continue
        result[col] = (df[col] / first_val) * 100

    return result


# ============================================================
# SECTION 4: SMOKE TEST
# ============================================================
#
# Run ingestor.py directly to verify both data sources work.
# This is a "smoke test" — a quick check that nothing is
# obviously broken before you run the full pipeline.
# The term comes from hardware engineering: turn it on,
# check if it smokes. If not, proceed.

if __name__ == "__main__":
    from config import START_DATE, END_DATE

    print("=" * 55)
    print("NAXA Ingestor — Smoke Test")
    print("=" * 55)

    # Test equity fetch
    print("\n[1/2] Testing equity fetch...")
    eq_df = fetch_equities(SHIPPING_TICKERS, START_DATE, END_DATE)
    if eq_df is not None:
        print(f"  ✓ Shape: {eq_df.shape}")
        print(f"  ✓ Columns: {list(eq_df.columns)}")
        print(f"  ✓ Date range: {eq_df.index[0].date()} → {eq_df.index[-1].date()}")
    else:
        print("  ✗ Equity fetch failed")

    # Test FRED fetch
    print("\n[2/2] Testing FRED fetch...")
    daily_df, monthly_df = fetch_fred(FRED_SERIES, START_DATE, END_DATE)
    print(f"  ✓ Daily shape:   {daily_df.shape}")
    print(f"  ✓ Monthly shape: {monthly_df.shape}")

    print("\n" + "=" * 55)
    print("Smoke test complete. Ingestor is operational.")
    print("=" * 55)