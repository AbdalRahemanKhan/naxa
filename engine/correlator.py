# ============================================================
# NAXA Phase 2 — engine/correlator.py
#
# The Signal Chain Correlator
# ============================================================
#
# WHAT THIS MODULE DOES:
#   This is the only genuinely new logic in Phase 2.
#   Every other module was ported or wrapped from Phase 1.
#   The correlator is where the pipeline becomes intelligent.
#
#   It takes an event description (type, date, severity)
#   and returns a fully assembled signal chain —
#   measured moves from live data, historical context from
#   the events database, and confidence scores from the scorer.
#
# THE THREE LAYERS IT CONNECTS:
#
#   [ingestor]  →  raw price DataFrames
#   [scorer]    →  confidence scores per signal
#   [events_db] →  historical move ranges + precedents
#         ↓
#   [correlator] assembles all three into signal_chain list
#         ↓
#   [analyze.py] wraps it in the full Gold Standard JSON
#
# QUANT CONCEPT — What "correlation" means here:
#   In finance, correlation = how two assets move together.
#   Here we use it differently: we're correlating an EVENT
#   to its downstream EFFECTS across asset classes.
#   This is "event-driven analysis" — a core strategy used
#   by macro hedge funds to identify cross-asset moves
#   triggered by a single causal event.
#   NAXA automates what a macro analyst does manually.
# ============================================================

import pandas as pd
from datetime import datetime, timedelta
from typing import Optional

from config import (
    SHIPPING_TICKERS,
    FRED_SERIES,
)
from engine.ingestor import fetch_equities, fetch_fred
from engine.scorer import score_all_signals
from .events_db import EVENTS, DB_METADATA


# ============================================================
# SECTION 1: SIGNAL → ASSET MAPPING
# ============================================================
#
# This map answers: "for each signal in our chain,
# which live data source measures it?"
#
# QUANT CONCEPT — Data proxies:
#   Ideal data and available data are rarely the same thing.
#   Drewry WCI is the ideal freight rate source — but it's
#   paywalled. FRED's Deep Sea Freight PPI is a proxy:
#   it measures the same underlying phenomenon (freight cost)
#   through a different lens (producer price index).
#   Professional quants use proxies constantly.
#   The key discipline: always flag when you're using a proxy
#   so the consumer of your data knows the limitation.
#
# Structure per signal:
#   layer        → where in the causal chain (1=event, 5=slowest)
#   asset_class  → what type of instrument
#   data_source  → "equity" | "fred_daily" | "fred_monthly" | "none"
#   tickers      → for equity signals: list of Yahoo Finance tickers
#   fred_series  → for FRED signals: the series ID
#   is_proxy     → True if this is not the ideal data source
#   proxy_note   → explains what the ideal source would be
#   direction    → expected direction for canal restriction events
#   lag_days     → expected lag from event to signal response

SIGNAL_ASSET_MAP = {

    "container_freight_asia_usec": {
        "layer":       2,
        "asset":       "Deep Sea Freight PPI (Drewry WCI proxy)",
        "asset_class": "freight_rate",
        "data_source": "fred_monthly",
        "fred_series": "PCU483111483111",
        "is_proxy":    True,
        "proxy_note":  "Ideal source is Drewry WCI (paywalled). "
                       "FRED PCU483111483111 is PPI: Deep Sea Freight — "
                       "measures same cost signal, monthly frequency.",
        "direction":   "UP",
        "lag_days":    12,
    },

    "shipping_equities_container": {
        "layer":       3,
        "asset":       "Container Shipping Equities",
        "asset_class": "equity",
        "data_source": "equity",
        "tickers":     ["ZIM", "MATX", "DAC"],
        "is_proxy":    False,
        "proxy_note":  None,
        "direction":   "MIXED",
        "lag_days":    7,
    },

    "shipping_equities_tanker": {
        "layer":       3,
        "asset":       "Tanker Shipping Equities",
        "asset_class": "equity",
        "data_source": "equity",
        "tickers":     ["FRO", "INSW"],
        "is_proxy":    False,
        "proxy_note":  None,
        "direction":   "UP",
        "lag_days":    10,
    },

    "grain_prices_corn": {
        "layer":       4,
        "asset":       "Global Soybean Price (grain proxy)",
        "asset_class": "commodity_agricultural",
        "data_source": "fred_monthly",
        "fred_series": "PSOYBUSDM",
        # Using soybean — corn series PMAIZMTUSD returns 400 on FRED
        # Soybean (PSOYBUSDM) is a valid grain trade proxy:
        # both travel the same routes, both affected by canal capacity
        "is_proxy":    True,
        "proxy_note":  "Corn series PMAIZMTUSD unavailable via FRED free tier. "
                       "Soybean (PSOYBUSDM) used as grain trade proxy — "
                       "both commodities use the same shipping routes.",
        "direction":   "MIXED",
        "lag_days":    45,
    },
}


