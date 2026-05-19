# ============================================================
# NAXA Phase 2 — config.py (root level)
#
# Central Configuration — reads from .env
# ============================================================
#
# WHY THIS IS DIFFERENT FROM PHASE 1's config.py:
#   Phase 1 config: hardcoded keys, lives in phase1/
#   Phase 2 config: reads from .env, lives at naxa/ root
#
# The upgrade matters for two reasons:
#   1. Security: API keys never exist in source code
#   2. Portability: your co-founder can clone the repo,
#      create their own .env, and run the pipeline without
#      you ever sharing keys directly
#
# BACKWARD COMPATIBILITY:
#   We keep START_DATE, END_DATE, EVENT_DATE, FRED_BASE_URL
#   so Phase 2 engine modules can import from this config
#   using the same field names Phase 1 used.
#   Phase 1 scripts still import from their local config.py
#   and are completely unaffected.
# ============================================================

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env ──────────────────────────────────────────────────
#
# Path(__file__).parent = the directory containing this file
# That's naxa/ — the root of our project.
# load_dotenv() reads naxa/.env and injects everything into
# os.environ — Python's global environment variable store.
#
# Think of os.environ like a secure notepad that Python
# reads from. load_dotenv() writes to that notepad.
# os.getenv() reads from it.

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")


# ── API Keys ───────────────────────────────────────────────────
#
# os.getenv("KEY") reads from os.environ.
# If the key doesn't exist, it returns None (not a crash).
# We add explicit guards below so failures are loud and clear.

FRED_API_KEY  = os.getenv("FRED_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
NAXA_VERSION  = os.getenv("NAXA_VERSION", "0.2.0")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ── Fail Fast Guard ────────────────────────────────────────────
#
# "Fail fast" is a core engineering principle.
# It means: if something is broken, crash immediately
# with a clear error message — don't limp along and
# produce garbage output 60 seconds later.
#
# A pipeline that silently uses a None API key will
# make 15 API calls, produce 15 errors, and waste
# your time debugging the wrong thing.
# This guard kills it at startup with an actionable message.

if not FRED_API_KEY:
    raise EnvironmentError(
        "FRED_API_KEY not found.\n"
        "Fix: Add FRED_API_KEY=your_key to naxa/.env\n"
        "Get a free key at: https://fred.stlouisfed.org/docs/api/api_key.html"
    )
if not GEMINI_API_KEY:
    raise EnvironmentError(
        "GEMINI_API_KEY not found.\n"
        "Fix: Add GEMINI_API_KEY=your_key to naxa/.env\n"
        "Get a free key at: https://aistudio.google.com/app/apikey"
    )


# ── URL Constants ──────────────────────────────────────────────
# Kept for backward compatibility with any engine modules
# that import FRED_BASE_URL from here

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"


# ── Date Constants ─────────────────────────────────────────────
#
# These are the Panama Canal 2023 event defaults.
# In Phase 3, analyze.py will accept these as CLI arguments
# and override them dynamically.
# For Phase 2, they remain as defaults.

START_DATE = "2023-06-01"   # 2 months before event: captures baseline
END_DATE   = "2024-01-31"   # 5 months after event: captures full chain
EVENT_DATE = "2023-08-01"   # ACP formal restriction: ACP Notice N-A-148-2023


# ── Directory Paths ────────────────────────────────────────────
#
# pathlib.Path is the modern Python way to handle file paths.
# It works on Windows (backslashes) AND Mac/Linux (forward slashes)
# without you doing anything special.
# The / operator on Path objects builds paths correctly
# for whichever OS you're on.

DATA_DIR      = BASE_DIR / "data"
RAW_DIR       = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR    = DATA_DIR / "output"

# Create all directories on import — if they exist, no crash
for _dir in [RAW_DIR, PROCESSED_DIR, OUTPUT_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)


# ── Shipping Tickers ───────────────────────────────────────────
#
# Centralized here so ingestor.py doesn't maintain its own list.
# Single source of truth: change here, updates everywhere.
#
# QUANT CONCEPT — Why these specific tickers:
#   ZIM, MATX, DAC → container operators (directly affected
#                     by canal capacity restriction)
#   GNK             → dry bulk (grain rerouting signal)
#   INSW, FRO       → tankers (ton-mile expansion signal —
#                     rerouting via Cape Horn adds voyage length,
#                     increasing revenue per vessel)

SHIPPING_TICKERS = {
    "ZIM":  "ZIM Integrated Shipping (container, Asia-Americas)",
    "MATX": "Matson Inc (US container, Pacific routes)",
    "DAC":  "Danaos Corp (container ship lessor)",
    "GNK":  "Genco Shipping (dry bulk)",
    "INSW": "International Seaways (tanker)",
    "FRO":  "Frontline PLC (tanker)",
}


# ── FRED Series ────────────────────────────────────────────────
#
# Format: "SERIES_ID": ("Human-readable name", "frequency")
# frequency: "d" = daily, "m" = monthly
#
# QUANT CONCEPT — Why frequency matters:
#   Daily series respond within days of an event.
#   Monthly series lag by up to 30 days just from
#   data publication timing — on top of any real lag.
#   This means monthly data gives LOWER confidence scores
#   not because the signal is weaker, but because our
#   measurement precision is lower.

FRED_SERIES = {
    "PCU483111483111": ("PPI: Deep Sea Freight Transportation", "m"),
    "DCOILWTICO":      ("WTI Crude Oil Spot Price (USD/barrel)", "d"),
    "MHHNGSP":         ("Henry Hub Natural Gas Spot Price (USD/MMBtu)", "m"),
    "PMAIZMTUSD":      ("Global Price of Corn/Maize (USD/MT)", "m"),
    "PSOYBUSDM":       ("Global Price of Soybeans (USD/MT)", "m"),
    "T10Y2Y":          ("10Y-2Y Treasury Yield Spread (macro context)", "d"),
}


# ── Pipeline Parameters ────────────────────────────────────────

# Confidence score floor and ceiling
# Below floor = we report "insufficient_data", not a number
# Above ceiling = impossible until n >= 12 (Phase 1 rationale)
CONFIDENCE_FLOOR   = 0.30
CONFIDENCE_CEILING = 0.85
MIN_EVENTS_FOR_CONFIDENCE = 3

# Lag windows (days) used throughout the pipeline
# These must match the lag fields in historical_events_db.py
LAG_WINDOWS = [14, 30, 60]


# ── Supported Event Types ──────────────────────────────────────
# Phase 2 supports one event type only.
# Expanding this list before shipping vertical is proven
# violates the core product principle.

SUPPORTED_EVENT_TYPES = ["canal_restriction"]


# ── Quick Verification ─────────────────────────────────────────
# Run this file directly to confirm the environment is correct.

if __name__ == "__main__":
    print("=" * 55)
    print("NAXA Phase 2 — Config Verification")
    print("=" * 55)
    print(f"  Version:       {NAXA_VERSION}")
    print(f"  FRED key:      {FRED_API_KEY[:6]}...{FRED_API_KEY[-4:]}")
    print(f"  Gemini key:    {GEMINI_API_KEY[:6]}...{GEMINI_API_KEY[-4:]}")
    print(f"  Base dir:      {BASE_DIR}")
    print(f"  Output dir:    {OUTPUT_DIR}")
    print(f"  Tickers:       {list(SHIPPING_TICKERS.keys())}")
    print(f"  FRED series:   {list(FRED_SERIES.keys())}")
    print(f"\n✓ Config loaded successfully")