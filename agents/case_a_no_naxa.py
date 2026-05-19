# ============================================================
# NAXA Demo — Case A: Agent WITHOUT NAXA
# ============================================================
#
# WHAT THIS SIMULATES:
#   A capable AI agent answering a macro event query
#   using only its own reasoning — no structured data layer.
#
# WHY MULTI-STEP:
#   A fair Case A cannot be a single LLM call.
#   A real agent would: identify what to investigate,
#   research each signal, assign confidence, then synthesize.
#   Four steps. Four API round trips. This is honest.
#   Sandbagging Case A would make the demo dishonest —
#   
#
# THE CRITICAL WEAKNESS OF CASE A:
#   Every confidence score here is LLM-generated.
#   There is no backtesting. No n=. No hit rate.
#   No source citation. The agent is doing its best —
#   and its best is not auditable.
#   That is exactly what NAXA replaces.
#
# LLM USED: Groq llama-3.3-70b (free tier)
#   Same model as the synthesizer. Consistent baseline.
# ============================================================

import time
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from groq import Groq
from config import GROQ_API_KEY

# ── Client init ────────────────────────────────────────────────
# Same pattern as synthesizer.py — initialize once at module load.
# Groq uses OpenAI-compatible syntax: chat.completions.create()
_client = Groq(api_key=GROQ_API_KEY)
MODEL   = "llama-3.3-70b-versatile"

QUERY = (
    "Panama Canal water levels dropped to historic lows in August 2023. "
    "What happens next across commodities and equities? "
    "Give me specific assets, directions, magnitudes, and confidence scores."
)


# ============================================================
# MAIN FUNCTION
# ============================================================

def run_case_a() -> dict:
    """
    Runs the no-NAXA agent: 4 sequential LLM calls.
    Returns a standardized result dict for comparison.
    """
    start     = time.time()
    api_calls = 0
    step_log  = []

    print("\n" + "=" * 60)
    print("CASE A — Agent WITHOUT NAXA")
    print("=" * 60)
    print(f"  Query: {QUERY[:80]}...\n")

    # ── Step 1: Identify signals ───────────────────────────────
    #
    # The agent first figures out WHAT to investigate.
    # A human analyst does this mentally in seconds.
    # An LLM agent needs an explicit API call for this step.

    print("[1/4] Identifying relevant asset classes...")

    r1 = _client.chat.completions.create(
        model    = MODEL,
        max_tokens = 250,
        messages = [{
            "role":    "user",
            "content": (
                f"Macro event: {QUERY}\n\n"
                "List exactly 4 asset classes or signals a financial analyst "
                "should investigate. One per line. No explanations."
            )
        }]
    )
    api_calls  += 1
    signals_raw = r1.choices[0].message.content.strip()
    step_log.append({"step": 1, "name": "identify_signals", "output": signals_raw})
    print(f"  Done — {api_calls} call(s) so far")

    # ── Step 2: Research historical impact ─────────────────────
    #
    # Now the agent tries to recall what happened historically.
    # This is training-data recall — not backtested measurement.
    # The agent cannot cite a source for any number it produces.

    print("[2/4] Researching historical impact per signal...")

    r2 = _client.chat.completions.create(
        model      = MODEL,
        max_tokens = 500,
        messages   = [{
            "role":    "user",
            "content": (
                f"For a Panama Canal restriction event, what historically "
                f"happens to these assets?\n\n{signals_raw}\n\n"
                "Give directional expectations and rough magnitude ranges "
                "based on your training knowledge. "
                "Be honest where you are uncertain. "
                "Do not fabricate specific statistics."
            )
        }]
    )
    api_calls   += 1
    research_raw = r2.choices[0].message.content.strip()
    step_log.append({"step": 2, "name": "research", "output": research_raw})
    print(f"  Done — {api_calls} call(s) so far")

    # ── Step 3: Assign confidence scores ──────────────────────
    #
    # THIS IS THE KEY VULNERABILITY OF CASE A.
    # The agent assigns confidence scores from pattern matching
    # on training data. Not backtested. Not sourced.
    # If you ask "what's your n=?", it cannot answer.
    # The number 0.75 here means: "I feel fairly sure."
    # The number 0.702 in NAXA means: hit_rate=1.0, n=4, 2016-2023.
    # These are fundamentally different claims.

    print("[3/4] Assigning confidence scores...")

    r3 = _client.chat.completions.create(
        model      = MODEL,
        max_tokens = 400,
        messages   = [{
            "role":    "user",
            "content": (
                f"Based on this research:\n{research_raw}\n\n"
                "Assign a confidence score (0.0-1.0) for each signal's "
                "directional prediction. "
                "Return ONLY a valid JSON array, no other text:\n"
                '[{"signal": "...", "direction": "UP/DOWN/MIXED", '
                '"confidence": 0.XX, "basis": "one sentence explaining why"}]'
            )
        }]
    )
    api_calls      += 1
    confidence_raw  = r3.choices[0].message.content.strip()

    # Strip markdown fences if the LLM added them
    if "```" in confidence_raw:
        parts = confidence_raw.split("```")
        confidence_raw = parts[1] if len(parts) > 1 else parts[0]
        if confidence_raw.startswith("json"):
            confidence_raw = confidence_raw[4:]

    try:
        confidence_data = json.loads(confidence_raw.strip())
    except Exception:
        confidence_data = [{"error": "Could not parse confidence JSON",
                            "raw":   confidence_raw[:200]}]

    step_log.append({"step": 3, "name": "confidence", "output": confidence_data})
    print(f"  Done — {api_calls} call(s) so far")

    # ── Step 4: Final synthesis ────────────────────────────────
    #
    # The agent synthesizes everything into a final summary.
    # After 4 API calls, it produces prose — not structured JSON.
    # An AI agent trying to consume this output downstream
    # has to parse unstructured text, not a machine-readable chain.

    print("[4/4] Synthesizing final output...")

    r4 = _client.chat.completions.create(
        model      = MODEL,
        max_tokens = 300,
        messages   = [{
            "role":    "user",
            "content": (
                f"Write a 2-3 sentence analyst summary for this query:\n"
                f"'{QUERY}'\n\n"
                f"Based on research:\n{research_raw}\n\n"
                f"And confidence scores:\n{json.dumps(confidence_data)}\n\n"
                "Note that confidence is based on general market knowledge, "
                "not backtested historical data."
            )
        }]
    )
    api_calls += 1
    summary    = r4.choices[0].message.content.strip()
    step_log.append({"step": 4, "name": "synthesis", "output": summary})

    elapsed = round(time.time() - start, 1)
    print(f"\n  Case A complete — {elapsed}s, {api_calls} API calls")

    return {
        "case":         "A",
        "label":        "Agent WITHOUT NAXA",
        "time_seconds": elapsed,
        "api_calls":    api_calls,
        "output": {
            "human_summary":    summary,
            "confidence_data":  confidence_data,
            "confidence_basis": "LLM-generated — no backtesting, no n=, no hit rate",
            "sourcing":         "Training data only — no citations, no source links",
            "auditable":        False,
            "agent_structured": False,
            "machine_readable": None,
        },
        "step_log": step_log,
    }


# ============================================================
# STANDALONE RUN
# ============================================================

if __name__ == "__main__":
    result = run_case_a()
    print("\n" + "=" * 60)
    print("CASE A OUTPUT")
    print("=" * 60)
    print(json.dumps(result["output"], indent=2))