# ============================================================
# NAXA Phase 2 — analyze.py
#
# The Single Entry Point
# ============================================================
#
# THIS IS THE PHASE 2 DELIVERABLE.
# Everything built across Phase 2 flows into this one file.
#
# WHAT IT DOES:
#   Accepts one event description via command line.
#   Runs the full engine pipeline.
#   Outputs the Gold Standard JSON.
#
# TARGET COMMAND:
#   python analyze.py --event "canal_restriction" \
#                     --date "2023-08-01"          \
#                     --severity 0.85
#
# ARCHITECTURE PRINCIPLE — Single entry point:
#   In production data systems, there is always one
#   executable that ties everything together.
#   Quant funds call this the "run script" or "main."
#   It is the thing a junior analyst runs without
#   needing to understand the internals.
#   It is also the thing a startup reviewer clones
#   your repo and runs in 60 seconds.
#   Everything depends on this working cleanly.
# ============================================================

import argparse
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import (
    NAXA_VERSION,
    OUTPUT_DIR,
    SUPPORTED_EVENT_TYPES,
)
from engine.correlator  import build_signal_chain
from engine.synthesizer import synthesize
from engine.events_db   import DB_METADATA


# ============================================================
# SECTION 1: ARGUMENT PARSER
# ============================================================
#
# argparse is Python's standard library for CLI arguments.
# It handles --flag value syntax, type conversion,
# and generates --help documentation automatically.
#
# QUANT CONCEPT — Why CLI arguments matter:
#   A script with hardcoded values is a demo.
#   A script with CLI arguments is a tool.
#   The difference: your co-founder can run it on any event
#   without touching the code. An AI agent can call it
#   programmatically in Phase 3.

