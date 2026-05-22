# ============================================================
# NAXA Demo — Side-by-Side Comparison Runner
# ============================================================
#
# USAGE:
#   Make sure Flask is running: python api/app.py
#   Then: python agents/compare.py
#
# THIS IS THE DEMO ARTIFACT.
# Run this in front of your co-founder.
# The output is the pitch.
# ============================================================

import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.case_a_no_naxa   import run_case_a
from agents.case_b_with_naxa import run_case_b


def print_comparison(a: dict, b: dict):
    W = 70

    print("\n" + "=" * W)
    print("  NAXA DEMO — SIDE BY SIDE COMPARISON")
    print("=" * W)
    print(f"  Query: Red Sea Houthi attacks — Maersk/MSC suspend transits, Dec 19 2023.")
    print(f"         What happens next across commodities and equities?")
    print("=" * W)

    # ── Metrics table ──────────────────────────────────────────
    metrics = [
        ("Time",             f"{a['time_seconds']}s",           f"{b['time_seconds']}s"),
        ("API calls",        str(a['api_calls']),                str(b['api_calls'])),
        ("Output format",    "Prose",                           "Structured JSON"),
        ("Auditable",        "No",                              "Yes"),
        ("Agent-readable",   "No",                              "Yes (machine_readable_chain)"),
        ("Confidence basis", "LLM-generated — no n=, no hit rate", "Backtested n=14, 2011-2024, hit rates sourced"),
        ("Source citations", "None",                            "FRED + yfinance + ACP"),
        ("Known limitations","Not flagged",                     "Explicitly listed"),
    ]

    print(f"\n  {'Metric':<22} {'CASE A — No NAXA':<22} {'CASE B — With NAXA'}")
    print(f"  {'-'*65}")
    for m in metrics:
        a_val = m[1][:21]
        b_val = m[2][:24]
        print(f"  {m[0]:<22} {a_val:<22} {b_val}")

    # ── Confidence comparison ──────────────────────────────────
    print(f"\n{'─' * W}")
    print("  CONFIDENCE SCORES")
    print(f"{'─' * W}")

    print("\n  Case A (LLM-generated — no historical basis):")
    for item in a["output"].get("confidence_data", []):
        if isinstance(item, dict) and "signal" in item:
            print(
                f"    {str(item.get('signal',''))[:30]:<32} "
                f"{item.get('direction','?'):<6} "
                f"conf={item.get('confidence','?')}  "
                f"basis: {str(item.get('basis','?'))[:35]}"
            )

    print("\n  Case B (Backtested — sourced hit rates):")
    for item in b["output"].get("confidence_data", []):
        if isinstance(item, dict) and "signal" in item:
            print(
                f"    {str(item.get('signal',''))[:30]:<32} "
                f"{item.get('direction','?'):<6} "
                f"conf={item.get('confidence','?')}  "
                f"n={item.get('n','?')}  "
                f"hit_rate={item.get('hit_rate','?')}"
            )

    # ── Summaries ──────────────────────────────────────────────
    print(f"\n{'─' * W}")
    print("  CASE A — HUMAN SUMMARY")
    print(f"{'─' * W}")
    summary_a = a["output"].get("human_summary", "")
    _wrap_print(summary_a, width=W-4)

    print(f"\n{'─' * W}")
    print("  CASE B — NAXA HUMAN SUMMARY")
    print(f"{'─' * W}")
    summary_b = b["output"].get("human_summary", "")
    _wrap_print(summary_b, width=W-4)

    # ── Machine readable chain ─────────────────────────────────
    if b["output"].get("machine_readable"):
        print(f"\n{'─' * W}")
        print("  CASE B — MACHINE READABLE CHAIN (for AI agents)")
        print(f"{'─' * W}")
        print(f"  {b['output']['machine_readable']}")

    # ── Flagged signals ────────────────────────────────────────
    if b["output"].get("flagged_signals"):
        print(f"\n{'─' * W}")
        print("  CASE B — FLAGGED LOW CONFIDENCE (system knows what it doesn't know)")
        print(f"{'─' * W}")
        for f in b["output"]["flagged_signals"]:
            print(f"    {f['step_id']}: conf={f['confidence']} — {f['reason']}")

    print(f"\n{'=' * W}")
    print("  VERDICT")
    print(f"{'=' * W}")
    print(f"  Case A: {a['time_seconds']}s, {a['api_calls']} LLM calls, 0 sources cited, confidence invented")
    print(f"  Case B: {b['time_seconds']}s, {b['api_calls']} API call,  every field sourced, confidence backtested")
    print(f"\n  NAXA query ID: {b['output'].get('query_id', 'N/A')}")
    print(f"{'=' * W}\n")


def _wrap_print(text: str, width: int = 66):
    """Word-wrap text for clean terminal output."""
    words, line = text.split(), ""
    for word in words:
        if len(line) + len(word) + 1 > width:
            print(f"  {line}")
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        print(f"  {line}")


if __name__ == "__main__":
    print("\nNAXA DEMO — Starting comparison run...")
    print("Make sure Flask is running: python api/app.py\n")

    print("Running Case A (without NAXA)...")
    result_a = run_case_a()

    print("\nRunning Case B (with NAXA — Flask must be running)...")
    result_b = run_case_b()

    print_comparison(result_a, result_b)