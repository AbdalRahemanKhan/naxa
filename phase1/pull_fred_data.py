# ============================================================
# NAXA Phase 1 — Script 2: Pull FRED Economic Data
# Purpose: Pull real economic measurements (not equity prices)
#          for the Panama Canal Drought 2023 signal chain
#
# What FRED gives us that yfinance cannot:
#   - Actual freight price indexes (not stock proxies)
#   - Raw commodity prices with official source citations
#   - Macro context indicators
#   - Data we can cite by series ID in our JSON
# ============================================================

import requests                  # makes HTTP API calls
import pandas as pd              # organizes data into tables
import matplotlib.pyplot as plt  # draws charts
import os                        # file path handling
from config import (             # pulls our keys + shared config
    FRED_API_KEY,
    FRED_BASE_URL,
    START_DATE,
    END_DATE,
    EVENT_DATE
)

# ============================================================
# SECTION 1: DEFINE THE FRED SERIES WE WANT
# ============================================================
#
# Each entry is:
#   "SERIES_ID": ("Human-readable name", "frequency")
#
# Frequency matters because FRED series run at different speeds:
#   "d" = daily   (new data every trading day)
#   "m" = monthly (new data once per month)
#
# This is the key new concept for Day 2:
# DAILY data and MONTHLY data cannot be directly combined —
# we need to align them first. We handle this in Section 4.

FRED_SERIES = {

    # --- TIER 1: Closest to actual shipping rates ---
    # PPI = Producer Price Index
    # Measures the average change in prices received by
    # domestic producers. For shipping, this tracks how much
    # it costs to move goods — from the shipper's perspective.
    "PCU483111483111": (
        "PPI: Deep Sea Freight Transportation",
        "m"   # monthly
    ),

    # --- TIER 2: Commodity prices affected by rerouting ---
    # When ships reroute via Cape Horn instead of Panama,
    # it adds ~15-20 days to the voyage.
    # That extra time = extra fuel cost = affects energy prices.
    # WTI crude is the benchmark fuel cost proxy.
    "DCOILWTICO": (
        "WTI Crude Oil Spot Price (USD/barrel)",
        "d"   # daily
    ),

    # Henry Hub is the pricing benchmark for US natural gas.
    # US LNG exports to Asia went through Panama Canal.
    # Rerouting added cost → affected Asian LNG spot prices.
    # Henry Hub is the upstream signal for that chain.
    "MHHNGSP": (
        "Henry Hub Natural Gas Spot Price (USD/MMBtu)",
        "m"   # monthly
    ),

    # --- TIER 3: Grain shipping proxies ---
    # Panama Canal handles ~5% of global grain trade.
    # When it restricts, grain stuck in US Gulf ports
    # cannot reach Asian buyers efficiently.
    # Corn and soybean prices reflect this demand shock.
    "PMAIZMTUSD": (
        "Global Price of Corn/Maize (USD/MT)",
        "m"   # monthly
    ),
    "PSOYBUSDM": (
        "Global Price of Soybeans (USD/MT)",
        "m"   # monthly
    ),

    # --- TIER 4: Macro context ---
    # The yield curve (10-year minus 2-year Treasury rate)
    # tells us the macroeconomic backdrop during the event.
    # A negative/falling yield curve = recession fears.
    # We need this to contextualize whether commodity moves
    # were caused by the canal event OR by macro fear.
    # This is the counterfactual baseline concept from yesterday.
    "T10Y2Y": (
        "10-Year minus 2-Year Treasury Yield Spread",
        "d"   # daily
    )
}

# ============================================================
# SECTION 2: THE API CALL FUNCTION
# ============================================================
#
# This is the core engine. One function that knows how to
# talk to FRED's API and return clean data.
#
# Teaching moment — function anatomy:
#   def function_name(inputs):     ← define what goes IN
#       [do something]             ← the work
#       return output              ← define what comes OUT
#
# This function takes a series_id string ("DCOILWTICO")
# and returns a pandas DataFrame with dates and values.

