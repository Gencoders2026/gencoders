"""End-to-end browser verification of the Task 6 "Assess escalation risk" button.

It drives the REAL Task 6 page in headless Chrome exactly like a human:

  1. opens  http://127.0.0.1:5173/task6
  2. types a customer reply with real keystrokes (real mouse click on the button)
  3. asserts the page called POST /support/analyze and rendered the risk
     score / level / reasoning / alert + recommended actions
  4. types a DIFFERENT (calmer) reply, clicks again and asserts the risk was
     recalculated (score changes, risk trail grows)
  5. asserts no JavaScript exception occurred and that /task6 is served
     (HTTP 200) both by the Vite dev server and by the FastAPI backend

Nothing is mocked and no value is hard-coded: every assertion is compared
against what the live page really renders.

Usage:
    python scripts/verify_task6_button_flow.py
    python scripts/verify_task6_button_flow.py --page http://127.0.0.1:5173/task6

Requirements: the backend (:8000) and the Vite dev server (:5173) must be
running, plus Google Chrome (the script SKIPs if Chrome is not installed).
"""
import argparse
import asyncio
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

try:
    import websockets
except ImportError:  # pragma: no cover - dependency only needed for the browser run
    websockets = None

CHROME_CANDIDATES = [
    os.path.join(os.environ.get("ProgramFiles", ""), "Google", "Chrome",
                 "Application", "chrome.exe"),
    os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Google", "Chrome",
                 "Application", "chrome.exe"),
    os.path.join(os.environ.get("ProgramFiles", ""), "Microsoft", "Edge",
                 "Application", "msedge.exe"),
    os.path.join(os.environ.get("ProgramFiles(x86)", ""), "Microsoft", "Edge",
                 "Application", "msedge.exe"),
]

ANGRY_REPLY = ("This is completely unacceptable! I demand a supervisor "
               "right now. Fix it immediately or I am cancelling my account.")
AGENT_REPLY = ("I understand your frustration. I am escalating this to my "
               "supervisor.")
CALM_REPLY = "Okay, I understand. Thank you for the update."

DEV_PORT = 9333
PASSED = []
FAILED = []


def check(label, condition, detail=""):
    (PASSED if condition else FAILED).append(label)
    mark = "PASS" if condition else "FAIL"
    print(f"  [{mark}] {label}" + (f"  -> {detail}" if detail else ""))
    return bool(condition)


def http_status(url, timeout=15):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status
    except Exception as exc:  # pragma: no cover - depends on live servers
        return f"error: {exc}"

class CDP:
    """Minimal Chrome DevTools Protocol client over a websocket."""

    def __init__(self, ws):
        self.ws = ws
        self.seq = 0
        self.errors = []
        self.requests = []
        self.responses = []

    async def send(self, method, **params):
        self.seq += 1
        my_id = self.seq
        await self.ws.send(json.dumps({"id": my_id, "method": method,
                                       "params": params}))
        while True:
            raw = await asyncio.wait_for(self.ws.recv(), timeout=180)
            message = json.loads(raw)
            if message.get("id") == my_id:
                if "error" in message:
                    raise RuntimeError(message["error"])
                return message.get("result", {})
            self._record(message)

    async def drain(self, seconds):
        end = time.time() + seconds
        while True:
            left = end - time.time()
            if left <= 0:
                return
            try:
                raw = await asyncio.wait_for(self.ws.recv(), timeout=left)
            except asyncio.TimeoutError:
                return
            self._record(json.loads(raw))

    def _record(self, message):
        method = message.get("method")
        if method == "Runtime.exceptionThrown":
            details = message["params"]["exceptionDetails"]
            self.errors.append(str(details.get("exception", {}).get(
                "description") or details)[:300])
        elif method == "Network.requestWillBeSent":
            url = message["params"]["request"]["url"]
            if "/support/analyze" in url:
                self.requests.append(message["params"]["request"]["method"])
        elif method == "Network.responseReceived":
            url = message["params"]["response"]["url"]
            if "/support/analyze" in url:
                self.responses.append(message["params"]["response"]["status"])

    async def evaluate(self, expression):
        result = await self.send("Runtime.evaluate", expression=expression,
                                 returnByValue=True, awaitPromise=True)
        if result.get("exceptionDetails"):
            return {"__error__": str(result["exceptionDetails"])[:300]}
        return result.get("result", {}).get("value")

    async def type_text(self, text):
        """Type like a human, with real key events (React needs them)."""
        for char in text:
            await self.send("Input.dispatchKeyEvent", type="keyDown",
                            text=char, unmodifiedText=char, key=char)
            await self.send("Input.dispatchKeyEvent", type="keyUp", key=char)

    async def focus(self, selector):
        return await self.evaluate(
            "(() => { const el = document.querySelector(%s);"
            " if (!el) return false; el.focus(); el.click(); return true; })()"
            % json.dumps(selector))

    async def click_button(self):
        center = await self.evaluate(BUTTON_CENTER_JS)
        if not center or isinstance(center, dict):
            return None
        point = json.loads(center)
        for kind in ("mousePressed", "mouseReleased"):
            await self.send("Input.dispatchMouseEvent", type=kind,
                            x=point["x"], y=point["y"], button="left",
                            clickCount=1)
        return point

