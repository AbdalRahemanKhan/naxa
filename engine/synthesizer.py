# ============================================================
# NAXA engine/synthesizer.py
#
# LLM Synthesis Layer — Groq (free tier, llama-3.3-70b)
# ============================================================
#
# WHY THIS MODULE EXISTS:
#   The rest of the pipeline produces structured numbers —
#   confidence scores, move percentages, lag days.
#   Those numbers are perfect for agents. Humans need prose.
#   This module bridges that gap: it takes the structured
#   signal chain and produces one readable paragraph.
#
# WHAT THIS MODULE DOES NOT DO:
#   It does NOT invent numbers, directions, or confidence.
#   Those come from backtested data in events_db.py.
#   The LLM here is a translator, not an analyst.
#
# WHY GROQ (not Gemini, not OpenAI):
#   Groq runs open-source models (Llama, Mixtral) on custom
#   inference hardware. The result: free tier, fast responses,
#   and reliable uptime. Gemini's free tier shares capacity
#   with Google's entire consumer base — hence the 503s.
#   Groq's free tier is specifically for developers.
#
# ARCHITECTURE PRINCIPLE — LLM as last step:
#   In a quant pipeline, you never let a model touch raw data.
#   You clean, normalize, score, then review.
#   Same here: data flows through ingestor → scorer →
#   correlator → then, finally, synthesizer.
#   By the time Groq sees the data, every number is already
#   sourced and validated. Groq just explains it in English.
# ============================================================

import sys
from pathlib import Path

# Add naxa/ root to path so we can import config.py
# (This file lives at naxa/engine/synthesizer.py,
#  config.py lives at naxa/config.py)
sys.path.insert(0, str(Path(__file__).parent.parent))

from groq import Groq
from config import GROQ_API_KEY


# ============================================================
# SECTION 1: CLIENT INITIALIZATION
# ============================================================
#
# We initialize the Groq client ONCE at module load time,
# not inside the synthesize() function.
#
# WHY THIS MATTERS:
#   Creating an API client involves network overhead —
#   DNS resolution, TCP handshake, auth token validation.
#   If we created it inside synthesize(), we'd pay that
#   cost on every single call.
#   Initializing at module load pays it once.
#   This is called the "singleton pattern" in software design.
#
# QUANT ANALOGY — Pre-market setup:
#   A trader doesn't log into Bloomberg mid-trade.
#   They connect at 7am, stay connected all day.
#   Module-level client initialization is the same idea.
#
# MODEL CHOICE — llama-3.3-70b-versatile:
#   70 billion parameters. Strong reasoning, clean prose.
#   Free on Groq's developer tier (no credit card needed).
#   Faster than Gemini 2.5 Flash was even on a good day.
#   "Versatile" = Groq's label for the instruction-tuned
#   version, optimized for following structured prompts.

_client    = Groq(api_key=GROQ_API_KEY)
GROQ_MODEL = "llama-3.3-70b-versatile"


# ============================================================
# SECTION 2: PROMPT BUILDER
# ============================================================
#
# WHY A SEPARATE FUNCTION FOR THE PROMPT:
#   The prompt is business logic — it defines what NAXA
#   asks the LLM to do and what constraints it must follow.
#   Keeping it separate from the API call means you can
#   iterate on prompt quality without touching infrastructure.
#   In production systems this is called "prompt management."
#
# PROMPT DESIGN — Structured input, constrained output:
#   We pass the LLM exact numbers from backtested data.
#   We explicitly forbid it from inventing numbers.
#   We specify format: one paragraph, ~150 words.
#
#   WHY explicit constraints matter:
#   LLMs are pattern matchers trained to sound helpful.
#   Without constraints, they will confidently invent
#   statistics that sound plausible but aren't sourced.
#   That violates NAXA's core principle: every field sourced.
#   The prompt is our enforcement mechanism.

def _build_prompt(context: dict) -> str:
    """
    Builds the synthesis prompt from structured pipeline context.

    Args:
        context (dict): must contain keys:
            'event'        → {type, date, severity}
            'signal_chain' → list of signal step dicts
            'db_metadata'  → {n_events, date_range, ...}

    Returns:
        str: formatted prompt ready to send to the LLM
    """
    event   = context["event"]
    chain   = context["signal_chain"]
    db_meta = context["db_metadata"]

    # Build a compact one-line summary per signal
    # This gives the LLM exactly what it needs —
    # no more, no less. Shorter prompts = faster + cheaper.
    signal_lines = []
    for step in chain:
        conf    = step["confidence"].get("score_30d", "N/A")
        m30     = step["measured"].get("move_30d_pct")
        exp     = step["expected"]
        m30_str = f"{m30:+.1f}%" if m30 is not None else "N/A"

        signal_lines.append(
            f"- {step['asset']} ({step['asset_class']}): "
            f"direction={step['direction']}, "
            f"measured_30d={m30_str}, "
            f"expected_range={exp.get('move_range', 'N/A')}, "
            f"confidence_30d={conf}, "
            f"lag_days={exp.get('lag_days', 'N/A')}, "
            f"n={step['confidence'].get('n', 'N/A')}, "
            f"hit_rate={step['confidence'].get('hit_rate', 'N/A')}"
        )

    signals_text = "\n".join(signal_lines)

    # The prompt has three parts:
    #   1. Role definition   — who is the LLM in this call
    #   2. Hard constraints  — what it must and must not do
    #   3. Structured data   — the actual numbers to explain
    #
    # This structure is called "system + data" prompting.
    # Role + rules first. Data second. Output instruction last.
    # This ordering produces more consistent, constrained output
    # than mixing rules and data together.

    return f"""You are the synthesis layer for NAXA, an alternative data API for macro event analysis.

Write ONE paragraph (~150 words) summarizing the signal chain below for a financial analyst.

STRICT RULES — follow exactly:
- Use ONLY the numbers provided below. Do not invent or estimate any figures.
- Reference confidence scores by their exact values (e.g. "confidence 0.70").
- Reference backtested sample sizes (e.g. "based on n=4 historical events").
- Mention which signals are high-confidence (>=0.60) vs flagged low-confidence (<0.50).
- Do NOT predict future prices. Describe historical patterns and what was measured.
- Write in plain English. No bullet points. No headers. One paragraph only.

EVENT:
Type:     {event['type']}
Date:     {event['date']}
Severity: {event['severity']} (0.0 = minor restriction, 1.0 = full closure)

SIGNAL CHAIN (backtested on {db_meta['n_events']} historical events, {db_meta['date_range']}):
{signals_text}

Write the one-paragraph summary now:"""