def fetch_fred_series(series_id, series_name, frequency):
    """
    Calls the FRED API for one series.
    Returns a DataFrame with two columns: 'date' and series_id.

    Parameters:
        series_id   (str): FRED series code e.g. "DCOILWTICO"
        series_name (str): Human-readable label for logging
        frequency   (str): "d" for daily, "m" for monthly

    Returns:
        pd.DataFrame with columns ['date', series_id]
        or None if the call fails
    """

    print(f"  Fetching: {series_id} — {series_name}...")

    # Build the request parameters
    # This is like filling out a form before sending it
    params = {
        "series_id":          series_id,
        "api_key":            FRED_API_KEY,
        "file_type":          "json",         # ask for JSON back
        "observation_start":  START_DATE,     # from June 1 2023
        "observation_end":    END_DATE,       # to Jan 31 2024
        "frequency":          frequency,      # d or m
        "aggregation_method": "avg"           # if downsampling: use average
    }

    # requests.get() sends the HTTP request to FRED's server
    # It's like typing a URL into a browser, but programmatically
    try:
        response = requests.get(FRED_BASE_URL, params=params, timeout=10)
        # timeout=10 means: if FRED doesn't respond in 10 seconds, give up
        # Without a timeout, your script could hang forever

        # .raise_for_status() crashes if FRED returned an error code
        # (e.g. 401 = bad API key, 404 = series not found)
        # Better to crash loudly here than silently return wrong data
        response.raise_for_status()

    except requests.exceptions.RequestException as e:
        # If anything goes wrong with the network call, catch it here
        # Print a helpful message and return None (nothing)
        print(f"  ERROR fetching {series_id}: {e}")
        return None

    # Parse the JSON response into a Python dictionary
    data = response.json()
    # data now looks like:
    # {
    #   "observations": [
    #     {"date": "2023-06-01", "value": "71.82"},
    #     {"date": "2023-06-02", "value": "72.14"},
    #     ...
    #   ]
    # }

    # Extract just the observations list
    observations = data.get("observations", [])

    if not observations:
        print(f"  WARNING: No data returned for {series_id}")
        return None

    # Convert to a DataFrame
    df = pd.DataFrame(observations)
    # df currently has columns: realtime_start, realtime_end, date, value
    # We only want: date, value

    df = df[["date", "value"]]

    # Convert date column from string to proper datetime objects
    # This lets pandas do date math (add 14 days, find nearest date, etc.)
    df["date"] = pd.to_datetime(df["date"])

    # FRED sometimes returns "." for missing values — convert to NaN
    # NaN = Not a Number — pandas' way of representing missing data
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    # errors="coerce" means: if you can't convert it to a number, make it NaN

    # Drop rows where value is NaN (missing data points)
    df = df.dropna(subset=["value"])

    # Set date as the index (the row label)
    # This makes date-based lookups much faster and cleaner
    df = df.set_index("date")

    # Rename the value column to the series_id
    # So instead of a generic "value" column, it's labeled "DCOILWTICO"
    # This matters when we merge multiple series later
    df = df.rename(columns={"value": series_id})

    print(f"  ✓ Got {len(df)} observations for {series_id}")
    return df


# ============================================================
# SECTION 3: PULL ALL SERIES
# ============================================================
#
# Now we call fetch_fred_series() for every series in our list.
# Each call returns a DataFrame. We store them all in a dict.
#
# Dict structure:
#   {
#     "DCOILWTICO": DataFrame(date_index, values),
#     "MHHNGSP":    DataFrame(date_index, values),
#     ...
#   }

print("=" * 55)
print("NAXA Phase 1 — Pulling FRED Data")
print("=" * 55)

raw_frames = {}   # empty dict to collect DataFrames as they arrive

for series_id, (series_name, frequency) in FRED_SERIES.items():
    df = fetch_fred_series(series_id, series_name, frequency)
    if df is not None:
        raw_frames[series_id] = df

print(f"\nSuccessfully pulled {len(raw_frames)} of {len(FRED_SERIES)} series")


# ============================================================
# SECTION 4: ALIGN FREQUENCIES
# ============================================================
#
# THIS IS THE KEY NEW CONCEPT FOR DAY 2.
#
# Problem: Daily series (WTI oil) have ~173 rows for our period.
#          Monthly series (corn price) have ~8 rows.
#          You cannot align them on a shared timeline without
#          deciding what to do with the gaps.
#
# Solution: Separate them. Analyze daily series daily.
#           Analyze monthly series monthly.
#           Only combine them at the "signal chain" level,
#           not at the raw data level.
#
# Think of it like this:
#   Daily data   = heartbeat monitor (reading every second)
#   Monthly data = doctor's monthly checkup notes
#   You can reference both, but you don't average them together.

daily_series_ids   = [s for s in raw_frames if FRED_SERIES[s][1] == "d"]
monthly_series_ids = [s for s in raw_frames if FRED_SERIES[s][1] == "m"]

