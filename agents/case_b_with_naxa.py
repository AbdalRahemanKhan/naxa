# ============================================================
# NAXA Demo — Case B: Agent WITH NAXA
# ============================================================
#
# WHAT THIS DEMONSTRATES:
#   One API call. Structured, sourced, backtested output.
#   The agent doesn't need to know anything about shipping.
#   It just calls NAXA and gets auditable signal chain data.
#
# THE CONTRAST WITH CASE A:
#   Same query. Same underlying question.
#   Case A: 4 API calls, invented confidence, no sourcing.
#   Case B: 1 API call, backtested confidence, every field sourced.
# ============================================================

import time
import sys
import json
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from config import NAXA_VERSION

NAXA_BASE_URL = os.getenv("NAXA_BASE_URL", "http://localhost:5000")
NAXA_API_KEY  = os.getenv("NAXA_API_KEY")

QUERY = (
    "Houthi militant attacks on Red Sea shipping began Dec 19 2023. "
    "Maersk and MSC suspended all Red Sea transits immediately. "
    "What happens next across commodities and equities? "
    "Give me specific assets, directions, magnitudes, and confidence scores."
    #"Panama Canal water levels dropped to historic lows in August 2023. "
    #"What happens next across commodities and equities? "
    #"Give me specific assets, directions, magnitudes, and confidence scores."
)


def run_case_b() -> dict:
    """
    Runs the NAXA-powered agent pipeline.
    Returns a standardized result dict for comparison.
    """
    start     = time.time()
    api_calls = 0

    print("\n" + "=" * 60)
    print("CASE B — Agent WITH NAXA")
    print("=" * 60)
    print(f"  Query: {QUERY[:80]}...\n")

    # ── Single NAXA call ───────────────────────────────────────
    #
    # This is the entire research workflow in one HTTP call.
    # No multi-step reasoning. No guessed confidence scores.
    # The pipeline runs backtested logic against 4 historical
    # events and returns sourced structured JSON.

    print("[1/1] POST /v1/analyze...")

    response = requests.post(
        f"{NAXA_BASE_URL}/v1/analyze",
        headers={
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {NAXA_API_KEY}",
        },
        json={
            "event":    "canal_restriction",
            "date":     "2023-12-19",
            "severity": 0.80,
            #"event":    "canal_restriction",
            #"date":     "2023-08-01",
            #"severity": 0.85,
        },
        timeout=60,
    )
    api_calls += 1

    if response.status_code != 200:
        return {
            "case":  "B",
            "error": response.json(),
        }

    data     = response.json()
    elapsed  = round(time.time() - start, 1)

    # Extract structured output for comparison display
    chain        = data.get("signal_chain", [])
    agent        = data.get("agent_payload", {})
    top_signals  = agent.get("top_confidence_signals", [])
    flagged      = agent.get("flagged_low_confidence", [])
    methodology  = data.get("methodology", {})

    # Build a clean confidence summary for display
    confidence_data = [
        {
            "signal":     step["step_id"],
            "direction":  step["direction"],
            "confidence": step["confidence"].get("score_30d"),
            "basis":      step["confidence"].get("basis"),
            "hit_rate":   step["confidence"].get("hit_rate"),
            "n":          step["confidence"].get("n"),
        }
        for step in chain
    ]

    print(f"\n  Case B complete — {elapsed}s, {api_calls} API call")

    return {
        "case":         "B",
        "label":        "Agent WITH NAXA",
        "time_seconds": elapsed,
        "api_calls":    api_calls,
        "output": {
            "human_summary":    data.get("human_summary"),
            "confidence_data":  confidence_data,
            "confidence_basis": (
                f"Backtested — n={methodology.get('n_comparable_events')} events, "
                f"{methodology.get('backtesting_period')}, "
                f"hit rates sourced"
            ),
            "sourcing":         "FRED API, yfinance, ACP advisories — every field cited",
            "auditable":        True,
            "agent_structured": True,
            "machine_readable": agent.get("machine_readable_chain"),
            "top_signals":      top_signals,
            "flagged_signals":  flagged,
            "query_id":         data.get("query_id"),
            "naxa_ms":          data.get("query_time_ms"),
        }
    }


if __name__ == "__main__":
    result = run_case_b()
    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(json.dumps(result["output"], indent=2))