# ============================================================
# NAXA Phase 1 — Script 1: Pull Shipping & Commodity Data
# Purpose: Pull historical price data for the Panama Canal
#          Drought 2023 signal chain analysis
# ============================================================

import yfinance as yf          # pulls financial market data
import pandas as pd            # organizes data into tables
import matplotlib.pyplot as plt  # draws charts
import os                      # handles file paths and folders

# ============================================================
# SECTION 1: DEFINE WHAT WE'RE PULLING
# ============================================================

# The six shipping stocks we care about and why each matters
SHIPPING_TICKERS = {
    'ZIM':  'ZIM Integrated Shipping (container)',
    'MATX': 'Matson Inc (US container, Pacific routes)',
    'DAC':  'Danaos Corp (container ship lessor)',
    'GNK':  'Genco Shipping (dry bulk)',
    'INSW': 'International Seaways (tanker)',
    'FRO':  'Frontline (tanker)'
}

# Commodity and macro proxies
# These are not the actual commodities — they're the closest
# free proxies we can get via yfinance
COMMODITY_TICKERS = {
    'BDI=F':  'Baltic Dry Index Futures (dry bulk freight proxy)',
    'NG=F':   'Natural Gas Futures (LNG proxy)',
    'ZC=F':   'Corn Futures (grain shipping proxy)'
}

# Date range: 2 months before the event → 2 months after peak
# Event: ACP announced restrictions Aug 2023
# We start June 1 to capture the pre-event baseline
START_DATE = '2023-06-01'
END_DATE   = '2024-01-31'

# The exact date the Panama Canal Authority issued formal
# draft restrictions — this is our event line on every chart
EVENT_DATE = '2023-08-01'

# ============================================================
# SECTION 2: PULL THE DATA
# ============================================================

print("Pulling shipping equity data...")

# yf.download() hits Yahoo Finance and returns a DataFrame
# A DataFrame is like a spreadsheet in Python:
# rows = dates, columns = ticker symbols
# 'Adj Close' = Adjusted Closing Price
# (adjusted for stock splits and dividends — always use this,
#  not raw 'Close', for accurate historical comparisons)

shipping_data = yf.download(
    tickers=list(SHIPPING_TICKERS.keys()),  # ['ZIM','MATX','DAC',...]
    start=START_DATE,
    end=END_DATE,
    auto_adjust=True   # gives us adjusted prices directly
)['Close']             # pull only the closing price column

print(f"Shipping data shape: {shipping_data.shape}")
# shape = (rows, columns) e.g. (173, 6) means 173 trading days, 6 stocks

print("\nPulling commodity proxy data...")

commodity_data = yf.download(
    tickers=list(COMMODITY_TICKERS.keys()),
    start=START_DATE,
    end=END_DATE,
    auto_adjust=True
)['Close']

print(f"Commodity data shape: {commodity_data.shape}")

# ============================================================
# SECTION 3: NORMALIZE THE DATA
# ============================================================

# Raw prices are useless for comparison — ZIM trades at $8,
# MATX at $90. Plotting them together is meaningless.
# We normalize: rebase every series to 100 on June 1, 2023.
# Now every line starts at 100, and the Y-axis shows
# percentage change from baseline. This is how quants do it.

def normalize_to_100(df):
    """
    Takes a DataFrame of prices.
    Divides every column by its first valid value.
    Multiplies by 100.
    Result: every series starts at 100, moves show % change.
    """
    return (df / df.iloc[0]) * 100

shipping_normalized   = normalize_to_100(shipping_data)
commodity_normalized  = normalize_to_100(commodity_data)

# ============================================================
# SECTION 4: SAVE THE RAW DATA
# ============================================================

# Always save raw data before doing anything else with it.
# Rule: raw data is sacred. Never modify it. Only read from it.

os.makedirs('data/raw', exist_ok=True)   # create folder if missing

shipping_data.to_csv('data/raw/shipping_equities_raw.csv')
commodity_data.to_csv('data/raw/commodity_proxies_raw.csv')

print("\nRaw data saved to data/raw/")

# ============================================================
# SECTION 5: CALCULATE KEY METRICS
# ============================================================

# For each ticker, calculate:
# - Price on event date (Aug 1 2023)
# - Price 14 days after event
# - Price 30 days after event
# - The % move at each lag

print("\n--- SIGNAL CHAIN METRICS ---")
print(f"Event date: {EVENT_DATE}")
print(f"Baseline: {START_DATE}\n")

# Convert EVENT_DATE string to a datetime for indexing
event_dt = pd.Timestamp(EVENT_DATE)

