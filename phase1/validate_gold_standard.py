# ============================================================
# NAXA Phase 1 — validate_gold_standard.py
#
# The Gold Standard Validator
# Purpose: Load the JSON we built and stress-test it.
#          Catch every problem BEFORE it reaches a customer.
#
# WHY VALIDATION EXISTS:
#   A validator is a quality gate.
#   Before any data leaves NAXA's system, it must pass checks.
#   If a confidence score is > 1.0, catch it here.
#   If a source field is empty, catch it here.
#   If a required field is missing, catch it here.
#   Better to crash internally than to serve broken data.
#
# This is the engineering principle called "fail fast":
#   Detect problems as early as possible, as loudly as possible.
#   The longer a bug survives undetected, the more damage it does.
#
# OUTPUT:
#   - PASS / FAIL for each check
#   - A full human-readable summary of what's in the JSON
#   - A list of warnings and errors
#   - An overall VALID / INVALID verdict
# ============================================================

import json
import sys

# ============================================================
# SECTION 1: LOAD THE JSON
# ============================================================

JSON_PATH = "data/processed/panama_canal_2023_gold_standard.json"

print("=" * 65)
print("NAXA Phase 1 — Gold Standard JSON Validator")
print("=" * 65)

try:
    with open(JSON_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"\n  ✓ Loaded: {JSON_PATH}\n")
except FileNotFoundError:
    print(f"\n  FATAL: {JSON_PATH} not found.")
    print("  Run build_gold_standard.py first.")
    sys.exit(1)
except json.JSONDecodeError as e:
    print(f"\n  FATAL: JSON parse error: {e}")
    print("  The file exists but is not valid JSON.")
    sys.exit(1)


# ============================================================
# SECTION 2: VALIDATION ENGINE
# ============================================================
#
# We build a list of results: each check either PASSES or FAILS.
# At the end, we count fails to determine overall validity.
#
# NEW CONCEPT: list comprehensions and conditional logic
#
#   results = []          → empty list
#   results.append(x)     → add item to list
#   all(r["pass"] for r in results)  → True if ALL items pass
#
# This pattern — collect results, then evaluate — is the
# foundation of any testing framework.

results  = []   # all validation results
warnings = []   # non-fatal issues worth noting

def check(name, condition, detail="", fatal=False):
    """
    Runs one validation check.
    Appends result to the results list.

    Args:
        name (str):      What we're checking
        condition (bool): True = PASS, False = FAIL
        detail (str):    Extra context on failure
        fatal (bool):    If True, FAIL = immediate exit
    """
    status = "PASS" if condition else "FAIL"
    results.append({
        "name":   name,
        "pass":   condition,
        "status": status,
        "detail": detail
    })

    icon = "✓" if condition else "✗"
    color_start = "" if condition else ""
    print(f"  {icon} {status}  {name}")
    if not condition and detail:
        print(f"       → {detail}")

    if not condition and fatal:
        print("\nFATAL error — stopping validation.")
        sys.exit(1)

def warn(message):
    """Records a non-fatal warning."""
    warnings.append(message)
    print(f"  ⚠  WARN  {message}")


# ============================================================
# SECTION 3: RUN ALL CHECKS
# ============================================================

print("── SCHEMA STRUCTURE CHECKS ──────────────────────────────\n")

# Required top-level fields
required_fields = [
    "schema_version", "naxa_version", "query_id", "generated_at",
    "event", "human_summary", "signal_chain",
    "agent_payload", "data_sources_used", "methodology"
]

for field in required_fields:
    check(
        f"Required field present: '{field}'",
        field in data,
        f"Missing top-level field: {field}"
    )

# Schema version format
sv = data.get("schema_version", "")
check(
    "Schema version format (X.Y.Z)",
    isinstance(sv, str) and len(sv.split(".")) == 3,
    f"Got: '{sv}'"
)

# Query ID is a UUID
qid = data.get("query_id", "")
check(
    "Query ID is a non-empty string",
    isinstance(qid, str) and len(qid) > 8,
    f"Got: '{qid}'"
)


print("\n── EVENT SECTION CHECKS ─────────────────────────────────\n")

event = data.get("event", {})

