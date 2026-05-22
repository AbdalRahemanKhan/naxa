# ============================================================
# NAXA engine/event_detector.py
#
# Live Event Detection via RSS Feed Monitoring
# ============================================================
#
# WHAT THIS DOES:
#   Monitors shipping news RSS feeds every 6 hours.
#   When a disruption keyword fires, classifies the event,
#   estimates severity from article text, and auto-runs
#   the NAXA pipeline. Stores the result so the analyst
#   dashboard shows "Latest Detected Event" on load.
#
# WHY RSS OVER GDELT:
#   RSS feeds from shipping publications are pre-filtered
#   by domain experts to exactly the events NAXA tracks.
#   GDELT covers all global events and requires complex
#   CAMEO code filtering to find shipping disruptions.
#   Splash247 and Hellenic Shipping News already do that
#   curation for us — for free.
#
# SEVERITY ESTIMATION:
#   Keyword-weighted scoring from article text.
#   Deterministic and auditable — not ML.
#   The severity_note field flags it as estimated.
#   Analyst should verify before acting on it.
#
# STORAGE:
#   data/latest_detected.json  → most recent full analysis
#   data/detected_events/      → timestamped archive
#   data/seen_urls.json        → deduplication store
# ============================================================

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import feedparser

sys.path.insert(0, str(Path(__file__).parent.parent))

log = logging.getLogger("naxa.detector")


# ============================================================
# SECTION 1: PATHS AND DIRECTORIES
# ============================================================

DATA_DIR       = Path(__file__).parent.parent / "data"
ALERTS_DIR     = DATA_DIR / "detected_events"
SEEN_URLS_FILE = DATA_DIR / "seen_urls.json"
LATEST_FILE    = DATA_DIR / "latest_detected.json"

for _dir in [ALERTS_DIR]:
    _dir.mkdir(parents=True, exist_ok=True)


# ============================================================
# SECTION 2: RSS FEED SOURCES
# ============================================================
#
# All free. No API keys. Updates as news publishes.
#
# SELECTION RATIONALE:
#   Splash247       → global shipping news, high volume
#   Hellenic        → Mediterranean + Suez coverage
#   AJOT            → US port + trade focus
#   Maritime Exec   → incident + regulatory coverage
#
# If a feed URL returns empty, feedparser handles it
# gracefully — no crash, just skips that source.
# Test each feed with: python -m engine.event_detector

RSS_FEEDS = [
    "https://splash247.com/feed/",
    "https://www.hellenicshippingnews.com/feed/",
    "https://www.ajot.com/news/rss",
    "https://www.maritimeexecutive.com/articles/rss.xml",
]


# ============================================================
# SECTION 3: DISRUPTION DETECTION RULES
# ============================================================
#
# STRUCTURE PER RULE:
#   event_type        → maps to NAXA's SUPPORTED_EVENT_TYPES
#   trigger_phrases   → any one phrase fires the alert
#   severity_base     → starting severity before modifiers
#   severity_modifiers → add/subtract from base severity
#
# SEVERITY SCALE:
#   0.20 = very minor, barely noteworthy
#   0.50 = moderate, meaningful disruption
#   0.75 = major, significant capacity loss
#   0.95 = extreme, near-complete closure
#
# QUANT PRINCIPLE — Conservative baseline:
#   We start at 0.60-0.70 and adjust DOWN for mild language,
#   UP for severe language. This is safer than starting high
#   and reducing — it avoids false positives on routine news.

DETECTION_RULES = [
    {
        "event_type":      "canal_restriction",
        "trigger_phrases": [
            "panama canal drought", "gatun lake", "canal water level",
            "panama canal restriction", "canal capacity", "acp notice",
            "panama canal transit", "canal slot",
        ],
        "severity_base": 0.60,
        "severity_modifiers": {
            "complete blockage": +0.35, "fully blocked":    +0.30,
            "record low":        +0.25, "severe drought":   +0.20,
            "major restriction": +0.15, "drought":          +0.10,
            "restriction":       +0.05, "minor":            -0.20,
            "temporary":         -0.10, "partial":          -0.10,
            "resolved":          -0.30, "lifted":           -0.35,
        }
    },
    {
        "event_type":      "canal_restriction",
        "trigger_phrases": [
            "suez canal block", "suez canal clos", "vessel grounded suez",
            "suez canal incident", "ever given",
        ],
        "severity_base": 0.70,
        "severity_modifiers": {
            "completely blocked": +0.25, "grounded":  +0.25,
            "full blockage":      +0.25, "closure":   +0.20,
            "disruption":         +0.05, "delay":     -0.10,
            "cleared":            -0.35, "refloated": -0.35,
        }
    },
    {
        "event_type":      "canal_restriction",
        "trigger_phrases": [
            "red sea attack", "houthi attack", "houthi missile",
            "red sea shipping halted", "red sea suspended",
            "bab-el-mandeb closure", "gulf of aden attack",
        ],
        "severity_base": 0.68,
        "severity_modifiers": {
            "suspended transits": +0.17, "halted all":    +0.15,
            "missile strike":     +0.12, "drone attack":  +0.12,
            "all carriers":       +0.10, "rerouting":     +0.07,
            "tensions":           -0.10, "warning":       -0.08,
            "ceasefire":          -0.25, "negotiations":  -0.15,
        }
    },
    {
        "event_type":      "canal_restriction",
        "trigger_phrases": [
            "strait of hormuz clos", "hormuz blockage",
            "hormuz shipping halted", "iran seizes vessel",
        ],
        "severity_base": 0.65,
        "severity_modifiers": {
            "blocked":  +0.25, "closure": +0.20,
            "tensions": -0.05, "drill":   -0.10,
        }
    },
]