# ============================================================
# SECTION 2: DATE UTILITIES
# ============================================================
#
# Canal events have specific timing requirements.
# We need data before and after the event date.
# These helpers handle the date arithmetic cleanly.

def _parse_event_date(event_date_str: str) -> pd.Timestamp:
    """
    Converts event date string to pandas Timestamp.
    Validates format — fails loudly if wrong.

    Args:
        event_date_str (str): "YYYY-MM-DD"

    Returns:
        pd.Timestamp
    """
    try:
        return pd.Timestamp(event_date_str)
    except Exception:
        raise ValueError(
            f"Invalid event_date: '{event_date_str}'. "
            f"Required format: 'YYYY-MM-DD'"
        )


def _get_nearest_date(df: pd.DataFrame, target: pd.Timestamp) -> Optional[pd.Timestamp]:
    """
    Finds the nearest available date in a DataFrame index
    that is >= target date.

    WHY THIS EXISTS:
        Markets are closed on weekends and holidays.
        If event_date + 14 days lands on a Sunday,
        there's no price data. We take the next
        available trading day instead.
        This is standard practice in backtesting.
    """
    available = df.index[df.index >= target]
    return available[0] if len(available) > 0 else None


def _calculate_move(
    df: pd.DataFrame,
    col: str,
    from_date: pd.Timestamp,
    to_date: pd.Timestamp,
) -> Optional[float]:
    """
    Calculates % price move between two dates for one column.

    Returns:
        float: percentage move e.g. 12.4 means +12.4%
        None:  if data is missing at either date
    """
    try:
        from_val = df.loc[from_date, col]
        to_val   = df.loc[to_date, col]

        if pd.isna(from_val) or pd.isna(to_val) or from_val == 0:
            return None

        return round(((to_val - from_val) / from_val) * 100, 2)

    except KeyError:
        return None


# ============================================================
# SECTION 3: HISTORICAL CONTEXT RETRIEVER
# ============================================================
#
# For each signal, pulls the historical move ranges and
# precedent events from events_db.
# This becomes the "expected" block in the signal chain step.

def _get_historical_context(signal_id: str) -> dict:
    """
    Retrieves historical move ranges and precedent events
    for a given signal from the events database.

    This is how we tell the user: "historically, when this
    type of event occurred, this signal moved X% to Y%."

    Returns:
        dict with expected_move_range, precedents, n_events
    """
    moves_30d  = []
    precedents = []

    for event_id, event in EVENTS.items():
        chain = event.get("signal_chain", {})
        if signal_id not in chain:
            continue

        step     = chain[signal_id]
        move_30d = step.get("move_30d")
        severity = event["meta"]["severity"]["score"]

        if move_30d is not None:
            moves_30d.append(move_30d)
            precedents.append({
                "event":    event_id,
                "move_30d": move_30d,
                "severity": severity,
            })

    if not moves_30d:
        return {
            "expected_move_range": None,
            "mean_move_pct":       None,
            "precedents":          [],
            "n_events":            0,
        }

    return {
        "expected_move_range": f"{min(moves_30d):+.1f}% to {max(moves_30d):+.1f}%",
        "mean_move_pct":       round(sum(moves_30d) / len(moves_30d), 1),
        "precedents":          precedents,
        "n_events":            len(precedents),
    }


# ============================================================
# SECTION 4: MEASURED MOVES CALCULATOR
# ============================================================
#
# Pulls live data and calculates actual measured moves
# for each signal at 14d, 30d, 60d lags.
#
# QUANT CONCEPT — Measured vs Expected:
#   "Expected" = what historical patterns predict will happen
#   "Measured" = what actually happened in the live data
#
#   For a PAST event (like Panama 2023):
#     Both measured and expected will exist.
#     You can compare them — this is backtesting validation.
#
#   For a FUTURE event (real-time query in Phase 3):
#     Only expected will exist until enough time passes
#     for the lags to resolve.
#
#   NAXA's job is to provide both so the analyst can judge
#   whether the live event is tracking historical patterns.