check("event.id present",       "id" in event)
check("event.type present",     "type" in event)
check("event.location present", "location" in event)
check("event.timeline present", "timeline" in event)
check("event.severity present", "severity" in event)

severity = event.get("severity", {})
sev_score = severity.get("score")
check(
    "Severity score in [0, 1]",
    isinstance(sev_score, (int, float)) and 0 <= sev_score <= 1,
    f"Got: {sev_score}"
)

check(
    "Severity has a source",
    "source" in severity and severity["source"],
    "Severity source is missing or empty"
)

timeline = event.get("timeline", {})
for date_field in ["formal_restriction_date", "peak_severity_date"]:
    check(
        f"timeline.{date_field} present",
        date_field in timeline and timeline[date_field],
        f"Missing: {date_field}"
    )


print("\n── SIGNAL CHAIN CHECKS ──────────────────────────────────\n")

chain = data.get("signal_chain", [])

check(
    "Signal chain is a non-empty array",
    isinstance(chain, list) and len(chain) >= 3,
    f"Got {len(chain)} steps — minimum 3 required"
)

# Check each step in the chain
for i, step in enumerate(chain):
    step_id = step.get("step_id", f"step_{i}")

    check(
        f"[{step_id}] has 'layer' field",
        "layer" in step and isinstance(step["layer"], int),
        f"Layer field missing or wrong type"
    )

    check(
        f"[{step_id}] has 'direction' field",
        "direction" in step and step["direction"] in
        ["UP", "DOWN", "MIXED", "FLAT"],
        f"Got: '{step.get('direction')}' — must be UP/DOWN/MIXED/FLAT"
    )

    check(
        f"[{step_id}] has 'sources' field",
        "sources" in step and isinstance(step["sources"], list)
        and len(step["sources"]) > 0,
        f"Sources missing or empty for step '{step_id}'"
    )

    conf = step.get("confidence", {})
    conf_score = conf.get("score")

    check(
        f"[{step_id}] confidence score in [0, 1]",
        isinstance(conf_score, (int, float)) and
        0 <= conf_score <= 1,
        f"Got: {conf_score}"
    )

    check(
        f"[{step_id}] confidence has 'basis' field",
        "basis" in conf and conf["basis"],
        "No confidence basis — score is unsourced"
    )

    # Warn if confidence is high but n= is small
    n_events = conf.get("n_events")
    if (isinstance(conf_score, float) and conf_score > 0.80
            and isinstance(n_events, int) and n_events < 12):
        warn(f"[{step_id}] confidence {conf_score} may be overconfident "
             f"for n={n_events} — check sample size cap")

    # Warn about unsourced confounder_warning fields
    if "confounder_warning" in step:
        note = step["confounder_warning"]
        if isinstance(note, str) and len(note) < 20:
            warn(f"[{step_id}] confounder_warning is too brief to be useful")


print("\n── HUMAN SUMMARY CHECKS ──────────────────────────────────\n")

summary = data.get("human_summary", "")

check(
    "Human summary is a non-empty string",
    isinstance(summary, str) and len(summary) > 50,
    f"Too short or missing — got {len(summary)} characters"
)

check(
    "Human summary contains confidence language",
    "confidence" in summary.lower() or "n=" in summary.lower(),
    "Summary should reference confidence scores — pure claims are not auditable"
)

# Check summary doesn't contain unsupported superlatives
flag_words = ["guaranteed", "certain", "definitely", "always", "never will"]
unsupported = [w for w in flag_words if w.lower() in summary.lower()]
check(
    "Human summary uses appropriate uncertainty language",
    len(unsupported) == 0,
    f"Overconfident language found: {unsupported}"
)


print("\n── AGENT PAYLOAD CHECKS ─────────────────────────────────\n")

agent = data.get("agent_payload", {})

check("agent_payload.machine_readable_chain present",
      "machine_readable_chain" in agent and agent["machine_readable_chain"])

check("agent_payload.top_confidence_signals present",
      "top_confidence_signals" in agent and
      len(agent["top_confidence_signals"]) > 0)

check("agent_payload.structured_assets present",
      "structured_assets" in agent and
      len(agent["structured_assets"]) > 0)

