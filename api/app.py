# ============================================================
# NAXA Phase 3 — api/app.py
#
# The Flask API Layer
# ============================================================
#
# WHAT THIS FILE DOES:
#   Wraps the Phase 2 pipeline (analyze.py) in HTTP.
#   Three things only:
#     1. Parse and validate HTTP requests
#     2. Call run_pipeline()
#     3. Return HTTP responses with correct status codes
#
# WHAT THIS FILE DOES NOT DO:
#   No business logic. No data fetching. No scoring.
#   All of that lives in engine/ and analyze.py.
#   This file is intentionally thin — a "controller layer."
#
# ARCHITECTURE PRINCIPLE — Separation of concerns:
#   In a trading system, the execution layer (order routing)
#   is completely separate from the alpha layer (signal gen).
#   If execution breaks, alpha keeps working.
#   If alpha changes, execution doesn't need to know.
#   This file is the execution layer. engine/ is the alpha layer.
# ============================================================

import os
import sys
import time
import uuid
import logging
from datetime import datetime
from functools import wraps
from pathlib import Path

from flask import Flask, request, jsonify, make_response
from flask_cors import CORS

# ── Path setup ─────────────────────────────────────────────────
#
# WHY THIS IS NEEDED:
#   This file lives at naxa/api/app.py.
#   analyze.py lives at naxa/analyze.py.
#   When Python runs api/app.py, it looks for imports
#   relative to naxa/api/ — so "from analyze import" fails.
#
#   We add naxa/ to Python's search path so imports work
#   regardless of which directory you run Flask from.
#   Path(__file__).parent.parent resolves to naxa/.

sys.path.insert(0, str(Path(__file__).parent.parent))

from analyze import run_pipeline
from config import SUPPORTED_EVENT_TYPES, NAXA_VERSION


# ============================================================
# SECTION 1: APP + LOGGING INITIALIZATION
# ============================================================
#
# We configure logging BEFORE Flask initializes.
# This ensures startup messages use our format,
# not Flask's default format.
#
# logging replaces print() for server code.
# print() goes to stdout and disappears.
# logging goes to stdout AND can be redirected to files,
# cloud log aggregators (Datadog, Papertrail), or
# error trackers (Sentry) — with zero code changes here.

logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt = "%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("naxa.api")

app = Flask(__name__)

# ── CORS ───────────────────────────────────────────────────────
#
# CORS is a BROWSER security mechanism — not an API one.
# Python scripts, curl, Postman: completely unaffected by CORS.
# Only browsers check it.
#
# With Bearer token auth enforcing access on all /v1/* routes,
# open CORS (allow all origins) costs us nothing.
# Restricting it would only break browser-based demos.

CORS(app)

# ── API Key ────────────────────────────────────────────────────
#
# Single shared key for Phase 3.
# Every AI agent or human caller must send:
#   Authorization: Bearer <NAXA_API_KEY>
#
# This is the same auth model used by:
#   OpenAI, Anthropic, FRED, Alpha Vantage, Polygon.io
# Your co-founder will recognize it immediately.
#
# Generate a key (run once in terminal):
#   python -c "import secrets; print('naxa_live_' + secrets.token_hex(16))"
# Then add to naxa/.env:
#   NAXA_API_KEY=naxa_live_<output>

NAXA_API_KEY = os.getenv("NAXA_API_KEY")

if not NAXA_API_KEY:
    raise EnvironmentError(
        "\nNAXA_API_KEY not found in environment.\n"
        "Fix: Add to naxa/.env:\n"
        "  NAXA_API_KEY=naxa_live_<your_key>\n"
        "Generate one:\n"
        "  python -c \"import secrets; print('naxa_live_' + secrets.token_hex(16))\"\n"
    )

log.info(f"NAXA API v{NAXA_VERSION} initialized — key loaded ({NAXA_API_KEY[:14]}...)")


# ============================================================
# SECTION 2: AUTH DECORATOR
# ============================================================
#
# A decorator wraps a function with additional behavior.
# @require_api_key before a route means:
#   "Run this auth check before the route handler executes."
#
# This pattern separates auth logic from business logic.
# If we later switch to JWT tokens or per-user keys,
# we change this decorator only — routes stay identical.
#
# TRADING SYSTEM ANALOGY:
#   Every order passes a pre-trade risk gate before routing.
#   The gate checks: is this a valid counterparty?
#   The execution logic doesn't need to know — it just runs.
#   This decorator is that gate.

