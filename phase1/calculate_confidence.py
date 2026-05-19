# ============================================================
# NAXA Phase 1 — calculate_confidence.py
#
# The Confidence Score Engine
# Purpose: Read the historical events database and produce
#          statistically grounded confidence scores for each
#          signal chain step.
#
# Output:
#   - Terminal: formatted n= comparison table
#   - data/processed/confidence_scores.json
#   - data/processed/historical_events_table.csv
#
# KEY PRINCIPLE:
#   Confidence scores come from historical backtesting.
#   Never from LLM generation.
#   Every score ships with its n=, date range, and methodology.
# ============================================================

import json
import math
import os
import pandas as pd
from historical_events_db import EVENTS, DB_METADATA

os.makedirs("data/processed", exist_ok=True)


# ============================================================
# SECTION 1: DATA QUALITY WEIGHTS
# ============================================================
#
# Not all data points are equal. We weight by quality.
# A PRIMARY measurement from Drewry counts more than
# an ESTIMATED number inferred from press reports.
#
# This is the "quality-weighted average" concept.
# A simple average treats all observations equally.
# A quality-weighted average trusts better data more.
#
# Example:
#   Event A: freight rate +28%, PRIMARY data    → weight 1.0
#   Event B: freight rate +19%, PARTIAL data    → weight 0.6
#   Event C: freight rate +22%, ESTIMATED data  → weight 0.4
#
#   Simple average:   (28 + 19 + 22) / 3 = 23.0%
#   Weighted average: (28×1.0 + 19×0.6 + 22×0.4) / (1.0+0.6+0.4) = 24.5%
#
#   The PRIMARY observation gets more influence because we trust it more.

QUALITY_WEIGHTS = {
    "PRIMARY":   1.0,   # Direct measurement from authoritative source
    "PARTIAL":   0.6,   # Real data but significant confounders present
    "ESTIMATED": 0.4,   # Inferred or approximated from secondary sources
}


# ============================================================
# SECTION 2: SAMPLE SIZE PENALTY FUNCTION
# ============================================================
#
# This is the most important mathematical concept in the engine.
#
# The problem: with n=4 events, even if all four moved UP,
# that doesn't mean the 5th definitely will. Small samples
# can produce misleading patterns by chance.
#
# The solution: a sample size penalty that shrinks the score
# toward 0.5 (random chance) as n gets smaller.
#
# Formula: factor = 1 - (1 / sqrt(n))
#
# What this produces:
#   n=1  → factor = 0.00  → any score becomes 0.50 (pure chance)
#   n=2  → factor = 0.29  
#   n=4  → factor = 0.50  → score is halfway between raw and 0.50
#   n=9  → factor = 0.67
#   n=12 → factor = 0.71
#   n=25 → factor = 0.80
#   n=100→ factor = 0.90
#
# The score never reaches 1.0 — there is always uncertainty.
# This is intellectual honesty baked into the mathematics.

def sample_size_factor(n):
    """
    Returns a penalty factor based on sample size.
    Shrinks confidence toward 0.5 for small n.
    
    Args:
        n (int): number of historical observations
    Returns:
        float: factor between 0.0 and 1.0
    """
    if n <= 0:
        return 0.0
    return 1.0 - (1.0 / math.sqrt(n))


# ============================================================
# SECTION 3: MAGNITUDE CONSISTENCY FUNCTION
# ============================================================
#
# Hit rate tells you DIRECTION consistency.
# Magnitude consistency tells you SIZE consistency.
#
# If freight rates always move between +18% and +31%,
# that's a tight, predictable range → high consistency.
#
# If freight rates move anywhere from +2% to +45%,
# that range is too wide to be useful → low consistency.
#
# Formula: consistency = 1 - (std_dev / mean)
#   Called the "Coefficient of Variation" in statistics.
#   Lower CV = more consistent = higher score.
#
# We clip it to [0, 1] — it can't be negative or >1.