def _calculate_measured_moves(
    signal_id:    str,
    signal_map:   dict,
    equity_df:    pd.DataFrame,
    fred_daily:   pd.DataFrame,
    fred_monthly: pd.DataFrame,
    event_date:   pd.Timestamp,
) -> dict:
    """
    Calculates measured moves at 14d, 30d, 60d for one signal.

    Returns:
        dict with move_14d, move_30d, move_60d, and data_availability
    """
    cfg         = signal_map[signal_id]
    data_source = cfg["data_source"]

    # Select the right DataFrame for this signal
    if data_source == "equity":
        df = equity_df

    elif data_source == "fred_daily":
        df = fred_daily

    elif data_source == "fred_monthly":
        df = fred_monthly

    else:
        return {"move_14d": None, "move_30d": None, "move_60d": None,
                "data_available": False, "note": "no_data_source_configured"}

    if df is None or df.empty:
        return {"move_14d": None, "move_30d": None, "move_60d": None,
                "data_available": False, "note": "data_pull_returned_empty"}

    # Find nearest available dates for each lag
    event_day = _get_nearest_date(df, event_date)
    day_14    = _get_nearest_date(df, event_date + pd.Timedelta(days=14))
    day_30    = _get_nearest_date(df, event_date + pd.Timedelta(days=30))
    day_60    = _get_nearest_date(df, event_date + pd.Timedelta(days=60))

    if event_day is None:
        return {"move_14d": None, "move_30d": None, "move_60d": None,
                "data_available": False,
                "note": "event_date_not_in_data_range"}

    # For equity signals: average move across all tickers in the group
    if data_source == "equity":
        tickers = [t for t in cfg.get("tickers", []) if t in df.columns]

        moves = {}
        for lag_label, lag_date in [("move_14d", day_14),
                                     ("move_30d", day_30),
                                     ("move_60d", day_60)]:
            if lag_date is None:
                moves[lag_label] = None
                continue

            lag_moves = [
                _calculate_move(df, t, event_day, lag_date)
                for t in tickers
            ]
            # Average only non-None values
            valid = [m for m in lag_moves if m is not None]
            moves[lag_label] = round(sum(valid) / len(valid), 2) if valid else None

        moves["data_available"] = any(v is not None for v in moves.values())
        moves["tickers_used"]   = tickers
        return moves

    # For FRED signals: single series move
    else:
        series_id = cfg.get("fred_series")
        if series_id not in df.columns:
            return {"move_14d": None, "move_30d": None, "move_60d": None,
                    "data_available": False,
                    "note": f"series_{series_id}_not_in_dataframe"}

        moves = {}
        for lag_label, lag_date in [("move_14d", day_14),
                                     ("move_30d", day_30),
                                     ("move_60d", day_60)]:
            moves[lag_label] = (
                _calculate_move(df, series_id, event_day, lag_date)
                if lag_date else None
            )

        moves["data_available"] = any(v is not None for v in moves.values())
        moves["fred_series"]    = series_id
        return moves


# ============================================================
# SECTION 5: SIGNAL CHAIN ASSEMBLER
# ============================================================
#
# The core public function. Orchestrates all the above.

