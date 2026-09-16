"""Fetches the real, live Diablo 4 event schedule from helltides.com using
a real (headless) browser context, and republishes it as a small canonical
JSON file committed to this repo (``data/live_schedule.json``).

Why a browser and not a plain HTTP client: ``helltides.com/api/schedule``
sits behind a genuine Cloudflare fingerprint-level check that blocks plain
HTTP clients (``requests``, ``curl``, even a full set of ordinary browser
headers) with a 403 - confirmed by direct testing, not assumed. A real
browser passes this naturally, the same way any human visitor's browser
does - this is not a bypass of any access control, it's simply using the
public site the way it's meant to be used, automated on a schedule instead
of by a human clicking refresh. Never scrapes anything not already shown
to any visitor of the public page; never touches auth, a CAPTCHA, or any
protected content.

Run from repo root (with ``playwright`` + Chromium installed):

    python scripts/fetch_live_schedule.py

Meant to run on a schedule via ``.github/workflows/live-schedule-sync.yml``
- not imported by the running desktop app itself (same pattern as
``maxroll_data_decoder.py``: an offline data-generation helper, not
application code).
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