# ============================================================
# SECTION 4: DEDUPLICATION HELPERS
# ============================================================
#
# We track article URLs we've already processed.
# Without this, every 6-hour scan would re-detect
# the same articles and spam the pipeline.
#
# Storage: simple JSON file. No database needed.
# Cap: 1000 URLs max to prevent unbounded file growth.

def _load_seen_urls() -> set:
    if SEEN_URLS_FILE.exists():
        try:
            return set(json.loads(SEEN_URLS_FILE.read_text()))
        except Exception:
            return set()
    return set()


def _save_seen_urls(urls: set) -> None:
    url_list = list(urls)[-1000:]
    SEEN_URLS_FILE.write_text(json.dumps(url_list))


# ============================================================
# SECTION 5: SEVERITY ESTIMATOR
# ============================================================
#
# WHY NOT ML:
#   ML models need training data we don't have yet.
#   Keyword scoring is transparent, auditable, and tunable.
#   A Citi market-maker can read the DETECTION_RULES dict
#   and understand exactly why severity was set to 0.75.
#   They cannot do that with a neural network.
#   Transparency is more valuable than marginal accuracy here.

def _estimate_severity(text: str, rule: dict) -> float:
    """
    Estimates severity from article text using keyword modifiers.
    Deterministic and auditable. Clamped to [0.20, 0.95].
    """
    text_lower = text.lower()
    severity   = rule["severity_base"]

    for phrase, delta in rule["severity_modifiers"].items():
        if phrase in text_lower:
            severity += delta
            log.debug(f"[Detector] Modifier '{phrase}': {delta:+.2f}")

    return round(max(0.20, min(0.95, severity)), 2)


# ============================================================
# SECTION 6: RSS SCANNER
# ============================================================

def scan_feeds() -> list:
    """
    Scans all RSS feeds for new shipping disruption articles.

    Returns list of detected event dicts, each containing:
        event_type, trigger_date, estimated_severity,
        headline, article_url, source_feed, detected_at
    """
    seen_urls = _load_seen_urls()
    detected  = []

    for feed_url in RSS_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            log.info(f"[Detector] {feed_url.split('/')[2]} — "
                     f"{len(feed.entries)} articles fetched")
        except Exception as e:
            log.warning(f"[Detector] Feed failed ({feed_url}): {e}")
            continue

        for entry in feed.entries[:25]:
            article_url = entry.get("link", "")
            if not article_url or article_url in seen_urls:
                continue

            title   = entry.get("title",   "")
            summary = entry.get("summary", "")
            text    = f"{title} {summary}".lower()

            for rule in DETECTION_RULES:
                if not any(phrase in text for phrase in rule["trigger_phrases"]):
                    continue

                # Parse publish date, fall back to today
                pub = entry.get("published_parsed")
                trigger_date = (
                    datetime(pub.tm_year, pub.tm_mon, pub.tm_mday)
                    .strftime("%Y-%m-%d")
                    if pub else
                    datetime.now().strftime("%Y-%m-%d")
                )

                severity = _estimate_severity(text, rule)

                detected.append({
                    "event_type":         rule["event_type"],
                    "trigger_date":       trigger_date,
                    "estimated_severity": severity,
                    "headline":           title,
                    "article_url":        article_url,
                    "source_feed":        feed_url,
                    "detected_at":        datetime.now(timezone.utc).isoformat(),
                    "severity_note":      (
                        "Severity estimated from keyword analysis. "
                        "Analyst should verify before acting."
                    ),
                })

                seen_urls.add(article_url)
                log.info(f"[Detector] ALERT | sev={severity} | {title[:65]}")
                break  # one rule match per article

    _save_seen_urls(seen_urls)
    log.info(f"[Detector] Scan complete — {len(detected)} new event(s) detected")
    return detected