def parse_args():
    parser = argparse.ArgumentParser(
        prog="analyze.py",
        description="NAXA — Macro Event Signal Chain Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python analyze.py --event canal_restriction --date 2023-08-01 --severity 0.85
  python analyze.py --event canal_restriction --date 2021-03-23 --severity 0.95
        """
    )

    parser.add_argument(
        "--event",
        type=str,
        required=True,
        choices=SUPPORTED_EVENT_TYPES,
        help=f"Event type. Supported: {SUPPORTED_EVENT_TYPES}",
    )

    parser.add_argument(
        "--date",
        type=str,
        required=True,
        help="Event trigger date in YYYY-MM-DD format",
    )

    parser.add_argument(
        "--severity",
        type=float,
        default=0.75,
        help="Severity score 0.0-1.0 (default: 0.75)",
    )

    parser.add_argument(
        "--no-synthesis",
        action="store_true",
        help="Skip LLM synthesis (faster, no human_summary)",
    )

    return parser.parse_args()


# ============================================================
# SECTION 2: INPUT VALIDATOR
# ============================================================

def validate_inputs(event_type: str, date: str, severity: float):
    """
    Validates all inputs before the pipeline runs.
    Fails fast with clear messages.

    ENGINEERING PRINCIPLE — Validate at the boundary:
        Check inputs once, at the entry point.
        Internal modules assume inputs are valid.
        This keeps internal code clean and fast.
    """
    # Date format check
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(
            f"Invalid date format: '{date}'. Required: YYYY-MM-DD"
        )

    # Severity range check
    if not 0.0 <= severity <= 1.0:
        raise ValueError(
            f"Severity must be between 0.0 and 1.0. Got: {severity}"
        )

    print(f"  ✓ Inputs validated")


# ============================================================
# SECTION 3: AGENT PAYLOAD BUILDER
# ============================================================
#
# The agent_payload is a stripped-down, machine-optimized
# version of the signal chain for AI agent consumers.
# Agents should read this — not the full signal_chain —
# for efficiency.
#
# PRODUCT PRINCIPLE — Serve two audiences in one call:
#   human_summary    → analyst reads this
#   signal_chain     → analyst digs into this
#   agent_payload    → AI agent parses this
#   All three in the same JSON response.

def build_agent_payload(signal_chain: list) -> dict:
    """
    Builds the compact machine-readable payload from signal chain.
    """
    structured_assets = []
    top_signals       = []
    flagged_low       = []

    for step in signal_chain:
        conf   = step["confidence"].get("score_30d")
        m30    = step["measured"].get("move_30d_pct")
        exp    = step["expected"]

        # Structured assets list
        asset_entry = {
            "step_id":       step["step_id"],
            "asset_class":   step["asset_class"],
            "direction":     step["direction"],
            "confidence_30d": conf,
            "lag_days":      exp.get("lag_days"),
            "move_range":    exp.get("move_range"),
            "measured_30d":  m30,
            "is_proxy":      step["measured"].get("is_proxy", False),
        }
        structured_assets.append(asset_entry)

        # Top confidence signals (>= 0.60)
        if conf is not None and conf >= 0.60:
            top_signals.append({
                "step_id":    step["step_id"],
                "confidence": conf,
                "direction":  step["direction"],
                "lag_days":   exp.get("lag_days"),
            })

        # Flagged low confidence (< 0.50)
        if conf is not None and conf < 0.50:
            flagged_low.append({
                "step_id":    step["step_id"],
                "confidence": conf,
                "reason":     "below_minimum_actionable_threshold",
            })

    # Sort top signals by confidence descending
    top_signals.sort(key=lambda x: x["confidence"], reverse=True)

    # Build compact machine-readable chain string
    # Format: StepID:Direction:Measured30d:Conf
    chain_parts = []
    for step in signal_chain:
        conf = step["confidence"].get("score_30d", 0)
        m30  = step["measured"].get("move_30d_pct")
        m30_str = f"{m30:+.1f}%" if m30 is not None else "N/A"
        chain_parts.append(
            f"{step['step_id']}:{step['direction']}:{m30_str}:{conf:.2f}"
        )

    return {
        "machine_readable_chain":  " | ".join(chain_parts),
        "top_confidence_signals":  top_signals,
        "flagged_low_confidence":  flagged_low,
        "structured_assets":       structured_assets,
        "query_metadata": {
            "event_type":              "canal_restriction",
            "n_comparable_events":     DB_METADATA["n_events"],
            "backtest_date_range":     DB_METADATA["date_range"],
            "confidence_methodology":  DB_METADATA["methodology"],
            "confidence_ceiling":      DB_METADATA["confidence_ceiling"],
        }
    }


# ============================================================
# SECTION 4: GOLD STANDARD JSON ASSEMBLER
# ============================================================

def assemble_gold_standard(
    event_type:     str,
    event_date:     str,
    severity:       float,
    signal_chain:   list,
    human_summary:  str,
    query_time_ms:  int,
) -> dict:
    """
    Assembles the complete Gold Standard JSON.
    This is the schema that every NAXA response follows.
    """
    return {
        "schema_version": "0.2.0",
        "naxa_version":   NAXA_VERSION,
        "query_id":       str(uuid.uuid4()),
        "generated_at":   datetime.now(timezone.utc).isoformat(),
        "query_time_ms":  query_time_ms,

        "event": {
            "type":           event_type,
            "date":           event_date,
            "severity_score": severity,
            "severity_basis": "transit_slot_reduction_pct_x_duration_weeks",
        },

        "human_summary": human_summary,

        "signal_chain": signal_chain,

        "agent_payload": build_agent_payload(signal_chain),

        "methodology": {
            "confidence_scoring":    DB_METADATA["methodology"],
            "backtesting_period":    DB_METADATA["date_range"],
            "n_comparable_events":   DB_METADATA["n_events"],
            "confidence_floor":      DB_METADATA["confidence_floor"],
            "confidence_ceiling":    DB_METADATA["confidence_ceiling"],
            "known_limitations": [
                "n=14 events across 4 disruption types — confidence ceiling maintained at 0.85 "
                "until 3 ESTIMATED events (2011, 2014, 2015) are verified with primary sources",
                "Drewry WCI not available on free tier — using FRED proxy",
                "Monthly FRED data limits precision for sub-30d lag analysis",
                "Corn series PMAIZMTUSD unavailable — soybean used as proxy",
                "Mixed event types (canal, route security, port) — directional signals valid, "
                "magnitude comparisons should note event type differences",
            ]
        }
    }


# ============================================================
# SECTION 5: MAIN PIPELINE
# ============================================================

def run_pipeline(
    event_type:    str,
    event_date:    str,
    severity:      float,
    skip_synthesis: bool = False,
    save_to_disk:   bool = True,   # True = CLI default; False = API mode
) -> dict:
    """
    Runs the full NAXA pipeline for one event.
    Returns the complete Gold Standard JSON as a dict.
    """
    print("\n" + "=" * 60)
    print("NAXA — Running Pipeline")
    print("=" * 60)
    print(f"  Event:    {event_type}")
    print(f"  Date:     {event_date}")
    print(f"  Severity: {severity}")
    print("=" * 60)

    pipeline_start = time.time()

    # ── Stage 1: Validate ─────────────────────────────────────
    print("\n[1/4] Validating inputs...")
    validate_inputs(event_type, event_date, severity)

    # ── Stage 2: Build Signal Chain ───────────────────────────
    print("\n[2/4] Building signal chain...")
    signal_chain = build_signal_chain(event_type, event_date, severity)

    # ── Stage 3: Synthesize ───────────────────────────────────
    if skip_synthesis:
        print("\n[3/4] Synthesis skipped (--no-synthesis flag)")
        human_summary = (
            "Synthesis skipped. Review signal_chain array for full data."
        )
    else:
        print("\n[3/4] Synthesizing human summary...")
        context = {
            "event": {
                "type":     event_type,
                "date":     event_date,
                "severity": severity,
            },
            "signal_chain": signal_chain,
            "db_metadata":  DB_METADATA,
        }
        human_summary = synthesize(context)

    # ── Stage 4: Assemble + Save ──────────────────────────────
    print("\n[4/4] Assembling Gold Standard JSON...")

    query_time_ms = int((time.time() - pipeline_start) * 1000)

    gold_standard = assemble_gold_standard(
        event_type    = event_type,
        event_date    = event_date,
        severity      = severity,
        signal_chain  = signal_chain,
        human_summary = human_summary,
        query_time_ms = query_time_ms,
    )

    # Save to output directory — CLI mode only.
    # API mode skips this: callers get JSON in the HTTP response.
    # Skipping also prevents a race condition where two concurrent
    # API requests for the same event+date overwrite each other's file.
    if save_to_disk:
        filename    = f"{event_type}_{event_date}.json"
        output_path = OUTPUT_DIR / filename
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(gold_standard, f, indent=2, ensure_ascii=False)
    else:
        output_path = None

    return gold_standard, output_path


# ============================================================
# SECTION 6: ENTRY POINT + SUMMARY PRINTER
# ============================================================

def print_summary(gold_standard: dict, output_path: Path):
    """Prints a clean human-readable summary of the run."""

    chain      = gold_standard["signal_chain"]
    agent      = gold_standard["agent_payload"]
    top        = agent["top_confidence_signals"]
    flagged    = agent["flagged_low_confidence"]
    query_time = gold_standard["query_time_ms"]

    print("\n" + "=" * 60)
    print("NAXA — PIPELINE COMPLETE")
    print("=" * 60)

    print(f"\n  Query time:     {query_time}ms")
    print(f"  Signal steps:   {len(chain)}")
    print(f"  High confidence signals: {len(top)}")
    print(f"  Low confidence flags:    {len(flagged)}")

    print(f"\n{'─' * 60}")
    print("  SIGNAL CHAIN SUMMARY")
    print(f"{'─' * 60}")
    print(f"  {'Signal':<35} {'30d':>7}  {'Conf':>6}")

    for step in chain:
        m30  = step["measured"].get("move_30d_pct")
        conf = step["confidence"].get("score_30d")
        m30_str  = f"{m30:+.1f}%" if m30  is not None else "N/A"
        conf_str = f"{conf:.3f}"  if conf is not None else "N/A"
        print(f"  {step['step_id']:<35} {m30_str:>7}  {conf_str:>6}")

    if top:
        print(f"\n{'─' * 60}")
        print("  TOP ACTIONABLE SIGNAL")
        print(f"{'─' * 60}")
        best = top[0]
        print(f"  {best['step_id']}")
        print(f"  Direction:  {best['direction']}")
        print(f"  Confidence: {best['confidence']:.3f}")
        print(f"  Lag:        {best['lag_days']} days")

    print(f"\n{'─' * 60}")
    print("  HUMAN SUMMARY")
    print(f"{'─' * 60}")
    summary = gold_standard.get("human_summary", "")
    # Word-wrap at 58 chars for clean terminal output
    words, line = summary.split(), ""
    for word in words:
        if len(line) + len(word) + 1 > 56:
            print(f"  {line}")
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        print(f"  {line}")

    print(f"\n{'─' * 60}")
    print(f"  Output saved: {output_path}")
    print(f"{'─' * 60}\n")


if __name__ == "__main__":
    args = parse_args()

    gold_standard, output_path = run_pipeline(
        event_type     = args.event,
        event_date     = args.date,
        severity       = args.severity,
        skip_synthesis = args.no_synthesis,
    )

    print_summary(gold_standard, output_path)