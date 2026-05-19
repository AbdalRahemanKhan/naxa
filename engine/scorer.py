# ============================================================
# NAXA Phase 2 — engine/scorer.py
#
# The Confidence Scoring Engine
# ============================================================
#
# WHAT THIS MODULE DOES:
#   Takes historical event observations and produces
#   statistically grounded confidence scores per signal.
#
# WHAT IT DOES NOT DO:
#   - It does not generate scores from an LLM
#   - It does not invent numbers
#   - Every score it produces cites n=, methodology, date range
#
# HOW IT RELATES TO PHASE 1:
#   This is a direct port of calculate_confidence.py.
#   The three core math functions are identical.
#   What changed:
#     - Imports from engine.events_db (not phase1/)
#     - Returns structured dicts instead of printing + saving
#     - Exposes one clean public function: score_all_signals()
#     - Correlator.py calls that function — it never touches
#       the internal math directly
#
# QUANT CONCEPT — Why this separation matters:
#   In quant shops, the "alpha engine" (signal generator) is
#   kept strictly separate from the "execution layer."
#   You never let the execution layer reach into the alpha
#   engine's internals. You expose a clean interface.
#   score_all_signals() is that interface.
# ============================================================

import math
from typing import Optional

from config import CONFIDENCE_FLOOR, CONFIDENCE_CEILING
from .events_db import EVENTS, DB_METADATA


# ============================================================
# SECTION 1: DATA QUALITY WEIGHTS
# ============================================================
#
# Not all historical data points are equal.
# A PRIMARY measurement from Drewry counts more than
# an ESTIMATED number inferred from press reports.
#
# QUANT CONCEPT — Quality-weighted average:
#   A simple average treats all observations equally.
#   A quality-weighted average trusts better data more.
#
#   Example with 3 observations of freight rate moves:
#     Event A: +28%, PRIMARY data    → weight 1.0
#     Event B: +19%, PARTIAL data    → weight 0.6
#     Event C: +22%, ESTIMATED data  → weight 0.4
#
#   Simple average:   (28 + 19 + 22) / 3          = 23.0%
#   Weighted average: (28×1.0 + 19×0.6 + 22×0.4)
#                   / (1.0 + 0.6 + 0.4)           = 24.5%
#
#   The PRIMARY observation gets more influence.
#   This is more honest than treating noise equally with signal.

QUALITY_WEIGHTS = {
    "PRIMARY":   1.0,
    "PARTIAL":   0.6,
    "ESTIMATED": 0.4,
}


# ============================================================
# SECTION 2: SIGNAL DEFINITIONS
# ============================================================
#
# These define WHAT we score and HOW we interpret direction.
# The "expected_direction" is what we predict will happen
# when a canal restriction occurs.
#
# Note: grain is listed as "UP" but its hit rate will come
# out low because empirically it moves both ways.
# That's not a bug — it's the engine correctly reflecting
# that grain is an unreliable signal for this event type.

SIGNAL_DEFINITIONS = [
    {
        "id":                 "container_freight_asia_usec",
        "name":               "Container Freight Rates Asia-USEC",
        "layer":              2,
        "expected_direction": "UP",
        "lags":               ["move_14d", "move_30d", "move_60d"],
    },
    {
        "id":                 "shipping_equities_container",
        "name":               "Container Shipping Equities",
        "layer":              3,
        "expected_direction": "UP",
        "lags":               ["move_14d", "move_30d", "move_60d"],
    },
    {
        "id":                 "shipping_equities_tanker",
        "name":               "Tanker Shipping Equities",
        "layer":              3,
        "expected_direction": "UP",
        "lags":               ["move_14d", "move_30d", "move_60d"],
    },
    {
        "id":                 "grain_prices_corn",
        "name":               "Corn / Grain Prices",
        "layer":              4,
        "expected_direction": "UP",
        "lags":               ["move_14d", "move_30d", "move_60d"],
    },
]


# ============================================================
# SECTION 3: CORE MATH FUNCTIONS
# ============================================================
#
# These three functions are the mathematical heart of NAXA.
# They are identical to Phase 1 — ported, not changed.
# If you change these, you change every confidence score
# in every output. Change them only with extreme care.