print(f"\nDaily series:   {daily_series_ids}")
print(f"Monthly series: {monthly_series_ids}")

# Combine all daily series into one DataFrame using pd.concat
# axis=1 means "stack them as columns" (not rows)
# join="outer" means "keep all dates, fill gaps with NaN"
if daily_series_ids:
    daily_df = pd.concat(
        [raw_frames[s] for s in daily_series_ids],
        axis=1,
        join="outer"
    )
    # Forward-fill gaps: if Tuesday is missing, use Monday's value
    # This handles weekends and holidays in daily series
    daily_df = daily_df.ffill()
else:
    daily_df = pd.DataFrame()

# Combine all monthly series
if monthly_series_ids:
    monthly_df = pd.concat(
        [raw_frames[s] for s in monthly_series_ids],
        axis=1,
        join="outer"
    )
else:
    monthly_df = pd.DataFrame()

print(f"\nDaily DataFrame shape:   {daily_df.shape}")
print(f"Monthly DataFrame shape: {monthly_df.shape}")


# ============================================================
# SECTION 5: SAVE RAW DATA
# ============================================================

os.makedirs("data/raw", exist_ok=True)
os.makedirs("data/processed", exist_ok=True)

if not daily_df.empty:
    daily_df.to_csv("data/raw/fred_daily_raw.csv")
    print("\nSaved: data/raw/fred_daily_raw.csv")

if not monthly_df.empty:
    monthly_df.to_csv("data/raw/fred_monthly_raw.csv")
    print("Saved: data/raw/fred_monthly_raw.csv")


# ============================================================
# SECTION 6: CALCULATE MOVES AROUND THE EVENT
# ============================================================
#
# Same approach as Day 1 — measure % move from event date
# at 14, 30, and 60 day lags.
#
# New concept introduced here: .loc[] vs .iloc[]
#   df.loc[date]  = look up by LABEL (a specific date)
#   df.iloc[0]    = look up by POSITION (the first row, index 0)
# We use .loc[] here because we want specific dates.

event_dt = pd.Timestamp(EVENT_DATE)

def get_nearest_date(df, target_date):
    """Find the closest date in the index that is >= target_date"""
    available = df.index[df.index >= target_date]
    return available[0] if len(available) > 0 else None

print("\n" + "=" * 55)
print("SIGNAL CHAIN — FRED DATA MOVES FROM EVENT DATE")
print("=" * 55)

def print_moves(df, series_map, label):
    """Print % moves for each series at key lag points"""
    if df.empty:
        return

    event_day = get_nearest_date(df, event_dt)
    day_14    = get_nearest_date(df, event_dt + pd.Timedelta(days=14))
    day_30    = get_nearest_date(df, event_dt + pd.Timedelta(days=30))
    day_60    = get_nearest_date(df, event_dt + pd.Timedelta(days=60))

    print(f"\n{label}")
    print(f"  Reference dates: event={event_day.date() if event_day else 'N/A'}, "
          f"+14d={day_14.date() if day_14 else 'N/A'}, "
          f"+30d={day_30.date() if day_30 else 'N/A'}, "
          f"+60d={day_60.date() if day_60 else 'N/A'}")
    print()

    results = []
    for series_id in df.columns:
        if series_id not in series_map:
            continue
        series_name = series_map[series_id][0]

        try:
            price_event = df.loc[event_day, series_id]
            price_14    = df.loc[day_14, series_id]
            price_30    = df.loc[day_30, series_id]
            price_60    = df.loc[day_60, series_id]

            move_14 = ((price_14 - price_event) / price_event) * 100
            move_30 = ((price_30 - price_event) / price_event) * 100
            move_60 = ((price_60 - price_event) / price_event) * 100

            print(f"  {series_id} ({series_name[:35]})")
            print(f"    +14d: {move_14:+.1f}%  |  +30d: {move_30:+.1f}%  |  +60d: {move_60:+.1f}%")
            print()

            results.append({
                "Series_ID":    series_id,
                "Description":  series_name,
                "Frequency":    series_map[series_id][1],
                "Value_Event":  round(price_event, 3),
                "Move_14d_%":   round(move_14, 2),
                "Move_30d_%":   round(move_30, 2),
                "Move_60d_%":   round(move_60, 2)
            })

        except (KeyError, TypeError) as e:
            print(f"  {series_id}: Could not calculate moves — {e}")

    return results