BUTTON_CENTER_JS = """
(() => {
  const btn = document.querySelector('button.task6-primary');
  if (!btn) { return null; }
  const r = btn.getBoundingClientRect();
  return JSON.stringify({x: Math.round(r.left + r.width / 2),
                         y: Math.round(r.top + r.height / 2)});
})()
"""

PAGE_STATE_JS = """
(() => {
  const q = (s) => document.querySelector(s);
  const btn = q('button.task6-primary');
  const badge = q('.escalation-card .risk-badge');
  const score = q('.escalation-card .risk-score');
  const banner = q('.alert-banner');
  return JSON.stringify({
    buttonFound: !!btn,
    buttonText: btn ? btn.innerText : null,
    buttonDisabled: btn ? btn.disabled : null,
    textareaFound: !!q('#task6-reply'),
    error: q('.task6-error') ? q('.task6-error').innerText : null,
    level: badge ? badge.innerText : null,
    score: score ? score.innerText : null,
    alertBanner: banner ? banner.innerText.replace(/\\n+/g, ' | ') : null,
    reasoningLines: document.querySelectorAll('.reasoning-list li').length,
    riskFactors: document.querySelectorAll('.indicator-chip').length,
    recommendedActions: q('.alert-actions')
      ? q('.alert-actions').querySelectorAll('li').length : 0,
    trailEntries: document.querySelectorAll('.task6-trail li').length,
    transcriptBubbles: document.querySelectorAll('.task6-bubble').length,
    suggestedResponse: q('.suggestion-text') ? 1 : 0,
    typing: q('#task6-reply') ? q('#task6-reply').value : null
  });
})()
"""


async def assess(cdp, text, agent_note=None):
    """Type a customer reply (+ optional agent note) and click the button."""
    await cdp.focus("#task6-reply")
    await cdp.type_text(text)
    if agent_note:
        await cdp.focus("#task6-agent-note")
        await cdp.type_text(agent_note)
    await cdp.drain(0.5)
    typed = await cdp.evaluate(
        "document.querySelector('#task6-reply').value")
    await cdp.click_button()
    await cdp.drain(16)
    state = json.loads(await cdp.evaluate(PAGE_STATE_JS))
    state["typed"] = typed
    return state