def magnitude_consistency(values):
    """
    Calculates how consistent a set of percentage moves are.
    
    Args:
        values (list): list of move percentages e.g. [28.4, 31.4, 18.7, 14.2]
    Returns:
        float: consistency score between 0.0 and 1.0
    """
    if len(values) < 2:
        return 0.5   # Not enough data to assess consistency
    
    mean = sum(values) / len(values)
    
    if mean == 0:
        return 0.5   # Division by zero protection
    
    # Standard deviation: measures average distance from mean
    # Higher std dev = more spread = less consistent
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std_dev = math.sqrt(variance)
    
    # Coefficient of variation: std_dev as % of mean
    cv = std_dev / abs(mean)
    
    # Convert to consistency score: 1 - CV, clipped to [0, 1]
    consistency = max(0.0, min(1.0, 1.0 - cv))
    
    return round(consistency, 4)


# ============================================================
# SECTION 4: CORE CONFIDENCE SCORE CALCULATOR
# ============================================================
#
# Combines hit rate + magnitude consistency + sample size penalty
# into one final score for a given signal at a given lag.

def calculate_confidence_score(
    observations,       # list of dicts: {move, direction, quality}
    target_lag,         # "move_14d", "move_30d", or "move_60d"
    expected_direction  # "UP" or "DOWN"
):
    """
    Calculates a confidence score for one signal chain step.
    
    Args:
        observations (list): data points from historical events
        target_lag (str):    which lag to analyze
        expected_direction:  what direction we predict
    
    Returns:
        dict: full confidence object with score + supporting metadata
    """
    
    valid_moves  = []   # move values where data exists
    valid_weights = []  # quality weights for those moves
    hits         = 0    # count of events where direction was correct
    total        = 0    # count of events where we had valid data
    weighted_hits = 0.0 # quality-weighted hit count
    total_weight  = 0.0 # sum of quality weights
    
    for obs in observations:
        move  = obs.get(target_lag)
        qual  = obs.get("data_quality", "ESTIMATED")
        w     = QUALITY_WEIGHTS.get(qual, 0.4)
        
        # Skip None values (missing data for this lag/event)
        if move is None:
            continue
        
        total        += 1
        total_weight += w
        
        valid_moves.append(move)
        valid_weights.append(w)
        
        # Check if direction was correct
        if expected_direction == "UP"   and move > 0:
            hits          += 1
            weighted_hits += w
        elif expected_direction == "DOWN" and move < 0:
            hits          += 1
            weighted_hits += w
    
    # Not enough data — return minimum confidence
    if total == 0 or total_weight == 0:
        return {
            "score":       DB_METADATA["confidence_floor"],
            "basis":       "insufficient_data",
            "n":           0,
            "hit_rate":    None,
            "mean_move":   None,
            "move_range":  None,
            "methodology": "no_valid_observations"
        }
    
    # --- Calculate components ---
    
    # Weighted hit rate
    w_hit_rate = weighted_hits / total_weight
    
    # Quality-weighted average move
    w_mean_move = sum(
        m * w for m, w in zip(valid_moves, valid_weights)
    ) / total_weight
    
    # Magnitude consistency (uses raw moves, not weighted)
    consistency = magnitude_consistency(valid_moves)
    
    # Sample size penalty
    ss_factor = sample_size_factor(total)
    
    # Raw score before penalty
    raw_score = (w_hit_rate * 0.6) + (consistency * 0.4)
    # 60% weight on direction accuracy, 40% on magnitude consistency
    # Rationale: getting direction right matters more than exact magnitude
    
    # Apply sample size penalty
    # Interpolates between 0.5 (random) and raw_score based on n
    penalized_score = 0.5 + (raw_score - 0.5) * ss_factor
    
    # Clip to configured floor and ceiling
    floor   = DB_METADATA["confidence_floor"]
    ceiling = DB_METADATA["confidence_ceiling"]
    final_score = max(floor, min(ceiling, penalized_score))
    
    return {
        "score":           round(final_score, 3),
        "raw_score":       round(raw_score, 3),
        "n":               total,
        "hit_rate":        round(w_hit_rate, 3),
        "weighted_hit_rate": round(w_hit_rate, 3),
        "mean_move_pct":   round(w_mean_move, 2),
        "move_range_pct":  [round(min(valid_moves), 2), round(max(valid_moves), 2)],
        "magnitude_consistency": round(consistency, 3),
        "sample_size_factor":    round(ss_factor, 3),
        "data_quality_mix":      {
            q: observations.count(
                next((o for o in observations if o.get("data_quality") == q), {})
            ) for q in QUALITY_WEIGHTS
        },
        "methodology":     "weighted_hit_rate_0.6_plus_magnitude_consistency_0.4_"
                           "penalized_by_sample_size_factor",
        "basis":           f"backtested_n={total}_events_{DB_METADATA['date_range']}"
    }