def _sample_size_factor(n: int) -> float:
    """
    Penalizes confidence scores for small sample sizes.
    Shrinks the score toward 0.5 (random chance) as n decreases.

    Formula: 1 - (1 / sqrt(n))

    Lookup table for intuition:
      n=1  → 0.00  (pure chance — one event proves nothing)
      n=2  → 0.29
      n=4  → 0.50  (our current n= — halfway to full confidence)
      n=9  → 0.67
      n=12 → 0.71  (target before removing ceiling cap)
      n=25 → 0.80
      n=100→ 0.90  (approaches but never reaches 1.0)

    The score never reaches 1.0. There is always uncertainty.
    This is intellectual honesty baked into the mathematics.
    """
    if n <= 0:
        return 0.0
    return 1.0 - (1.0 / math.sqrt(n))


def _magnitude_consistency(values: list) -> float:
    """
    Measures how consistent the SIZE of moves is across events.
    Complements hit_rate, which only measures direction.

    If freight rates always move +18% to +31%, that's a tight,
    predictable range — high consistency.
    If they move anywhere from +2% to +45%, that range is too
    wide to be actionable — low consistency.

    Formula: 1 - (std_dev / mean)
    This is the inverse of the Coefficient of Variation (CV).

    QUANT CONCEPT — Coefficient of Variation:
      CV = std_dev / mean
      Used in finance to compare volatility across assets
      with different price levels. A CV of 0.1 means the
      standard deviation is 10% of the mean — tight.
      A CV of 0.8 means the spread is almost as wide as
      the mean itself — noisy, low predictive value.
    """
    if len(values) < 2:
        return 0.5

    mean = sum(values) / len(values)
    if mean == 0:
        return 0.5

    variance = sum((v - mean) ** 2 for v in values) / len(values)
    std_dev  = math.sqrt(variance)
    cv       = std_dev / abs(mean)

    # Clip to [0, 1] — consistency can't be negative or above 1
    return round(max(0.0, min(1.0, 1.0 - cv)), 4)


def _calculate_score(
    observations: list,
    target_lag: str,
    expected_direction: str,
) -> dict:
    """
    Combines hit rate + magnitude consistency + sample size penalty
    into one final confidence score.

    Weighting rationale:
      60% hit rate:           direction accuracy matters most
      40% magnitude consistency: size predictability matters less
                                 but still informs usefulness

    Args:
        observations (list):       data points from historical events
        target_lag (str):          "move_14d", "move_30d", or "move_60d"
        expected_direction (str):  "UP" or "DOWN"

    Returns:
        dict: full confidence object with score + all supporting data
    """
    valid_moves   = []
    valid_weights = []
    weighted_hits = 0.0
    total_weight  = 0.0
    total         = 0

    for obs in observations:
        move = obs.get(target_lag)
        qual = obs.get("data_quality", "ESTIMATED")
        w    = QUALITY_WEIGHTS.get(qual, 0.4)

        if move is None:
            continue

        total        += 1
        total_weight += w
        valid_moves.append(move)
        valid_weights.append(w)

        if expected_direction == "UP"   and move > 0:
            weighted_hits += w
        elif expected_direction == "DOWN" and move < 0:
            weighted_hits += w

    # Not enough data — return floor with explanation
    if total == 0 or total_weight == 0:
        return {
            "score":       CONFIDENCE_FLOOR,
            "basis":       "insufficient_data",
            "n":           0,
            "hit_rate":    None,
            "mean_move_pct":  None,
            "move_range_pct": None,
            "methodology": "no_valid_observations",
        }

    # ── Core calculations ─────────────────────────────────────
    w_hit_rate  = weighted_hits / total_weight
    w_mean_move = sum(
        m * w for m, w in zip(valid_moves, valid_weights)
    ) / total_weight

    consistency = _magnitude_consistency(valid_moves)
    ss_factor   = _sample_size_factor(total)

    # Raw score: direction accuracy + magnitude consistency
    raw_score = (w_hit_rate * 0.6) + (consistency * 0.4)

    # Apply sample size penalty:
    # Interpolates between 0.5 (random) and raw_score
    # based on how much we trust our n=
    penalized = 0.5 + (raw_score - 0.5) * ss_factor

    # Clip to configured floor and ceiling
    final = max(CONFIDENCE_FLOOR, min(CONFIDENCE_CEILING, penalized))

    return {
        "score":                 round(final, 3),
        "raw_score":             round(raw_score, 3),
        "n":                     total,
        "hit_rate":              round(w_hit_rate, 3),
        "mean_move_pct":         round(w_mean_move, 2),
        "move_range_pct":        [
            round(min(valid_moves), 2),
            round(max(valid_moves), 2)
        ],
        "magnitude_consistency": round(consistency, 3),
        "sample_size_factor":    round(ss_factor, 3),
        "methodology": (
            "weighted_hit_rate_0.6_plus_magnitude_consistency_0.4"
            "_penalized_by_sample_size_factor"
        ),
        "basis": (
            f"backtested_n={total}_events_{DB_METADATA['date_range']}"
        ),
    }


