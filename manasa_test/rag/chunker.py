def create_chunks(
    documents,
    chunk_size=500,
    chunk_overlap=100
):
    """
    Split documents into overlapping chunks while
    preserving metadata.
    """

    chunks = []

    for document in documents:

        text = document["text"]
        metadata = document["metadata"]

        start = 0

        while start < len(text):

            end = start + chunk_size

            chunk_text = text[start:end].strip()

            if chunk_text:
                chunks.append({
                    "text": chunk_text,
                    "metadata": metadata.copy()
                })

            start += chunk_size - chunk_overlap

    return chunks