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


def search_knowledge(
    query: str,
    top_k: int = 3,
    min_score: float = 0.0,
) -> List[Dict]:
    """
    Retrieve the most relevant knowledge-base chunks for a query.

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

    try:
        raw_results = search_fn(str(query).strip(), top_k=top_k)
    except Exception:  # pragma: no cover - depends on env
        return []

    results: List[Dict] = []

    for item in raw_results or []:
        score = float(item.get("score", 0.0) or 0.0)

        if score < min_score:
            continue

        metadata = item.get("metadata") or {}

        results.append({
            "text": str(item.get("text", "")).strip(),
            "score": round(score, 4),
            "metadata": {
                "source": metadata.get("source") or "Knowledge Base",
                "page": metadata.get("page"),
                "file_type": metadata.get("file_type"),
            },
        })

    return results
