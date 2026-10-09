"""
Smoke-check that the Support Console served on port 8000 is the built
React bundle and that it really renders the Escalation Risk Monitor
fields (gauge, level, indicators, reasoning, alert banner).

Run with the backend already listening on http://127.0.0.1:8000
"""

import re
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"

PASS = 0
FAIL = 0


def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label} :: {detail}")


def main():
    html = urllib.request.urlopen(BASE + "/", timeout=30).read().decode(
        "utf-8", "replace"
    )
    check("root serves an HTML page", "<script" in html, html[:200])
    check("root mounts the React app", 'id="root"' in html, "no #root")

    match = re.search(r"/assets/[A-Za-z0-9._-]+\.js", html)
    check("a built JS bundle is referenced", match is not None, "no bundle")
    if not match:
        sys.exit(1)

    bundle = urllib.request.urlopen(
        BASE + match.group(0), timeout=60
    ).read().decode("utf-8", "replace")
    print(f"  bundle: {match.group(0)} ({len(bundle):,} bytes)")

    # The strings the Escalation Risk Monitor card renders, taken from
    # the real SupportConsole.jsx field accesses.
    for label, needle in [
        ("Escalation Risk Monitor card", "Escalation Risk"),
        ("risk gauge score", "escalation_score"),
        ("risk level pill", "escalation_level"),
        ("risk trend", "escalation_trend"),
        ("satisfaction trend", "satisfaction_trend"),
        ("alert banner", "Escalation Alert"),
        ("alert threshold", "Threshold:"),
        ("indicator chips", "escalation_indicators"),
        ("reasoning list", "escalation_reasoning"),
        ("recommended actions", "recommended_actions"),
        ("negative streak", "negative_streak"),
    ]:
        check(f"bundle renders {label}", needle in bundle,
              f"missing {needle!r}")

    # Coach / knowledge cards from Tasks 4, 5 and 6.
    for label, needle in [
        ("intent badge", "intent"),
        ("emotion badge", "emotion"),
        ("frustration gauge", "frustration_level"),
        ("sentiment pill", "sentiment"),
        ("confidence meter", "confidence"),
        ("knowledge results", "knowledge_results"),
        ("suggested response", "suggested_response"),
        ("response evaluation", "response_evaluation"),
        ("coaching tips", "coaching_guidance"),
    ]:
        check(f"bundle renders {label}", needle in bundle,
              f"missing {needle!r}")

    print()
    print(f"  checks passed : {PASS}")
    print(f"  checks failed : {FAIL}")
    print()
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
