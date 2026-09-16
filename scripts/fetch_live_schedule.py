"""Fetches the real, live Diablo 4 event schedule from helltides.com using
a real (headless) browser context, and reshapes it into a small canonical
JSON structure ({"source", "fetched_at", "events": [...]})..

**CONFIRMED NOT VIABLE FROM ANY CLOUD/CI INFRASTRUCTURE - do not wire this
into a GitHub Actions cron job.** helltides.com/api/schedule sits behind a
Cloudflare check that blocks not just plain HTTP clients (requests/curl,
even with a full set of ordinary browser headers - 403 every time) but
ALSO a real, unmodified headless Chromium running via Playwright, tested
for real on an actual GitHub Actions ubuntu-latest runner (a genuinely
different network than this project's dev sandbox) - still a 403. This
means the block is not (only) about "looks like a script" or "looks
headless" - it very likely also scores by IP reputation, and GitHub
Actions' runner IP ranges are well-known datacenter ranges many Cloudflare
configurations deprioritize/block outright. No further header/fingerprint
tweaking was attempted past this point - that would cross into the
fingerprint-spoofing/bypass territory this project has explicitly ruled
out, not just a compatibility issue to engineer around.

This script's fetch+reshape LOGIC is still real and correct (confirmed
against real helltides.com data earlier in this project) and is kept as
a reusable building block IF a legitimate way to run it from a
non-datacenter IP is ever found (e.g. manually, or on a schedule, from a
real residential machine's own browser context - not attempted or
promised as a shipped feature). It is not currently wired into any
workflow or into the running desktop app. See PROJECT_STATUS.md's
"Diablo 4 Live Event Data" entries for the full investigation and
current honest conclusion (DATA UNAVAILABLE is the correct terminal
state, not a stopgap).

Run from repo root (with ``playwright`` + Chromium installed) purely for
manual experimentation:

    python scripts/fetch_live_schedule.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

from playwright.sync_api import sync_playwright

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(REPO_ROOT, "data", "live_schedule.json")

SCHEDULE_URL = "https://helltides.com/api/schedule"


def fetch_raw_schedule() -> dict:
    """Fetch the real, live JSON response using a real headless browser
    context - the only method confirmed (by direct testing) to actually
    get past helltides.com's Cloudflare fingerprint check. Raises if the
    page doesn't return valid JSON (network failure, site change, etc.) -
    the caller must not write a partial/invalid file on failure."""

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            page = browser.new_page()
            response = page.goto(SCHEDULE_URL, wait_until="load", timeout=30000)

            if response is None or not response.ok:
                status = response.status if response else "no response"
                raise RuntimeError(f"helltides.com returned {status}")

            body_text = page.locator("body").inner_text()
            return json.loads(body_text)
        finally:
            browser.close()


def to_canonical_events(raw: dict) -> list[dict]:
    """Reshape helltides.com's real ``{"world_boss": [...], "legion": [...],
    "helltide": [...]}`` response into one flat, type-tagged canonical list -
    only ever using fields the real API actually provides for each type
    (confirmed live: only ``world_boss`` entries have a real ``boss``
    name and ``zone``; ``legion``/``helltide`` have neither). Never
    invents a field that isn't present."""

    events = []

    for boss in raw.get("world_boss") or []:
        if boss.get("type", "world_boss") != "world_boss":
            continue
        zone_list = boss.get("zone") or []
        events.append({
            "type": "world_boss",
            "startTime": boss.get("startTime"),
            "timestamp": boss.get("timestamp"),
            "name": boss.get("boss"),
            "location": zone_list[0]["name"] if zone_list else None,
        })

    for legion in raw.get("legion") or []:
        if legion.get("type", "legion") != "legion":
            continue
        events.append({
            "type": "legion",
            "startTime": legion.get("startTime"),
            "timestamp": legion.get("timestamp"),
            "name": None,
            "location": None,
        })

    for helltide in raw.get("helltide") or []:
        if helltide.get("type", "helltide") != "helltide":
            continue
        events.append({
            "type": "helltide",
            "startTime": helltide.get("startTime"),
            "timestamp": helltide.get("timestamp"),
            "name": None,
            "location": None,
        })

    events.sort(key=lambda e: e["timestamp"] or 0)
    return events


def main() -> int:
    try:
        raw = fetch_raw_schedule()
    except Exception as exc:  # noqa: BLE001 - any failure here must not
        # write a stale/partial file; the app's own freshness check
        # already treats an old file as DATA UNAVAILABLE, so a failed
        # fetch simply means the existing file ages out naturally.
        print(f"Kunne ikke hente live schedule: {exc}", file=sys.stderr)
        return 1

    events = to_canonical_events(raw)

    if not events:
        print("helltides.com svarede, men uden nogen events - skriver ikke en tom fil.", file=sys.stderr)
        return 1

    output = {
        "source": "helltides.com",
        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "events": events,
    }

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"OK: wrote {len(events)} events to {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
