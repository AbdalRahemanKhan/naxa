# ============================================================
# test_api.py — Quick API smoke test
# Run from naxa/ with: python test_api.py
# ============================================================

import os
from dotenv import load_dotenv
import requests
import json

load_dotenv()

BASE_URL = "http://localhost:5000"
API_KEY  = os.getenv("NAXA_API_KEY")

HEADERS = {
    "Content-Type":  "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# ── Test 1: Health ─────────────────────────────────────────
print("\n[1/3] Health check...")
r = requests.get(f"{BASE_URL}/health")
print(f"  Status: {r.status_code}")
print(f"  Body:   {r.json()}")

# ── Test 2: Events list ────────────────────────────────────
print("\n[2/3] Events list...")
r = requests.get(f"{BASE_URL}/v1/events", headers=HEADERS)
print(f"  Status: {r.status_code}")
print(f"  Events: {[e['type'] for e in r.json()['supported_events']]}")

# ── Test 3: Full analyze (takes ~19s) ──────────────────────
print("\n[3/3] Analyze — canal_restriction 2023-08-01...")
print("  (this takes ~19s — Gemini synthesis running)")

r = requests.post(
    f"{BASE_URL}/v1/analyze",
    headers=HEADERS,
    json={
        "event":        "canal_restriction",
        "date":         "2023-08-01",
        "severity":     0.85,
        
    }
)

# Print full output so you can see the complete schema
if r.status_code == 200:
    print(json.dumps(r.json(), indent=2))
else:
    print(r.json())

print(f"  Status:     {r.status_code}")

if r.status_code == 200:
    data = r.json()
    print(f"  Query ID:   {data['query_id']}")
    print(f"  Query time: {data['query_time_ms']}ms")
    print(f"  Signals:    {len(data['signal_chain'])}")
    print(f"\n  SUMMARY:\n  {data['human_summary']}")
else:
    print(f"  Error: {r.json()}")