# ============================================================
# SECTION 5: EXTRACT OBSERVATIONS PER SIGNAL
# ============================================================
#
# Loops through all events in the database.
# For each signal chain step (freight rates, equities, etc.),
# collects all observations across events into a flat list.
# Then passes that list to calculate_confidence_score().

SIGNAL_DEFINITIONS = [
    {
        "id":                "container_freight_asia_usec",
        "name":              "Container Freight Rates Asia-USEC",
        "layer":             2,
        "expected_direction": "UP",
        "lags":              ["move_14d", "move_30d", "move_60d"]
    },
    {
        "id":                "shipping_equities_container",
        "name":              "Container Shipping Equities",
        "layer":             3,
        "expected_direction": "UP",
        "lags":              ["move_14d", "move_30d", "move_60d"]
    },
    {
        "id":                "shipping_equities_tanker",
        "name":              "Tanker Shipping Equities",
        "layer":             3,
        "expected_direction": "UP",
        "lags":              ["move_14d", "move_30d", "move_60d"]
    },
    {
        "id":                "grain_prices_corn",
        "name":              "Corn / Grain Prices",
        "layer":             4,
        "expected_direction": "UP",
        # Historically mixed — testing UP direction to see hit rate
        "lags":              ["move_14d", "move_30d", "move_60d"]
    }
]


def collect_observations(signal_id):
    """
    Collects all historical observations for one signal ID
    across all events in the database.
    
    Returns:
        list of dicts, one per event that has data for this signal
    """
    observations = []
    for event_id, event in EVENTS.items():
        chain = event.get("signal_chain", {})
        if signal_id not in chain:
            continue
        step = chain[signal_id]
        obs = {
            "event_id":     event_id,
            "event_name":   event["meta"]["name"],
            "trigger_date": event["meta"]["trigger_date"],
            "severity":     event["meta"]["severity"]["score"],
            "move_14d":     step.get("move_14d"),
            "move_30d":     step.get("move_30d"),
            "move_60d":     step.get("move_60d"),
            "direction":    step.get("direction"),
            "data_quality": step.get("data_quality", "ESTIMATED"),
            "notes":        step.get("notes", "")
        }
        observations.append(obs)
    return observations


# ============================================================
# SECTION 6: RUN THE ENGINE + PRINT THE n= TABLE
# ============================================================

print("=" * 70)
print("NAXA Phase 1 — Confidence Score Engine")
print(f"Database: {DB_METADATA['n_events']} events, {DB_METADATA['date_range']}")
print("=" * 70)

all_confidence_scores = {}
table_rows = []

