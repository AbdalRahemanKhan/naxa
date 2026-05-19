# ============================================================
# NAXA — config.py
# Stores API keys and shared configuration
# NEVER share this file or upload it to GitHub
# ============================================================

# Paste your FRED API key between the quotes below
FRED_API_KEY = "ae8ad4a3dacbb68e262edc32da290546"

# Base URL for the FRED API — this never changes
FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# Shared date range used across all Phase 1 scripts
START_DATE = "2023-06-01"
END_DATE   = "2024-01-31"
EVENT_DATE = "2023-08-01"