# ============================================================
# SECTION 7: DETECT AND ANALYZE (main scheduled function)
# ============================================================
#
# This is the function the scheduler calls every 6 hours.
# It ties detection → pipeline → storage together.
#
# DESIGN CHOICE — highest severity wins:
#   If multiple events fire in one scan, we analyze the most
#   severe one. An analyst opening the dashboard sees the
#   most critical event first. All events are still archived.

def detect_and_analyze(alerts=None) -> dict | None:
    """
    Scheduled function: scan → classify → analyze → store.
    Accepts pre-detected alerts to avoid double-scanning when
    called from the manual test block.
    """
    from analyze import run_pipeline

    log.info("[Detector] ── Scheduled scan starting ──")

    if alerts is None:          # called by scheduler — scan fresh
        alerts = scan_feeds()

    if not alerts:
        log.info("[Detector] No new events. Nothing to analyze.")
        return None

    # Take highest-severity alert from this scan
    top = max(alerts, key=lambda a: a["estimated_severity"])
    log.info(
        f"[Detector] Analyzing: {top['event_type']} | "
        f"{top['trigger_date']} | sev={top['estimated_severity']}"
    )

    try:
        gold_standard, _ = run_pipeline(
            event_type     = top["event_type"],
            event_date     = top["trigger_date"],
            severity       = top["estimated_severity"],
            skip_synthesis = False,
            save_to_disk   = False,
        )
    except Exception as e:
        log.error(f"[Detector] Pipeline failed: {e}")
        return None

    # Attach detection metadata so the dashboard knows HOW it was found
    gold_standard["detection_metadata"] = {
        "detected_at":          top["detected_at"],
        "source_headline":      top["headline"],
        "source_url":           top["article_url"],
        "source_feed":          top["source_feed"],
        "severity_note":        top["severity_note"],
        "alerts_this_scan":     len(alerts),
        "auto_detected":        True,
    }

    # Save as latest (dashboard reads this on load)
    LATEST_FILE.write_text(
        json.dumps(gold_standard, indent=2, ensure_ascii=False)
    )

    # Archive with timestamp
    ts       = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    arc_name = f"{top['event_type']}_{top['trigger_date']}_{ts}.json"
    (ALERTS_DIR / arc_name).write_text(
        json.dumps(gold_standard, indent=2, ensure_ascii=False)
    )

    log.info(f"[Detector] ✓ Stored: {arc_name}")
    return gold_standard


# ============================================================
# SECTION 8: READ HELPERS (called by Flask endpoints)
# ============================================================

def get_latest() -> dict | None:
    """Returns the most recently auto-detected + analyzed event."""
    if LATEST_FILE.exists():
        try:
            return json.loads(LATEST_FILE.read_text())
        except Exception:
            return None
    return None


def get_recent_alerts(limit: int = 10) -> list:
    """Returns lightweight summaries of recent detected events."""
    files     = sorted(ALERTS_DIR.glob("*.json"), reverse=True)[:limit]
    summaries = []

    for f in files:
        try:
            data = json.loads(f.read_text())
            meta = data.get("detection_metadata", {})
            summaries.append({
                "detected_at": meta.get("detected_at"),
                "headline":    meta.get("source_headline"),
                "source_url":  meta.get("source_url"),
                "event_type":  data.get("event", {}).get("type"),
                "severity":    data.get("event", {}).get("severity_score"),
                "query_id":    data.get("query_id"),
            })
        except Exception:
            continue

    return summaries


# ============================================================
# SECTION 9: MANUAL TEST
# ============================================================
#
# Run from naxa/ directory:
#   python -m engine.event_detector
#
# This scans all feeds right now and prints what it finds.
# Run this first to verify feed URLs are reachable.

if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s"
    )

    print("=" * 65)
    print("NAXA Event Detector — Manual Scan Test")
    print("=" * 65)
    print(f"  Feeds:    {len(RSS_FEEDS)}")
    print(f"  Rules:    {len(DETECTION_RULES)}")
    print("=" * 65)

    print("\nScanning feeds...")
    alerts = scan_feeds()

    if alerts:
        print(f"\n  {len(alerts)} disruption event(s) detected:\n")
        for a in alerts:
            print(f"  [{a['trigger_date']}] sev={a['estimated_severity']} "
                  f"| {a['headline'][:60]}")

        print("\nRunning full analysis on top event (takes ~7s)...")
        result = detect_and_analyze(alerts=alerts)   # pass alerts, skip re-scan
        if result:
            print(f"\n  ✓ Analysis complete")
            print(f"  Query ID: {result.get('query_id')}")
            meta = result.get("detection_metadata", {})
            print(f"  Source:   {meta.get('source_headline','')[:60]}")
    else:
        print("\n  No new shipping disruptions detected in current feeds.")
        print("  (This is normal — disruptions are infrequent.)")
        print("\n  To test the full pipeline, run:")
        print("  python analyze.py --event canal_restriction "
              "--date 2023-12-19 --severity 0.80")