def require_api_key(f):
    @wraps(f)   # preserves original function name for Flask routing
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")

        if not auth_header.startswith("Bearer "):
            return _error_response(
                code    = "UNAUTHORIZED",
                message = "Missing or malformed Authorization header.",
                detail  = "Required format: Authorization: Bearer <your_naxa_api_key>",
                status  = 401,
            )

        token = auth_header[7:]   # strip "Bearer " prefix (7 characters)

        if token != NAXA_API_KEY:
            return _error_response(
                code    = "FORBIDDEN",
                message = "Invalid API key.",
                detail  = "Verify the NAXA_API_KEY value you were issued.",
                status  = 403,
            )

        return f(*args, **kwargs)
    return decorated


# ============================================================
# SECTION 3: ERROR RESPONSE HELPER
# ============================================================
#
# WHY a consistent error schema matters:
#   Flask returns HTML by default for 404 errors.
#   An AI agent calling your API and receiving HTML
#   will either crash or produce garbage output.
#   Every response from NAXA — success OR failure —
#   must be JSON.
#
# Error shape:
#   {
#     "error":        {"code": "...", "message": "...", "detail": "..."},
#     "naxa_version": "0.2.0",
#     "request_id":   "uuid"
#   }
#
# "code" is machine-readable (agent parses this).
# "message" is human-readable (analyst reads this).
# "detail" is optional context for debugging.

def _error_response(
    code:    str,
    message: str,
    detail:  str = "",
    status:  int = 400,
    req_id:  str = None,
) -> tuple:
    body = {
        "error": {
            "code":    code,
            "message": message,
            "detail":  detail,
        },
        "naxa_version": NAXA_VERSION,
        "request_id":   req_id or str(uuid.uuid4()),
    }
    return jsonify(body), status


# ============================================================
# SECTION 4: ROUTES
# ============================================================

# ── GET /health ───────────────────────────────────────────────
#
# INTENTIONALLY unauthenticated.
#
# Health endpoints must work without keys because:
#   1. Render uses this to check the server is alive
#   2. UptimeRobot pings this every 5 minutes (keeps Render
#      free tier from sleeping — see deployment notes)
#   3. Your co-founder can verify the server is up before
#      entering his API key
#   4. Checking "is the server alive?" should never cost
#      a 19-second pipeline call
#
# This is standard in every production API.
# Bloomberg, Refinitiv, all have unauthenticated health checks.

@app.route("/health", methods=["GET"])
def health():
    """Server liveness check. No auth required."""
    return jsonify({
        "status":           "ok",
        "naxa_version":     NAXA_VERSION,
        "supported_events": SUPPORTED_EVENT_TYPES,
        "timestamp":        datetime.utcnow().isoformat() + "Z",
    }), 200

import os
from flask import send_from_directory

@app.route('/')
def dashboard():
    here = os.path.dirname(os.path.abspath(__file__))
    frontend = os.path.abspath(os.path.join(here, '..', 'frontend'))
    return send_from_directory(frontend, 'dashboard.html')

# ── GET /v1/events ────────────────────────────────────────────
#
# Lists supported event types and their parameters.
# This is called "API discovery" or "capability enumeration."
#
# Why this matters for AI agents:
#   An agent calling your API needs to know:
#     - What event types exist?
#     - What parameters does each take?
#     - What's the backtest basis for each?
#   Without this endpoint, agents must hardcode assumptions.
#   With it, agents can query capabilities at runtime —
#   enabling dynamic, self-updating agent workflows.
#
# Think of it like the instruments endpoint on a trading API:
#   GET /instruments returns what you can trade.
#   GET /v1/events returns what NAXA can analyze.