# ============================================================
# SECTION 4: OBSERVATION COLLECTOR
# ============================================================
#
# Loops through all events in the database.
# For a given signal_id, collects all observations
# across all events into a flat list.
# That list then feeds into _calculate_score().

def _collect_observations(signal_id: str, events: dict) -> list:
    """
    Collects all historical data points for one signal ID.

    Args:
        signal_id (str): e.g. "container_freight_asia_usec"
        events (dict):   the EVENTS database

    Returns:
        list of dicts, one per event that has this signal
    """
    observations = []

    for event_id, event in events.items():
        chain = event.get("signal_chain", {})
        if signal_id not in chain:
            continue

        step = chain[signal_id]
        observations.append({
            "event_id":     event_id,
            "event_name":   event["meta"]["name"],
            "trigger_date": event["meta"]["trigger_date"],
            "severity":     event["meta"]["severity"]["score"],
            "move_14d":     step.get("move_14d"),
            "move_30d":     step.get("move_30d"),
            "move_60d":     step.get("move_60d"),
            "direction":    step.get("direction"),
            "data_quality": step.get("data_quality", "ESTIMATED"),
            "notes":        step.get("notes", ""),
        })

    return observations


# ============================================================
# SECTION 5: PUBLIC API
# ============================================================
#
# This is the only function correlator.py calls.
# It runs the full scoring engine and returns a structured dict.
#
# Everything above this line is internal implementation.
# Everything below this line is what the pipeline sees.

def score_all_signals(events: Optional[dict] = None) -> dict:
    """
    Scores all defined signals against the historical events database.

    Args:
        events (dict): override the default EVENTS database.
                       Used for testing. Defaults to engine/events_db.py.

    Returns:
        dict: {
            signal_id: {
                "signal_name": str,
                "layer": int,
                "n_events": int,
                "scores": {
                    "move_14d": {score_object},
                    "move_30d": {score_object},
                    "move_60d": {score_object},
                }
            }
        }
    """
    if events is None:
        events = EVENTS

    results = {}

    for signal_def in SIGNAL_DEFINITIONS:
        signal_id  = signal_def["id"]
        direction  = signal_def["expected_direction"]

        observations = _collect_observations(signal_id, events)

        scores_per_lag = {}
        for lag in signal_def["lags"]:
            scores_per_lag[lag] = _calculate_score(
                observations, lag, direction
            )

        results[signal_id] = {
            "signal_name": signal_def["name"],
            "layer":       signal_def["layer"],
            "n_events":    len(observations),
            "scores":      scores_per_lag,
        }

    return results


# ============================================================
# SECTION 6: SMOKE TEST
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("NAXA Scorer — Smoke Test")
    print("=" * 60)

    all_scores = score_all_signals()

    print(f"\n{'Signal':<38} {'n':>3}  {'14d':>6}  {'30d':>6}  {'60d':>6}")
    print("─" * 60)

    for signal_id, data in all_scores.items():
        s14 = data["scores"]["move_14d"]["score"]
        s30 = data["scores"]["move_30d"]["score"]
        s60 = data["scores"]["move_60d"]["score"]
        n   = data["n_events"]
        print(f"{data['signal_name']:<38} {n:>3}  "
              f"{s14:>6.3f}  {s30:>6.3f}  {s60:>6.3f}")

    print("─" * 60)
    print(f"\nNote: scores capped at {CONFIDENCE_CEILING} until n≥12")
    print("\n✓ Scorer operational")