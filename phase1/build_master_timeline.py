# ============================================================
# NAXA Phase 1 — Script 3: Build Master Signal Chain Timeline
# Purpose: Combine Day 1 equity data + Day 2 FRED data into
#          one unified view of the Panama Canal signal chain
#
# This is the first time you'll see the full chain together:
#   Physical event → Freight rates → Commodities → Equities
#
# This combined view becomes the visual proof that NAXA's
# signal chain logic is grounded in real data.
# ============================================================

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import os
from config import EVENT_DATE, START_DATE, END_DATE

# ============================================================
# SECTION 1: LOAD ALL PREVIOUSLY SAVED DATA
# ============================================================
#
# We never re-pull data we already have.
# We read from the CSV files saved in Day 1 and Day 2.
#
# This is the "raw data is sacred" principle in action:
# Pull once, save, read many times.
# If you need to re-analyze, you don't re-hit the API.

print("Loading saved data...")

# Day 1: Shipping equity prices
try:
    equity_df = pd.read_csv(
        "data/raw/shipping_equities_raw.csv",
        index_col=0,           # first column is the date index
        parse_dates=True       # auto-convert date strings to datetime
    )
    print(f"  ✓ Equity data loaded: {equity_df.shape}")
except FileNotFoundError:
    print("  ERROR: Run pull_shipping_data.py first (Day 1)")
    equity_df = pd.DataFrame()

# Day 2: FRED daily data (WTI oil, yield curve)
try:
    fred_daily_df = pd.read_csv(
        "data/raw/fred_daily_raw.csv",
        index_col=0,
        parse_dates=True
    )
    print(f"  ✓ FRED daily data loaded: {fred_daily_df.shape}")
except FileNotFoundError:
    print("  ERROR: Run pull_fred_data.py first (Day 2)")
    fred_daily_df = pd.DataFrame()

# Day 2: FRED monthly data (commodities, freight PPI)
try:
    fred_monthly_df = pd.read_csv(
        "data/raw/fred_monthly_raw.csv",
        index_col=0,
        parse_dates=True
    )
    print(f"  ✓ FRED monthly data loaded: {fred_monthly_df.shape}")
except FileNotFoundError:
    print("  ERROR: Run pull_fred_data.py first (Day 2)")
    fred_monthly_df = pd.DataFrame()


# ============================================================
# SECTION 2: NORMALIZE EVERYTHING TO 100
# ============================================================
#
# Same concept, new data. Each time you see it in a new
# context, the neural circuit gets stronger.
#
# New variation: handling NaN at position [0]
# If the first row is NaN (missing), iloc[0] would give NaN,
# and dividing by NaN breaks everything.
# We use .bfill().iloc[0] — backfill first, then take row 0.

def normalize_to_100(df):
    """
    Rebase all columns to 100 at their first valid value.
    Handles NaN values at the start of series safely.
    """
    first_valid = df.bfill().iloc[0]   # backfill, then take first row
    return (df / first_valid) * 100


def normalize_to_100_safe(df):
    """Same but processes column by column for safety"""
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


if not equity_df.empty:
    equity_norm = normalize_to_100_safe(equity_df)

if not fred_daily_df.empty:
    fred_daily_norm = normalize_to_100_safe(fred_daily_df)

if not fred_monthly_df.empty:
    fred_monthly_norm = normalize_to_100_safe(fred_monthly_df)


# ============================================================
# SECTION 3: BUILD THE MASTER SUMMARY TABLE
# ============================================================
#
# This is the table that answers: "What happened, and when?"
# It becomes the evidence base for your confidence scores.
#
# Structure:
#   Layer | Asset | 14d move | 30d move | 60d move | Direction
#
# This table is the precursor to your Phase 1 JSON.
# Every row here = one step in the signal_chain array.

event_dt = pd.Timestamp(EVENT_DATE)

def get_nearest_date(df, target_date):
    available = df.index[df.index >= target_date]
    return available[0] if len(available) > 0 else None

def calculate_move(df, col, from_date, to_date):
    """Calculate % move between two dates for one column"""
    try:
        from_val = df.loc[from_date, col]
        to_val   = df.loc[to_date, col]
        if pd.isna(from_val) or pd.isna(to_val) or from_val == 0:
            return None
        return round(((to_val - from_val) / from_val) * 100, 2)
    except KeyError:
        return None