@app.route("/v1/events", methods=["GET"])
@require_api_key
def list_events():
    """Returns supported event types and their parameter schemas."""
    return jsonify({
        "supported_events": [
            {
                "type":        "canal_restriction",
                "description": "Shipping chokepoint capacity restriction (Panama Canal, Suez Canal)",
                "parameters": {
                    "event": {
                        "type":     "string",
                        "required": True,
                        "enum":     ["canal_restriction"],
                    },
                    "date": {
                        "type":     "string",
                        "required": True,
                        "format":   "YYYY-MM-DD",
                        "example":  "2023-08-01",
                    },
                    "severity": {
                        "type":     "float",
                        "required": False,
                        "default":  0.75,
                        "range":    "0.0–1.0",
                        "note":     "Proportion of normal capacity lost",
                    },
                    "no_synthesis": {
                        "type":     "boolean",
                        "required": False,
                        "default":  False,
                        "note":     "Set true to skip LLM summary. ~2-4s instead of ~19s.",
                    },
                },
                "confidence_basis": {
                    "n_events":       4,
                    "backtest_range": "2010–2023",
                    "methodology":    "sample_size_factor × magnitude_consistency",
                },
            }
        ],
        "naxa_version": NAXA_VERSION,
        "note":         "Additional event types (energy, agricultural) in roadmap.",
    }), 200


# ── POST /v1/analyze ──────────────────────────────────────────
#
# THE CORE ENDPOINT. NAXA's entire value proposition
# in a single HTTP call.
#
# REQUEST BODY (JSON):
#   {
#     "event":        "canal_restriction",   ← required
#     "date":         "2023-08-01",          ← required
#     "severity":     0.85,                  ← optional, default 0.75
#     "no_synthesis": false                  ← optional, default false
#   }
#
# RESPONSE: Gold Standard JSON schema v0.2.0
#
# TIMING (approximate):
#   With synthesis:    ~19s  (Gemini API latency dominates)
#   Without synthesis: ~3-5s (data fetch + scoring only)
#
# RESPONSE HEADERS:
#   X-Request-Id:     UUID for this request (for debugging)
#   X-Query-Time-Ms:  Wall-clock time from receipt to response
#
# QUANT CONCEPT — Idempotency:
#   Same inputs → equivalent outputs every time.
#   (query_id and generated_at will differ; data won't.)
#   Critical for agents that retry on network failure:
#   they can safely retry POST /v1/analyze without
#   producing duplicate or contradictory results.