daily_results   = print_moves(daily_df,   FRED_SERIES, "DAILY SERIES")
monthly_results = print_moves(monthly_df, FRED_SERIES, "MONTHLY SERIES")

# Save combined results
all_results = []
if daily_results:
    all_results.extend(daily_results)
if monthly_results:
    all_results.extend(monthly_results)

if all_results:
    results_df = pd.DataFrame(all_results)
    results_df.to_csv("data/processed/fred_moves_from_event.csv", index=False)
    print("Saved: data/processed/fred_moves_from_event.csv")


# ============================================================
# SECTION 7: VISUALIZE
# ============================================================
#
# Three charts:
#   Top:    WTI oil (daily) — energy complex response
#   Middle: Freight PPI + Natural Gas (monthly) — rate response
#   Bottom: Corn + Soybean (monthly) — grain trade response
#
# Each normalized to 100 at start (same technique as Day 1)
# Red dashed line = event date on every chart

def normalize_to_100(df):
    """Rebase all columns to 100 at their first valid value"""
    return (df / df.iloc[0]) * 100

fig, axes = plt.subplots(3, 1, figsize=(14, 13))
event_line = pd.Timestamp(EVENT_DATE)

# --- Chart 1: Daily series (WTI oil + yield curve) ---
ax1 = axes[0]
if not daily_df.empty:
    norm_daily = normalize_to_100(daily_df)
    for col in norm_daily.columns:
        label = FRED_SERIES.get(col, (col,))[0][:40]
        ax1.plot(norm_daily.index, norm_daily[col], label=label, linewidth=1.5)

ax1.axvline(x=event_line, color="red", linestyle="--",
            linewidth=2, label="ACP Restriction Aug 1 2023")
ax1.axhline(y=100, color="gray", linestyle=":", linewidth=1, alpha=0.4)
ax1.set_title("Daily FRED Series — Normalized to 100 at Jun 1 2023", fontsize=12)
ax1.set_ylabel("Index (Rebased to 100)")
ax1.legend(loc="upper left", fontsize=8)
ax1.grid(True, alpha=0.3)

# --- Chart 2: Monthly energy + freight ---
ax2 = axes[1]
monthly_energy_ids = ["MHHNGSP", "PCU483111483111"]
monthly_energy_df = monthly_df[[c for c in monthly_energy_ids if c in monthly_df.columns]]

if not monthly_energy_df.empty:
    norm_energy = normalize_to_100(monthly_energy_df)
    for col in norm_energy.columns:
        label = FRED_SERIES.get(col, (col,))[0][:40]
        ax2.plot(norm_energy.index, norm_energy[col],
                 label=label, linewidth=2, marker="o", markersize=4)

ax2.axvline(x=event_line, color="red", linestyle="--", linewidth=2)
ax2.axhline(y=100, color="gray", linestyle=":", linewidth=1, alpha=0.4)
ax2.set_title("Monthly: Freight PPI + Natural Gas — Normalized to 100", fontsize=12)
ax2.set_ylabel("Index (Rebased to 100)")
ax2.legend(loc="upper left", fontsize=8)
ax2.grid(True, alpha=0.3)

# --- Chart 3: Monthly grain prices ---
ax3 = axes[2]
monthly_grain_ids = ["PMAIZMTUSD", "PSOYBUSDM"]
monthly_grain_df = monthly_df[[c for c in monthly_grain_ids if c in monthly_df.columns]]

if not monthly_grain_df.empty:
    norm_grain = normalize_to_100(monthly_grain_df)
    for col in norm_grain.columns:
        label = FRED_SERIES.get(col, (col,))[0][:40]
        ax3.plot(norm_grain.index, norm_grain[col],
                 label=label, linewidth=2, marker="s", markersize=4)

ax3.axvline(x=event_line, color="red", linestyle="--", linewidth=2)
ax3.axhline(y=100, color="gray", linestyle=":", linewidth=1, alpha=0.4)
ax3.set_title("Monthly: Grain Prices (Corn + Soybean) — Normalized to 100", fontsize=12)
ax3.set_ylabel("Index (Rebased to 100)")
ax3.set_xlabel("Date")
ax3.legend(loc="upper left", fontsize=8)
ax3.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig("data/processed/fred_signal_chain_chart.png", dpi=150)
plt.show()

print("\nChart saved: data/processed/fred_signal_chain_chart.png")
print("\nPhase 1 Day 2 complete.")
print("\nNext: build_master_timeline.py — combine equity + FRED into one view")