# Define assets and which DataFrame they live in
# Format: (label, DataFrame, column_name, layer, asset_class)
ASSET_MAP = [
    # Layer 2: Energy complex (daily — most responsive)
    ("WTI Crude Oil",
     fred_daily_df, "DCOILWTICO",
     2, "commodity_energy"),

    ("10Y-2Y Yield Spread (Macro Context)",
     fred_daily_df, "T10Y2Y",
     2, "macro_indicator"),

    # Layer 3: Shipping equities (daily)
    ("ZIM Integrated Shipping",
     equity_df, "ZIM",
     3, "shipping_equity"),

    ("Matson Inc",
     equity_df, "MATX",
     3, "shipping_equity"),

    ("Genco Shipping (Dry Bulk)",
     equity_df, "GNK",
     3, "shipping_equity"),

    ("Frontline (Tanker)",
     equity_df, "FRO",
     3, "shipping_equity"),

    # Layer 4: Freight rates (monthly — slower signal)
    ("Deep Sea Freight PPI",
     fred_monthly_df, "PCU483111483111",
     4, "freight_rate"),

    ("Natural Gas (LNG Proxy)",
     fred_monthly_df, "MHHNGSP",
     4, "commodity_energy"),

    # Layer 5: Agricultural commodities (monthly — slowest)
    ("Corn Price (Grain Trade)",
     fred_monthly_df, "PMAIZMTUSD",
     5, "commodity_agricultural"),

    ("Soybean Price (Grain Trade)",
     fred_monthly_df, "PSOYBUSDM",
     5, "commodity_agricultural"),
]

print("\n" + "=" * 70)
print("MASTER SIGNAL CHAIN — PANAMA CANAL DROUGHT 2023")
print(f"Event Date: {EVENT_DATE}")
print("=" * 70)
print(f"\n{'Layer':<6} {'Asset':<38} {'14d':>7} {'30d':>7} {'60d':>7} {'Signal'}")
print("-" * 70)

master_results = []

for (label, df, col, layer, asset_class) in ASSET_MAP:
    if df.empty or col not in df.columns:
        print(f"  {layer:<5} {label:<38} [NO DATA]")
        continue

    event_day = get_nearest_date(df, event_dt)
    day_14    = get_nearest_date(df, event_dt + pd.Timedelta(days=14))
    day_30    = get_nearest_date(df, event_dt + pd.Timedelta(days=30))
    day_60    = get_nearest_date(df, event_dt + pd.Timedelta(days=60))

    m14 = calculate_move(df, col, event_day, day_14)
    m30 = calculate_move(df, col, event_day, day_30)
    m60 = calculate_move(df, col, event_day, day_60)

    # Determine direction for signal chain
    if m30 is not None:
        direction = "UP" if m30 > 1 else ("DOWN" if m30 < -1 else "FLAT")
    else:
        direction = "N/A"

    # Format for display
    m14_str = f"{m14:+.1f}%" if m14 is not None else "N/A"
    m30_str = f"{m30:+.1f}%" if m30 is not None else "N/A"
    m60_str = f"{m60:+.1f}%" if m60 is not None else "N/A"

    print(f"L{layer:<5} {label:<38} {m14_str:>7} {m30_str:>7} {m60_str:>7}  {direction}")

    master_results.append({
        "layer":        layer,
        "asset":        label,
        "asset_class":  asset_class,
        "direction":    direction,
        "move_14d_pct": m14,
        "move_30d_pct": m30,
        "move_60d_pct": m60,
        "fred_series":  col if df is fred_daily_df or df is fred_monthly_df else None,
        "data_source":  "FRED" if df is fred_daily_df or df is fred_monthly_df else "yfinance"
    })

print("-" * 70)

# Save master results
master_df = pd.DataFrame(master_results)
master_df.to_csv("data/processed/master_signal_chain.csv", index=False)
print("\nSaved: data/processed/master_signal_chain.csv")
print("\n(This CSV is the raw evidence base for your Phase 1 JSON)")


# ============================================================
# SECTION 4: THE MASTER VISUALIZATION
# ============================================================
#
# This is the chart that makes the signal chain visible.
# Four panels, reading top to bottom = moving through the chain
# from fastest-responding to slowest-responding assets.
#
# Visual design principle:
#   - Vertical red line = event date (same on every panel)
#   - Horizontal gray line = 100 baseline (same on every panel)
#   - Top panels = faster signals (daily data, moves within days)
#   - Bottom panels = slower signals (monthly data, moves over weeks)
#
# When you look at this chart, you should see the disruption
# "travel" down from top to bottom over time — that lag
# structure IS the signal chain NAXA maps.

fig = plt.figure(figsize=(16, 18))
fig.suptitle(
    "NAXA — Panama Canal Drought 2023\nComplete Signal Chain: Event → Physical → Financial → Agricultural",
    fontsize=14,
    fontweight="bold",
    y=0.98
)

# GridSpec lets us control panel heights precisely
# 4 rows, heights proportional to data density
gs = gridspec.GridSpec(4, 1, figure=fig,
                       hspace=0.45,
                       height_ratios=[1.2, 1.5, 1.2, 1.2])

event_line = pd.Timestamp(EVENT_DATE)

