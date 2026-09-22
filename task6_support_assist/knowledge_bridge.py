"""
Bridge to the Knowledge Recommendation Agent.

Wraps the FAISS-based RAG retriever that lives in the `rag/` folder so
the support-assistance pipeline (Task 6) can ground its response
suggestions in the customer-support knowledge base.

The import is lazy and fully guarded: if the vector database, the
embedding model or any dependency is unavailable, the bridge degrades
gracefully and returns an empty result list instead of breaking the
support API.
"""

import sys
import threading
from pathlib import Path
from typing import Dict, List, Optional

RAG_DIR = Path(__file__).resolve().parent.parent / "rag"

# Global lazy-initialisation state
_lock = threading.Lock()
_search_fn = None
_init_error: Optional[str] = None


def _get_search_fn():
    """
    Lazily import `semantic_search` from the rag package.

    The rag modules use flat imports (`from embeddings import model`),
    so the rag folder itself must be on sys.path.
    """
    global _search_fn, _init_error

    with _lock:
        if _search_fn is not None or _init_error is not None:
            return _search_fn

        try:
            if str(RAG_DIR) not in sys.path:
                sys.path.insert(0, str(RAG_DIR))

            # The rag vector_store resolves "vector_db" relative to the
            # current working directory. Pin it to the rag folder so
            # retrieval works no matter where the API server is
            # started from.
            import vector_store as vector_store_module  # noqa: E402

            vector_db_dir = RAG_DIR / "vector_db"
            vector_store_module.VECTOR_DB_PATH = str(vector_db_dir)
            vector_store_module.INDEX_PATH = str(
                vector_db_dir / "index.faiss"
            )
            vector_store_module.METADATA_PATH = str(
                vector_db_dir / "metadata.pkl"
            )

            from retriever import semantic_search  # noqa: E402

            _search_fn = semantic_search
        except Exception as exc:  # pragma: no cover - depends on env
            _init_error = f"{type(exc).__name__}: {exc}"
            _search_fn = None

        return _search_fn


def knowledge_available() -> bool:
    """Return True when the RAG retriever could be loaded."""
    return _get_search_fn() is not None


def knowledge_status() -> Dict:
    """Return a small diagnostic payload about the knowledge agent."""
    return {
        "available": knowledge_available(),
        "error": _init_error,
        "source": str(RAG_DIR),
    }


# ==========================================================
# KNOWLEDGE RETRIEVAL — INTENT -> ALLOWED DOCUMENT MAP
# ==========================================================
# Maps each detected customer intent to the knowledge-base document
# sources that are relevant to it. When ``search_knowledge`` is called
# with an ``intent``, only chunks from the allowed sources for that
# intent are returned, so the response suggestion, coaching guidance
# and escalation analysis stay grounded in contextually relevant
# information (e.g. delayed_order -> delivery/order docs, never
# payment_issues.txt).
#
# Sources are matched against the ``source`` field in each chunk's
# metadata (the filename the RAG chunker stored). A source is
# considered relevant if its name contains any of the keywords listed
# for the intent. ``general_inquiry`` has no restriction (all sources
# are allowed) because no specific topic has been detected yet.

_INTENT_SOURCE_KEYWORDS: Dict[str, List[str]] = {
    "refund_request": [
        "Refund", "Cancellation",
    ],
    # delayed_order: the knowledge base has no dedicated delivery/order
    # document, so the closest RELEVANT policies are the Refund Policy
    # (customers with undelivered orders often request refunds) and the
    # Cancellation Policy (order cancellation). application_issues.txt
    # is about app troubleshooting only and is NOT relevant here.
    "delayed_order": [
        "Refund", "Cancellation",
    ],
    "payment_failure": [
        "payment_issues", "Refund",
    ],
    "account_issue": [
        "login_issues",
    ],
    "cancellation": [
        "Cancellation", "Refund",
    ],
    # general_inquiry: no restriction — caller can still filter later
    # if it wants, but at detection time we do not know the topic yet.
    "general_inquiry": [],
}


def _allowed_sources_for_intent(intent: str) -> List[str]:
    """Return the intent-specific source keywords for ``intent``."""
    return _INTENT_SOURCE_KEYWORDS.get(intent, [])


def search_knowledge(
    query: str,
    top_k: int = 3,
    min_score: float = 0.0,
    intent: Optional[str] = None,
) -> List[Dict]:
    """
    Retrieve the most relevant knowledge-base chunks for a query.

    When ``intent`` is provided, only chunks whose source document is
    relevant to that intent are returned, so the response suggestion,
    coaching guidance and escalation analysis stay grounded in
    contextually relevant information (e.g. ``delayed_order`` returns
    delivery/order documents, never ``payment_issues.txt``).

    Returns a list of:
        {
            "text": str,
            "score": float (cosine similarity 0..1),
            "metadata": {"source": str, "page": int | None},
        }

    An empty list is returned when retrieval is unavailable or fails,
    so callers never need to handle knowledge-agent outages.
    """
    if not query or not str(query).strip():
        return []

    search_fn = _get_search_fn()
    if search_fn is None:
        return []

    allowed_sources = _allowed_sources_for_intent(intent) \
        if intent and intent != "general_inquiry" else []

    # When intent-aware filtering is active we request more candidates
    # from the retriever so that relevant documents which rank lower
    # (e.g. Refund Policy.pdf for a delayed_order query) still have a
    # chance to appear before the intent filter is applied.
    retrieval_top_k = top_k
    if allowed_sources:
        retrieval_top_k = max(top_k, 20)

    try:
        raw_results = search_fn(str(query).strip(), top_k=retrieval_top_k)
    except Exception:  # pragma: no cover - depends on env
        return []

    results: List[Dict] = []

    for item in raw_results or []:
        score = float(item.get("score", 0.0) or 0.0)

        if score < min_score:
            continue

        metadata = item.get("metadata") or {}
        source = metadata.get("source") or "Knowledge Base"

        # Intent-aware document filter: keep only chunks from sources
        # relevant to the detected customer intent. When no intent or
        # intent is general_inquiry, all sources are allowed.
        if allowed_sources:
            if not any(
                kw.lower() in source.lower() for kw in allowed_sources
            ):
                continue

        results.append({
            "text": str(item.get("text", "")).strip(),
            "score": round(score, 4),
            "metadata": {
                "source": source,
                "page": metadata.get("page"),
                "file_type": metadata.get("file_type"),
            },
        })

    return results[:top_k]