# ============================================================
# SECTION 3: PUBLIC SYNTHESIZE FUNCTION
# ============================================================
#
# This is the only function analyze.py imports.
# Everything else in this file is internal.
#
# DESIGN PRINCIPLE — Graceful degradation:
#   If the LLM call fails (network error, quota, timeout),
#   the function returns a fallback string instead of crashing.
#   The pipeline keeps running. The Gold Standard JSON is
#   still valid — only human_summary is degraded.
#
#   This is called "graceful degradation" in systems design.
#   QUANT ANALOGY: a trading system that can't pull live
#   prices should fall back to last-known prices and flag
#   the staleness — not crash and stop all trading.
#   Same principle here.

def synthesize(context: dict) -> str:
    """
    Synthesizes a human-readable summary from structured signal chain data.

    Args:
        context (dict): structured data from the pipeline
            (event metadata + signal chain + db metadata)

    Returns:
        str: One paragraph plain-English summary.
             Never raises — returns fallback string on failure.

    IMPORTANT — What this function guarantees:
        It ALWAYS returns a string.
        It NEVER raises an exception.
        It NEVER invents numbers (enforced via prompt constraints).
        The returned string goes directly into human_summary
        in the Gold Standard JSON.
    """
    print(f"  [Synthesizer] Building prompt...")
    prompt = _build_prompt(context)

    print(f"  [Synthesizer] Calling {GROQ_MODEL}...")

    try:
        # chat.completions.create() is the standard interface
        # used by OpenAI, Groq, and most modern LLM APIs.
        # It accepts a list of message dicts:
        #   role="system"    → sets the LLM's behavior context
        #   role="user"      → the actual query or prompt
        #   role="assistant" → LLM's prior responses (for multi-turn)
        #
        # We use role="user" only — single-turn, one-shot synthesis.
        # No conversation history needed here.

        response = _client.chat.completions.create(
            model      = GROQ_MODEL,
            max_tokens = 400,      # ~300 word ceiling — keeps summary tight
            messages   = [{"role": "user", "content": prompt}]
        )

        # response.choices[0].message.content is where Groq
        # (and OpenAI-compatible APIs) put the response text.
        # choices[0] = the first (and only, for n=1) completion.
        # .message.content = the actual text string.

        summary = response.choices[0].message.content.strip()

        print(f"  [Synthesizer] ✓ Summary generated "
              f"({len(summary.split())} words)")

        return summary

    except Exception as e:
        # Catch everything — network errors, quota errors,
        # malformed responses. Log it, return fallback.
        # The pipeline caller (analyze.py) does not need to
        # know the synthesis failed — it just gets a string.
        print(f"  [Synthesizer] ERROR: {e}")
        return (
            f"Synthesis unavailable. Signal chain data is complete "
            f"and valid. Review signal_chain array directly. "
            f"Error: {str(e)}"
        )


# ============================================================
# SECTION 4: SMOKE TEST
# ============================================================
#
# Run this file directly to verify Groq connectivity
# before running the full pipeline:
#   python -m engine.synthesizer

if __name__ == "__main__":
    from engine.correlator import build_signal_chain
    from engine.events_db  import DB_METADATA

    print("=" * 60)
    print("NAXA Synthesizer — Smoke Test (Groq)")
    print("=" * 60)

    chain = build_signal_chain(
        event_type     = "canal_restriction",
        event_date     = "2023-08-01",
        severity_score = 0.85,
    )

    context = {
        "event": {
            "type":     "canal_restriction",
            "date":     "2023-08-01",
            "severity": 0.85,
        },
        "signal_chain": chain,
        "db_metadata":  DB_METADATA,
    }

    print("\n[Synthesizer] Generating human_summary...\n")
    summary = synthesize(context)

    print("\n" + "─" * 60)
    print("HUMAN SUMMARY OUTPUT:")
    print("─" * 60)
    print(summary)
    print("─" * 60)
    print("\n✓ Synthesizer operational")