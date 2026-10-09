"""
Check the Task 5 Knowledge Recommendation agent actually retrieves
policy snippets for every scenario, not just the happy path.

Run with the backend already listening on http://127.0.0.1:8000
"""

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"

QUERIES = [
    "I want a refund for my damaged order",
    "where is my delayed order tracking",
    "my payment keeps failing at checkout",
    "I cannot login to my account",
    "please cancel my subscription",
    "what is your refund policy window",
]


def call(query, session):
    payload = {"query": query, "session_id": session, "sender": "customer"}
    request = urllib.request.Request(
        BASE + "/support/analyze",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    return json.loads(urllib.request.urlopen(request, timeout=60).read())


def main():
    failed = 0
    available_seen = False

    for i, query in enumerate(QUERIES):
        data = call(query, f"knowledge-probe-{i}")
        results = data.get("knowledge_results") or []
        available = data.get("knowledge_available")
        available_seen = available_seen or bool(available)
        ok = bool(results)
        if not ok:
            failed += 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {query[:44]:46} "
              f"results={len(results)} available={available}")
        if results:
            top = results[0].get("text", "")
            print(f"         top: {top[:66]!r}")

    print()
    if not available_seen:
        print("  [FAIL] the RAG retriever reported itself unavailable")
        failed += 1
    else:
        print("  [PASS] the RAG retriever is available")

    print()
    print(f"  checks failed : {failed}")
    print()
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
