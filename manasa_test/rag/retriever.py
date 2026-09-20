from embeddings import model
from vector_store import load_vector_store


def semantic_search(
    query,
    top_k=3
):
    """
    Retrieve the most relevant chunks
    using semantic similarity.
    """

    index, chunks = load_vector_store()

    query_embedding = model.encode(
        [query],
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    scores, indices = index.search(
        query_embedding.astype("float32"),
        top_k
    )

    results = []

    for score, index_id in zip(
        scores[0],
        indices[0]
    ):

        if index_id == -1:
            continue

        result = chunks[index_id].copy()

        result["score"] = float(score)

        results.append(result)

    return results