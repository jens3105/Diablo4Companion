"""ISOLATED PROOF-OF-CONCEPT - not part of Diablo4Companion.

Question this answers: does a real WebView2 browser context (via
pywebview's edgechromium backend - the same Edge/Chromium engine already
built into Windows 10/11) get past helltides.com's Cloudflare check when
run on a REAL Windows machine with a REAL residential internet
connection?

This must be run on an actual Windows PC with a normal home internet
connection - it CANNOT be meaningfully tested from a Linux dev sandbox
or from any cloud CI runner (GitHub Actions included), since those all
use datacenter IP ranges - exactly the category already proven blocked.
The entire premise being tested here is "does a real consumer IP change
the outcome", so testing it from a datacenter IP would prove nothing.

No Cloudflare bypass, no CAPTCHA bypass, no fingerprint spoofing, no
proxy, no VPN, no anti-bot tricks of any kind - this is a completely
normal, unmodified WebView2 browser window doing exactly what a human's
browser would do when visiting the page.

SETUP (on the Windows PC, in a terminal/PowerShell):

    pip install pywebview

    (pywebview does NOT bundle a browser - it uses the WebView2 runtime
    already installed by Windows Update on virtually all Windows 10/11
    machines. If this script fails with an error mentioning WebView2 not
    being found, that itself is a real, useful result to report.)

RUN:

    python webview2_poc.py

This writes two files next to itself:
  - webview2_poc_log.json   - a summary of what happened (always written)
  - webview2_poc_result.json - the full raw JSON from helltides.com,
                                only written if real JSON was received

Please share the CONTENTS of webview2_poc_log.json (and ideally
webview2_poc_result.json) back - that is the actual evidence needed,
not a paraphrase of what happened.
"""

import json
import threading

import webview

TARGET_URL = "https://helltides.com/api/schedule"
LOG_PATH = "webview2_poc_log.json"
RESULT_PATH = "webview2_poc_result.json"

result_log = {"target_url": TARGET_URL}


def _looks_like_cloudflare_challenge(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in (
            "checking your browser",
            "just a moment",
            "cf-browser-verification",
            "cloudflare",
            "attention required",
            "ray id",
        )
    )


def _write_log():
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(result_log, f, indent=2, ensure_ascii=False, default=str)
    print("\n=== RESULT ===")
    print(json.dumps(result_log, indent=2, ensure_ascii=False, default=str))


def on_loaded():
    window = webview.windows[0]

    try:
        body_text = window.evaluate_js("document.body.innerText")
    except Exception as exc:  # noqa: BLE001 - this IS the diagnostic
        result_log["evaluate_js_error"] = f"{type(exc).__name__}: {exc}"
        _write_log()
        window.destroy()
        return

    result_log["raw_length"] = len(body_text) if body_text else 0
    result_log["raw_preview"] = (body_text or "")[:300]
    result_log["looks_like_cloudflare_challenge"] = _looks_like_cloudflare_challenge(body_text)

    try:
        data = json.loads(body_text)
    except (json.JSONDecodeError, TypeError) as exc:
        result_log["json_parsed"] = False
        result_log["json_error"] = str(exc)
        _write_log()
        window.destroy()
        return

    result_log["json_parsed"] = True
    result_log["top_level_keys"] = list(data.keys())

    world_boss = data.get("world_boss") or []
    legion = data.get("legion") or []
    helltide = data.get("helltide") or []

    result_log["world_boss_count"] = len(world_boss)
    result_log["legion_count"] = len(legion)
    result_log["helltide_count"] = len(helltide)

    if world_boss:
        wb = world_boss[0]
        result_log["world_boss_sample"] = {
            "boss": wb.get("boss"),
            "startTime": wb.get("startTime"),
            "timestamp": wb.get("timestamp"),
            "zone": wb.get("zone"),
            "type": wb.get("type"),
        }
    if legion:
        result_log["legion_sample"] = legion[0]
    if helltide:
        result_log["helltide_sample"] = helltide[0]

    with open(RESULT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    result_log["saved_full_response_to"] = RESULT_PATH

    _write_log()
    window.destroy()


def _timeout_guard():
    # Safety net only - if `loaded` never fires (network hang, WebView2
    # missing, etc.) this makes sure the script still exits and reports
    # something instead of hanging forever.
    import time

    time.sleep(30)
    if "json_parsed" not in result_log and "evaluate_js_error" not in result_log:
        result_log["timed_out"] = True
        _write_log()
        try:
            webview.windows[0].destroy()
        except Exception:
            pass


def main():
    window = webview.create_window(
        "WebView2 PoC - Diablo4Companion",
        TARGET_URL,
        hidden=True,
        width=200,
        height=200,
    )
    window.events.loaded += on_loaded

    threading.Thread(target=_timeout_guard, daemon=True).start()

    # gui="edgechromium" makes pywebview require the real WebView2/Edge
    # runtime rather than falling back to the older, weaker `mshtml`
    # (Internet Explorer engine) renderer on Windows - that fallback
    # would NOT be a fair test of "does a real modern browser pass this".
    webview.start(gui="edgechromium", debug=False)


if __name__ == "__main__":
    main()