def add_event_line(ax, label=True):
    ax.axvline(x=event_line, color="red", linestyle="--",
               linewidth=1.8,
               label="ACP Restriction (Aug 1 2023)" if label else "_nolegend_")
    ax.axhline(y=100, color="gray", linestyle=":", linewidth=1, alpha=0.4)
    ax.grid(True, alpha=0.25)

# ─── Panel 1: Macro Context (yield curve + WTI) ───────────────
ax1 = fig.add_subplot(gs[0])
daily_cols_to_plot = ["DCOILWTICO", "T10Y2Y"]
if not fred_daily_norm.empty:
    for col in daily_cols_to_plot:
        if col in fred_daily_norm.columns:
            label_map = {
                "DCOILWTICO": "WTI Crude Oil",
                "T10Y2Y": "10Y-2Y Yield Spread (macro context)"
            }
            ax1.plot(fred_daily_norm.index,
                     fred_daily_norm[col],
                     label=label_map.get(col, col),
                     linewidth=1.5)

add_event_line(ax1)
ax1.set_title("Layer 2 — Daily: Energy + Macro Context", fontsize=11)
ax1.set_ylabel("Index (100 = Jun 1 baseline)")
ax1.legend(loc="upper left", fontsize=8)

# ─── Panel 2: Shipping Equities ───────────────────────────────
ax2 = fig.add_subplot(gs[1])
shipping_to_plot = ["ZIM", "MATX", "GNK", "INSW", "DAC", "FRO"]
if not equity_norm.empty:
    for col in shipping_to_plot:
        if col in equity_norm.columns:
            ax2.plot(equity_norm.index,
                     equity_norm[col],
                     label=col,
                     linewidth=1.4)

add_event_line(ax2, label=False)
ax2.set_title("Layer 3 — Daily: Shipping Equities (normalized)", fontsize=11)
ax2.set_ylabel("Index (100 = Jun 1 baseline)")
ax2.legend(loc="upper left", fontsize=8, ncol=3)

# ─── Panel 3: Freight + Natural Gas (monthly) ─────────────────
ax3 = fig.add_subplot(gs[2])
monthly_energy = ["PCU483111483111", "MHHNGSP"]
if not fred_monthly_norm.empty:
    for col in monthly_energy:
        if col in fred_monthly_norm.columns:
            label_map = {
                "PCU483111483111": "Deep Sea Freight PPI",
                "MHHNGSP": "Natural Gas (LNG proxy)"
            }
            ax3.plot(fred_monthly_norm.index,
                     fred_monthly_norm[col],
                     label=label_map.get(col, col),
                     linewidth=2,
                     marker="o",
                     markersize=5)

add_event_line(ax3, label=False)
ax3.set_title("Layer 4 — Monthly: Freight PPI + Natural Gas", fontsize=11)
ax3.set_ylabel("Index (100 = Jun 1 baseline)")
ax3.legend(loc="upper left", fontsize=8)

# ─── Panel 4: Agricultural Commodities (monthly) ──────────────
ax4 = fig.add_subplot(gs[3])
monthly_agri = ["PMAIZMTUSD", "PSOYBUSDM"]
if not fred_monthly_norm.empty:
    for col in monthly_agri:
        if col in fred_monthly_norm.columns:
            label_map = {
                "PMAIZMTUSD": "Global Corn Price",
                "PSOYBUSDM":  "Global Soybean Price"
            }
            ax4.plot(fred_monthly_norm.index,
                     fred_monthly_norm[col],
                     label=label_map.get(col, col),
                     linewidth=2,
                     marker="s",
                     markersize=5)

add_event_line(ax4, label=False)
ax4.set_title("Layer 5 — Monthly: Agricultural Commodities", fontsize=11)
ax4.set_ylabel("Index (100 = Jun 1 baseline)")
ax4.set_xlabel("Date")
ax4.legend(loc="upper left", fontsize=8)

plt.savefig(
    "data/processed/master_signal_chain_chart.png",
    dpi=150,
    bbox_inches="tight"
)
plt.show()

print("\nMaster chart saved: data/processed/master_signal_chain_chart.png")
print("\n" + "=" * 70)
print("DAY 2 COMPLETE")
print("=" * 70)
print("\nWhat you now have:")
print("  data/raw/shipping_equities_raw.csv      ← Day 1 equity prices")
print("  data/raw/fred_daily_raw.csv             ← Day 2 FRED daily")
print("  data/raw/fred_monthly_raw.csv           ← Day 2 FRED monthly")
print("  data/processed/master_signal_chain.csv ← The evidence table")
print("  data/processed/master_signal_chain_chart.png ← The visual proof")
print("\nNext: Day 3 — research comparable historical events, build the n= table")
print("      That n= table is what converts raw moves into confidence scores.")