# Find the nearest available trading day to each target date
def get_nearest_date(df, target_date):
    """Find closest date in index that is >= target date"""
    available = df.index[df.index >= target_date]
    return available[0] if len(available) > 0 else None

event_day    = get_nearest_date(shipping_data, event_dt)
day_14       = get_nearest_date(shipping_data, event_dt + pd.Timedelta(days=14))
day_30       = get_nearest_date(shipping_data, event_dt + pd.Timedelta(days=30))
day_60       = get_nearest_date(shipping_data, event_dt + pd.Timedelta(days=60))

print(f"Event day used:  {event_day.date()}")
print(f"14-day mark:     {day_14.date()}")
print(f"30-day mark:     {day_30.date()}")
print(f"60-day mark:     {day_60.date()}\n")

# Calculate % moves for each ticker
results = []

for ticker in SHIPPING_TICKERS:
    if ticker not in shipping_data.columns:
        continue
    
    price_event = shipping_data.loc[event_day, ticker]
    price_14    = shipping_data.loc[day_14, ticker]
    price_30    = shipping_data.loc[day_30, ticker]
    price_60    = shipping_data.loc[day_60, ticker]
    
    move_14 = ((price_14 - price_event) / price_event) * 100
    move_30 = ((price_30 - price_event) / price_event) * 100
    move_60 = ((price_60 - price_event) / price_event) * 100
    
    results.append({
        'Ticker':      ticker,
        'Description': SHIPPING_TICKERS[ticker],
        'Price_Event': round(price_event, 2),
        'Move_14d_%':  round(move_14, 2),
        'Move_30d_%':  round(move_30, 2),
        'Move_60d_%':  round(move_60, 2)
    })
    
    print(f"{ticker}: +14d={move_14:+.1f}%  +30d={move_30:+.1f}%  +60d={move_60:+.1f}%")

# Save metrics to CSV
results_df = pd.DataFrame(results)
results_df.to_csv('data/processed/shipping_moves_from_event.csv', index=False)
print("\nMetrics saved to data/processed/shipping_moves_from_event.csv")

# ============================================================
# SECTION 6: PLOT THE CHARTS
# ============================================================

# Chart 1: Shipping Equities — normalized from baseline

fig, axes = plt.subplots(2, 1, figsize=(14, 10))
# subplots(2, 1) = 2 rows, 1 column of charts
# figsize=(14, 10) = width 14 inches, height 10 inches

ax1 = axes[0]  # top chart
ax2 = axes[1]  # bottom chart

# Plot each shipping stock as its own line
for ticker in shipping_normalized.columns:
    ax1.plot(
        shipping_normalized.index,      # X axis = dates
        shipping_normalized[ticker],    # Y axis = normalized price
        label=ticker,
        linewidth=1.5
    )

# Draw a vertical red line on the event date
ax1.axvline(
    x=pd.Timestamp(EVENT_DATE),
    color='red',
    linestyle='--',
    linewidth=2,
    label='ACP Restriction Announcement'
)

# Draw a horizontal line at 100 (the baseline)
ax1.axhline(y=100, color='gray', linestyle=':', linewidth=1, alpha=0.5)

ax1.set_title('Shipping Equities — Normalized to 100 at Jun 1 2023', fontsize=13)
ax1.set_ylabel('Price (Rebased to 100)')
ax1.legend(loc='upper left', fontsize=8)
ax1.grid(True, alpha=0.3)

# Chart 2: Commodity Proxies
for ticker in commodity_normalized.columns:
    ax2.plot(
        commodity_normalized.index,
        commodity_normalized[ticker],
        label=ticker,
        linewidth=1.5
    )

ax2.axvline(
    x=pd.Timestamp(EVENT_DATE),
    color='red',
    linestyle='--',
    linewidth=2,
    label='ACP Restriction Announcement'
)

ax2.axhline(y=100, color='gray', linestyle=':', linewidth=1, alpha=0.5)

ax2.set_title('Commodity Proxies — Normalized to 100 at Jun 1 2023', fontsize=13)
ax2.set_ylabel('Price (Rebased to 100)')
ax2.set_xlabel('Date')
ax2.legend(loc='upper left', fontsize=8)
ax2.grid(True, alpha=0.3)

plt.tight_layout()  # prevents charts from overlapping
plt.savefig('data/processed/panama_canal_signal_chain_chart.png', dpi=150)
plt.show()

print("\nChart saved to data/processed/panama_canal_signal_chain_chart.png")
print("\nPhase 1 Day 1 complete.")