@app.route("/v1/analyze", methods=["POST"])
@require_api_key
def analyze():
    """
    Core endpoint. Runs the full signal chain pipeline
    and returns Gold Standard JSON.
    """
    req_id        = str(uuid.uuid4())
    request_start = time.time()
    log.info(f"[{req_id}] POST /v1/analyze received")

    # ── Parse JSON body ────────────────────────────────────────
    # silent=True: returns None instead of crashing on bad JSON
    body = request.get_json(silent=True)

    if body is None:
        return _error_response(
            code    = "INVALID_JSON",
            message = "Request body must be valid JSON.",
            detail  = "Set header: Content-Type: application/json",
            status  = 400,
            req_id  = req_id,
        )

    # ── Extract + validate fields ──────────────────────────────
    event_type = body.get("event")
    event_date = body.get("date")
    severity   = body.get("severity",      0.75)
    no_synth   = body.get("no_synthesis",  False)

    # event: required, must be in supported types
    if not event_type:
        return _error_response(
            code    = "MISSING_FIELD",
            message = "Field 'event' is required.",
            detail  = f"Supported values: {SUPPORTED_EVENT_TYPES}",
            status  = 400,
            req_id  = req_id,
        )

    if event_type not in SUPPORTED_EVENT_TYPES:
        return _error_response(
            code    = "UNSUPPORTED_EVENT",
            message = f"Event type '{event_type}' is not supported.",
            detail  = f"Supported: {SUPPORTED_EVENT_TYPES}. See GET /v1/events.",
            status  = 422,
            req_id  = req_id,
        )

    # date: required, YYYY-MM-DD format
    if not event_date:
        return _error_response(
            code    = "MISSING_FIELD",
            message = "Field 'date' is required.",
            detail  = "Format: YYYY-MM-DD (e.g. '2023-08-01')",
            status  = 400,
            req_id  = req_id,
        )

    try:
        datetime.strptime(event_date, "%Y-%m-%d")
    except ValueError:
        return _error_response(
            code    = "INVALID_DATE",
            message = f"Invalid date format: '{event_date}'.",
            detail  = "Required format: YYYY-MM-DD",
            status  = 400,
            req_id  = req_id,
        )

    # severity: optional float, must be 0.0–1.0
    if not isinstance(severity, (int, float)) or not 0.0 <= float(severity) <= 1.0:
        return _error_response(
            code    = "INVALID_SEVERITY",
            message = f"Field 'severity' must be a float between 0.0 and 1.0. Got: {severity}",
            status  = 400,
            req_id  = req_id,
        )

    # no_synthesis: optional boolean
    if not isinstance(no_synth, bool):
        return _error_response(
            code    = "INVALID_FIELD",
            message = "Field 'no_synthesis' must be a boolean (true or false).",
            status  = 400,
            req_id  = req_id,
        )

    log.info(
        f"[{req_id}] event={event_type} date={event_date} "
        f"severity={severity} no_synthesis={no_synth}"
    )

    # ── Run Pipeline ───────────────────────────────────────────
    #
    # save_to_disk=False is the key change from CLI mode.
    # API callers receive the JSON in the HTTP response body.
    # Writing it to disk too would be wasted I/O, and on
    # concurrent requests with identical params, a race condition.

    try:
        gold_standard, _ = run_pipeline(
            event_type     = event_type,
            event_date     = event_date,
            severity       = float(severity),
            skip_synthesis = no_synth,
            save_to_disk   = False,
        )

    except ValueError as e:
        log.warning(f"[{req_id}] Validation error in pipeline: {e}")
        return _error_response(
            code    = "PIPELINE_VALIDATION_ERROR",
            message = str(e),
            status  = 400,
            req_id  = req_id,
        )

    except Exception as e:
        # Log full traceback server-side.
        # Return generic message client-side — never leak internals.
        log.exception(f"[{req_id}] Unexpected pipeline error: {e}")
        return _error_response(
            code    = "PIPELINE_ERROR",
            message = "An internal error occurred. The team has been notified.",
            detail  = "If this persists, try with no_synthesis=true to isolate the LLM layer.",
            status  = 500,
            req_id  = req_id,
        )

    # ── Build and return response ──────────────────────────────
    wall_clock_ms = int((time.time() - request_start) * 1000)
    log.info(f"[{req_id}] Complete — {wall_clock_ms}ms")

    response = make_response(jsonify(gold_standard), 200)
    # Headers agent builders can read without parsing the full JSON body
    response.headers["X-Request-Id"]    = req_id
    response.headers["X-Query-Time-Ms"] = str(wall_clock_ms)

    return response


# ============================================================
# SECTION 5: GLOBAL ERROR HANDLERS
# ============================================================
#
# Without these, Flask returns HTML for 404/405/500.
# AI agents cannot parse HTML. These handlers ensure
# every NAXA response is JSON — including framework errors.

@app.errorhandler(404)
def not_found(e):
    return _error_response(
        code    = "NOT_FOUND",
        message = "Endpoint not found.",
        detail  = "Available: POST /v1/analyze  GET /v1/events  GET /health",
        status  = 404,
    )

@app.errorhandler(405)
def method_not_allowed(e):
    return _error_response(
        code    = "METHOD_NOT_ALLOWED",
        message = "HTTP method not allowed on this endpoint.",
        detail  = "POST /v1/analyze requires POST. /health requires GET.",
        status  = 405,
    )

@app.errorhandler(500)
def internal_error(e):
    return _error_response(
        code    = "INTERNAL_ERROR",
        message = "An unexpected server error occurred.",
        status  = 500,
    )


# ============================================================
# SECTION 6: SERVER STARTUP
# ============================================================
#
# host="0.0.0.0"  — accept connections from any IP.
#   Required for Render (Render sends traffic from their
#   proxy, not localhost). Without this, Render can't reach
#   your Flask app even though it's running.
#
# PORT env var — Render injects its own PORT value.
#   Always read from env, fallback to 5000 for local.
#
# debug — NEVER True in production.
#   Debug mode exposes an interactive Python shell
#   to anyone who triggers an error. On a public URL,
#   that means arbitrary code execution on your server.
#   Use FLASK_ENV=development locally; production default is off.

if __name__ == "__main__":
    log.info("=" * 55)
    log.info(f"NAXA API v{NAXA_VERSION} — Starting server")
    log.info(f"  POST /v1/analyze  — requires Bearer token")
    log.info(f"  GET  /v1/events   — requires Bearer token")
    log.info(f"  GET  /health      — no auth")
    log.info("=" * 55)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)