# Check structured assets have required fields
for asset in agent.get("structured_assets", []):
    for required in ["direction", "confidence", "lag_days"]:
        check(
            f"Asset '{asset.get('instrument','?')}' has '{required}'",
            required in asset,
            f"Missing field: {required}"
        )
    c = asset.get("confidence")
    check(
        f"Asset '{asset.get('instrument','?')}' confidence in [0,1]",
        isinstance(c, (int, float)) and 0 <= c <= 1,
        f"Got: {c}"
    )


print("\n── DATA SOURCES CHECKS ──────────────────────────────────\n")

sources = data.get("data_sources_used", [])

check(
    "At least 3 distinct data sources",
    len(sources) >= 3,
    f"Got {len(sources)} sources"
)

for src in sources:
    check(
        f"Source '{src.get('id','?')}' has name and url",
        "name" in src and "url" in src and
        src["name"] and src["url"],
        f"Source missing name or url"
    )
    check(
        f"Source '{src.get('id','?')}' has fields_sourced",
        "fields_sourced" in src and src["fields_sourced"],
        "fields_sourced links source to specific JSON fields"
    )


print("\n── METHODOLOGY CHECKS ───────────────────────────────────\n")

method = data.get("methodology", {})

check("methodology.confidence_scoring present",
      "confidence_scoring" in method and method["confidence_scoring"])

check("methodology.n_comparable_events >= 1",
      isinstance(method.get("n_comparable_events"), int)
      and method["n_comparable_events"] >= 1)

check("methodology.known_limitations present",
      "known_limitations" in method
      and len(method["known_limitations"]) > 0)


# ============================================================
# SECTION 4: PRINT THE FINAL VERDICT
# ============================================================

passes  = sum(1 for r in results if r["pass"])
fails   = sum(1 for r in results if not r["pass"])
total   = len(results)
n_warns = len(warnings)

print("\n" + "=" * 65)
print("VALIDATION SUMMARY")
print("=" * 65)
print(f"\n  Checks passed:   {passes} / {total}")
print(f"  Checks failed:   {fails}")
print(f"  Warnings:        {n_warns}")

if fails == 0 and n_warns == 0:
    verdict = "VALID — Gold Standard JSON is production-ready for Phase 1."
    verdict_icon = "✓"
elif fails == 0 and n_warns > 0:
    verdict = "VALID WITH WARNINGS — review warnings before Phase 2 automation."
    verdict_icon = "⚠"
else:
    verdict = f"INVALID — {fails} check(s) failed. Fix before proceeding."
    verdict_icon = "✗"

print(f"\n  {verdict_icon} VERDICT: {verdict}")

# Print the human-readable summary of what's in the JSON
print("\n" + "=" * 65)
print("WHAT'S INSIDE THE GOLD STANDARD JSON")
print("=" * 65)

event = data.get("event", {})
chain = data.get("signal_chain", [])
agent = data.get("agent_payload", {})

print(f"\n  Event:      {event.get('name', 'N/A')}")
print(f"  Severity:   {event.get('severity', {}).get('score', 'N/A')} "
      f"(transit reduction: {event.get('severity', {}).get('reduction_percentage', 'N/A')}%)")
print(f"  Date range: "
      f"{event.get('timeline', {}).get('formal_restriction_date', 'N/A')} → "
      f"{event.get('timeline', {}).get('resolution_date', 'N/A')}")

print(f"\n  Signal chain layers:")
for step in chain:
    conf = step.get("confidence", {})
    print(f"    L{step.get('layer','?')} [{step.get('step_id','?')[:30]:<30}] "
          f"→ {step.get('direction','?'):<6} "
          f"conf={conf.get('score', '?')}")

print(f"\n  Top agent signals by confidence:")
for sig in agent.get("top_confidence_signals", []):
    print(f"    {sig.get('step_id','?'):<35} "
          f"conf={sig.get('confidence','?')} "
          f"lag={sig.get('lag_days','?')}d")

print(f"\n  Data sources: {len(data.get('data_sources_used', []))}")
print(f"  Schema version: {data.get('schema_version', 'N/A')}")
print(f"  Query ID: {data.get('query_id', 'N/A')[:20]}...")

print("\n" + "=" * 65)
print("Phase 1 Day 4 complete.")
print("=" * 65)
print("\nNext: Run Day 5 stress-test session — then Phase 2 begins.")
print("Phase 2: Python automates the production of this same JSON.")