def build_signal_chain(
    event_type:     str,
    event_date:     str,
    severity_score: float,
) -> list:
    """
    Builds the complete signal chain for a given event.

    This is the function analyze.py calls.
    It orchestrates ingestor → scorer → historical context
    into a structured signal_chain list matching the
    Gold Standard JSON schema.

    Args:
        event_type     (str):   e.g. "canal_restriction"
        event_date     (str):   "YYYY-MM-DD"
        severity_score (float): 0.0–1.0

    Returns:
        list: signal_chain array ready for Gold Standard JSON
    """
    print(f"\n[Correlator] Building signal chain...")
    print(f"[Correlator] Event: {event_type} | "
          f"Date: {event_date} | Severity: {severity_score}")

    event_ts = _parse_event_date(event_date)

    # ── Step 1: Define data pull window ───────────────────────
    # Pull from 90 days before event to 90 days after
    # 90 days before: captures the pre-event baseline
    # 90 days after:  captures the full 60d lag window + buffer
    pull_start = (event_ts - pd.Timedelta(days=90)).strftime("%Y-%m-%d")
    pull_end   = (event_ts + pd.Timedelta(days=90)).strftime("%Y-%m-%d")

    print(f"[Correlator] Data window: {pull_start} → {pull_end}")

    # ── Step 2: Pull live data ─────────────────────────────────
    print("[Correlator] Pulling live data...")

    equity_df = fetch_equities(SHIPPING_TICKERS, pull_start, pull_end)

    fred_daily, fred_monthly = fetch_fred(
        FRED_SERIES, pull_start, pull_end
    )

    # ── Step 3: Get confidence scores ─────────────────────────
    print("[Correlator] Scoring signals...")
    all_scores = score_all_signals()

    # ── Step 4: Assemble signal chain ─────────────────────────
    signal_chain = []

    for signal_id, cfg in SIGNAL_ASSET_MAP.items():

        print(f"[Correlator]   Processing: {signal_id}")

        # Get measured moves from live data
        measured = _calculate_measured_moves(
            signal_id, SIGNAL_ASSET_MAP,
            equity_df, fred_daily, fred_monthly,
            event_ts,
        )

        # Get historical context (expected ranges)
        historical = _get_historical_context(signal_id)

        # Get confidence scores for 30d (primary lag)
        scores     = all_scores.get(signal_id, {})
        score_30d  = scores.get("scores", {}).get("move_30d", {})
        score_14d  = scores.get("scores", {}).get("move_14d", {})
        score_60d  = scores.get("scores", {}).get("move_60d", {})

        # Assemble the step
        step = {
            "layer":       cfg["layer"],
            "step_id":     signal_id,
            "asset":       cfg["asset"],
            "asset_class": cfg["asset_class"],
            "direction":   cfg["direction"],

            "measured": {
                "move_14d_pct":    measured.get("move_14d"),
                "move_30d_pct":    measured.get("move_30d"),
                "move_60d_pct":    measured.get("move_60d"),
                "data_available":  measured.get("data_available", False),
                "data_source":     cfg["data_source"],
                "is_proxy":        cfg["is_proxy"],
                "proxy_note":      cfg["proxy_note"],
            },

            "expected": {
                "move_range":    historical["expected_move_range"],
                "mean_move_pct": historical["mean_move_pct"],
                "lag_days":      cfg["lag_days"],
                "n_events":      historical["n_events"],
                "precedents":    historical["precedents"],
            },

            "confidence": {
                "score_14d": score_14d.get("score"),
                "score_30d": score_30d.get("score"),
                "score_60d": score_60d.get("score"),
                "n":         score_30d.get("n"),
                "hit_rate":  score_30d.get("hit_rate"),
                "basis":     score_30d.get("basis"),
                "methodology": score_30d.get("methodology"),
            },
        }

        signal_chain.append(step)

    # Sort by layer so the chain reads causally: L2 → L3 → L4
    signal_chain.sort(key=lambda x: x["layer"])

    print(f"[Correlator] ✓ Signal chain built: "
          f"{len(signal_chain)} steps")

    return signal_chain


# ============================================================
# SECTION 6: SMOKE TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("NAXA Correlator — Smoke Test")
    print("=" * 60)

    chain = build_signal_chain(
        event_type     = "canal_restriction",
        event_date     = "2023-08-01",
        severity_score = 0.85,
    )

    print(f"\n{'─' * 60}")
    print(f"{'Step':<35} {'L':>3}  {'30d':>7}  {'Conf':>6}  {'Exp Range'}")
    print(f"{'─' * 60}")

    for step in chain:
        m30  = step["measured"]["move_30d_pct"]
        conf = step["confidence"]["score_30d"]
        exp  = step["expected"]["move_range"] or "N/A"

        m30_str  = f"{m30:+.1f}%" if m30  is not None else "N/A"
        conf_str = f"{conf:.3f}"  if conf is not None else "N/A"

        print(f"{step['step_id']:<35} {step['layer']:>3}  "
              f"{m30_str:>7}  {conf_str:>6}  {exp}")

    print(f"{'─' * 60}")
    print(f"\n✓ Correlator operational — {len(chain)} signals processed")