for signal_def in SIGNAL_DEFINITIONS:
    signal_id  = signal_def["id"]
    signal_name = signal_def["name"]
    layer      = signal_def["layer"]
    direction  = signal_def["expected_direction"]
    
    observations = collect_observations(signal_id)
    
    print(f"\n{'─' * 70}")
    print(f"SIGNAL: {signal_name}  [Layer {layer}]")
    print(f"Expected direction: {direction}")
    print(f"Events with data:   {len(observations)}")
    print()
    
    # Print the raw observation table — this is the n= table
    print(f"  {'Event':<35} {'Sev':>5} {'14d':>8} {'30d':>8} {'60d':>8} {'Quality'}")
    print(f"  {'─'*35} {'─'*5} {'─'*8} {'─'*8} {'─'*8} {'─'*8}")
    
    for obs in observations:
        m14 = f"{obs['move_14d']:+.1f}%" if obs['move_14d'] is not None else "N/A"
        m30 = f"{obs['move_30d']:+.1f}%" if obs['move_30d'] is not None else "N/A"
        m60 = f"{obs['move_60d']:+.1f}%" if obs['move_60d'] is not None else "N/A"
        print(f"  {obs['event_name']:<35} {obs['severity']:>5.2f} "
              f"{m14:>8} {m30:>8} {m60:>8}  {obs['data_quality']}")
    
    # Calculate confidence for each lag
    scores_for_signal = {}
    
    for lag in signal_def["lags"]:
        score_obj = calculate_confidence_score(observations, lag, direction)
        scores_for_signal[lag] = score_obj
        lag_label = lag.replace("move_", "").replace("_", " ")
        
        print(f"\n  {lag_label} confidence score: {score_obj['score']}")
        if score_obj.get("n", 0) > 0:
            print(f"    Hit rate:     {score_obj['hit_rate']:.1%} "
                  f"({score_obj['n']} events)")
            print(f"    Mean move:    {score_obj['mean_move_pct']:+.1f}%")
            print(f"    Move range:   {score_obj['move_range_pct'][0]:+.1f}% "
                  f"to {score_obj['move_range_pct'][1]:+.1f}%")
            print(f"    Consistency:  {score_obj['magnitude_consistency']:.2f}")
            print(f"    n= penalty:   {score_obj['sample_size_factor']:.2f}")
    
    all_confidence_scores[signal_id] = {
        "signal_name":  signal_name,
        "layer":        layer,
        "direction":    direction,
        "n_events":     len(observations),
        "scores":       scores_for_signal
    }
    
    # Flatten for CSV export
    for obs in observations:
        table_rows.append({
            "signal":       signal_name,
            "layer":        layer,
            "event":        obs["event_name"],
            "trigger_date": obs["trigger_date"],
            "severity":     obs["severity"],
            "move_14d":     obs["move_14d"],
            "move_30d":     obs["move_30d"],
            "move_60d":     obs["move_60d"],
            "data_quality": obs["data_quality"]
        })


# ============================================================
# SECTION 7: PRINT THE KEY INSIGHT TABLE
# ============================================================
#
# This table is the most important output of Day 3.
# It's the raw evidence that every NAXA confidence score
# traces back to. Print it clearly.

print("\n\n" + "=" * 70)
print("CONFIDENCE SCORE SUMMARY — PHASE 1 BASELINE")
print("=" * 70)
print(f"\n{'Signal':<38} {'L':>3} {'14d Score':>10} {'30d Score':>10} {'60d Score':>10} {'n':>4}")
print("─" * 70)

for signal_id, data in all_confidence_scores.items():
    s14 = data["scores"].get("move_14d", {}).get("score", "N/A")
    s30 = data["scores"].get("move_30d", {}).get("score", "N/A")
    s60 = data["scores"].get("move_60d", {}).get("score", "N/A")
    n   = data["n_events"]
    l   = data["layer"]
    name = data["signal_name"][:37]
    
    s14_str = f"{s14:.3f}" if isinstance(s14, float) else s14
    s30_str = f"{s30:.3f}" if isinstance(s30, float) else s30
    s60_str = f"{s60:.3f}" if isinstance(s60, float) else s60
    
    print(f"{name:<38} {l:>3} {s14_str:>10} {s30_str:>10} {s60_str:>10} {n:>4}")

print("─" * 70)
print(f"\nNote: Scores penalized for n={DB_METADATA['n_events']}. "
      f"Max score capped at {DB_METADATA['confidence_ceiling']} until n≥12.")


# ============================================================
# SECTION 8: SAVE OUTPUTS
# ============================================================

# Save full confidence scores as JSON
output = {
    "naxa_version":     "0.1.0",
    "generated_from":   "calculate_confidence.py",
    "db_metadata":      DB_METADATA,
    "confidence_scores": all_confidence_scores
}

with open("data/processed/confidence_scores.json", "w") as f:
    json.dump(output, f, indent=2)

print("\nSaved: data/processed/confidence_scores.json")

# Save flat table as CSV for human review
table_df = pd.DataFrame(table_rows)
table_df.to_csv("data/processed/historical_events_table.csv", index=False)
print("Saved: data/processed/historical_events_table.csv")

print("\n" + "=" * 70)
print("DAY 3 COMPLETE")
print("=" * 70)
print("\nWhat you now have:")
print("  Backtested confidence scores for 4 signal chain steps")
print("  Each score has: n=, hit rate, mean move, range, methodology")
print("  This is the intellectual foundation of NAXA's JSON output")
print("\nNext: Day 4 — hand-build the Gold Standard JSON using")
print("      everything you've measured across Days 1, 2, and 3.")