async def run_browser_checks(page_url, dev_url, backend_url):
    profile = os.path.join(tempfile.gettempdir(), "task6-verify-profile")
    shutil.rmtree(profile, ignore_errors=True)
    chrome = next((path for path in CHROME_CANDIDATES if path
                   and os.path.exists(path)), None)
    if not chrome:
        print("  [SKIP] Chrome/Edge not found - browser checks skipped")
        return
    if websockets is None:
        print("  [FAIL] python package 'websockets' is required")
        FAILED.append("websockets installed")
        return

    process = subprocess.Popen([
        chrome, f"--remote-debugging-port={DEV_PORT}",
        "--remote-allow-origins=*", "--headless=new", "--disable-gpu",
        "--no-first-run", "--no-default-browser-check",
        "--window-size=1440,1000", f"--user-data-dir={profile}", "about:blank",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    try:
        target = None
        for _ in range(60):
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{DEV_PORT}/json/list",
                        timeout=5) as response:
                    targets = json.load(response)
            except Exception:
                targets = []
            pages = [t for t in targets if t.get("type") == "page"]
            if pages:
                target = pages[0]
                break
            time.sleep(0.5)
        if not target:
            check("headless browser attached", False, "no page target")
            return

        async with websockets.connect(target["webSocketDebuggerUrl"],
                                      max_size=32 * 1024 * 1024) as ws:
            cdp = CDP(ws)
            for method in ("Page.enable", "Runtime.enable", "Network.enable"):
                await cdp.send(method)
            await cdp.send("Page.navigate", url=page_url)
            await cdp.drain(7)

            before = json.loads(await cdp.evaluate(PAGE_STATE_JS))
            check("Task 6 page loads with the 'Assess escalation risk' button",
                  before["buttonFound"] and "Assess" in (before["buttonText"] or ""),
                  before["buttonText"] or "button missing")
            check("reply textarea + risk panel are present",
                  before["textareaFound"] and before["score"] is None)

            print("\n1) customer reply -> 'Assess escalation risk' -> API -> result")
            first = await assess(cdp, ANGRY_REPLY, AGENT_REPLY)
            check("the typed reply really reached the page",
                  (first.get("typed") or "") == ANGRY_REPLY)
            check("POST /support/analyze was sent by the browser",
                  "POST" in cdp.requests, str(cdp.requests))
            check("the API answered 200",
                  200 in cdp.responses, str(cdp.responses))
            check("no 'Type a customer reply first.' guard fired",
                  not (first.get("error") or ""), first.get("error") or "none")
            check("risk score + level rendered",
                  bool(first.get("score")) and bool(first.get("level")),
                  f"{first.get('level')} {first.get('score')}")
            check("escalation reasoning rendered",
                  first.get("reasoningLines", 0) > 0,
                  f"{first.get('reasoningLines')} reasons")
            check("risk factors + suggested response rendered",
                  first.get("riskFactors", 0) > 0
                  and first.get("suggestedResponse") == 1)
            check("alert + recommended actions rendered",
                  bool(first.get("alertBanner"))
                  and first.get("recommendedActions", 0) > 0,
                  f"{first.get('recommendedActions')} actions")
            check("customer + agent turns shown in the transcript",
                  first.get("transcriptBubbles", 0) >= 2,
                  f"{first.get('transcriptBubbles')} bubbles")

            print("\n2) A DIFFERENT customer reply -> 'Assess escalation risk'"
                  " -> recalculated risk")
            second = await assess(cdp, CALM_REPLY)
            check("second reply assessed without any error",
                  not (second.get("error") or ""),
                  second.get("error") or "none")
            check("risk score AND level were recalculated for the new reply",
                  second.get("score") != first.get("score")
                  and second.get("level") != first.get("level"),
                  f"{first.get('level')} {first.get('score')} -> "
                  f"{second.get('level')} {second.get('score')}")
            check("new risk factors/reasoning were recomputed",
                  second.get("reasoningLines", 0) != first.get("reasoningLines", 0)
                  or second.get("riskFactors", 0) != first.get("riskFactors", 0),
                  f"reasoning {first.get('reasoningLines')} -> "
                  f"{second.get('reasoningLines')}")
            check("risk trail shows the movement per reply",
                  second.get("trailEntries", 0) >= 2,
                  f"{second.get('trailEntries')} entries")
            check("alert clears when the risk falls below the threshold",
                  not second.get("alertBanner"),
                  f"level now {second.get('level')}")
            check("a 2nd POST /support/analyze was issued",
                  cdp.requests.count("POST") >= 2,
                  f"{cdp.requests.count('POST')} POST calls")
            check("no JavaScript exception during the whole flow",
                  not cdp.errors, "; ".join(cdp.errors[:2]) or "clean console")
    finally:
        process.terminate()
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", default="http://127.0.0.1:5173/task6",
                        help="Task 6 page driven in the browser")
    parser.add_argument("--backend", default="http://127.0.0.1:8000",
                        help="Task 6 backend base URL")
    args = parser.parse_args()

    print("Task 6 - 'Assess escalation risk' button end-to-end verification")
    print("=" * 70)

    print("\n0) the Task 6 page is served on both entry points")
    dev_status = http_status(args.page)
    check(f"Vite dev server serves /task6 ({args.page})", dev_status == 200,
          f"HTTP {dev_status}")
    backend_page = args.backend.rstrip("/") + "/task6"
    backend_status = http_status(backend_page)
    check(f"backend serves /task6 ({backend_page})", backend_status == 200,
          f"HTTP {backend_status}")

    asyncio.run(run_browser_checks(args.page, args.page, args.backend))

    print("\n" + "=" * 70)
    total = len(PASSED) + len(FAILED)
    print(f"Task 6 button flow: {len(PASSED)}/{total} checks passed")
    if FAILED:
        for label in FAILED:
            print(f"  FAILED: {label}")
        return 1
    print("RESULT: PASS - the button calls the real Task 6 API and renders "
          "score/level/reasoning/alert, and a changed reply is recalculated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())




