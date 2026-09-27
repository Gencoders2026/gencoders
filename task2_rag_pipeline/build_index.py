import os

from document_loader import load_document
from text_cleaner import clean_text
from chunker import create_chunks
from embeddings import generate_embeddings
from vector_store import create_vector_store


# Knowledge base folder
KNOWLEDGE_BASE_DIR = os.path.join(
    "data",
    "knowledge_base"
)


def get_all_files(folder):
    """
    Recursively find all PDF and TXT files
    inside the knowledge base folder.
    """

    files = []

    for root, _, filenames in os.walk(folder):

        for filename in filenames:

            if filename.lower().endswith((".pdf", ".txt")):

                file_path = os.path.join(
                    root,
                    filename
                )

                files.append(file_path)

    return files


def main():

    print("=" * 60)
    print("Building Knowledge Base")
    print("=" * 60)

    # Check knowledge base folder
    if not os.path.exists(KNOWLEDGE_BASE_DIR):

        print(
            f"ERROR: Knowledge base folder not found: "
            f"{KNOWLEDGE_BASE_DIR}"
        )

        return

    # Get PDF/TXT files
    files = get_all_files(
        KNOWLEDGE_BASE_DIR
    )

    if not files:

        print(
            "ERROR: No PDF or TXT documents found."
        )

        return

    print(
        f"\nFound {len(files)} documents.\n"
    )

    all_documents = []

    # --------------------------------------------------
    # STEP 1: Load documents
    # --------------------------------------------------

    for file_path in files:

        print(
            f"Loading: {file_path}"
        )

        documents = load_document(
            file_path
        )

        # Clean text
        for document in documents:

            document["text"] = clean_text(
                document["text"]
            )

        all_documents.extend(
            documents
        )

    print(
        f"\nLoaded {len(all_documents)} document sections."
    )

    # --------------------------------------------------
    # STEP 2: Create chunks
    # --------------------------------------------------

    print(
        "\nCreating chunks..."
    )

    chunks = create_chunks(
        all_documents
    )

    print(
        f"Created {len(chunks)} chunks."
    )

    # --------------------------------------------------
    # STEP 3: Generate embeddings
    # --------------------------------------------------

    print(
        "\nGenerating embeddings..."
    )

    texts = [
        chunk["text"]
        for chunk in chunks
    ]

    embeddings = generate_embeddings(
        texts
    )

    print(
        "Embeddings generated successfully."
    )

    # --------------------------------------------------
    # STEP 4: Create FAISS vector store
    # --------------------------------------------------

    print(
        "\nCreating FAISS vector database..."
    )

    create_vector_store(
        embeddings,
        chunks
    )

    print("\n" + "=" * 60)
    print("Knowledge Base Created Successfully!")
    print("=" * 60)

    print(
        f"Documents processed : {len(files)}"
    )

    print(
        f"Chunks created      : {len(chunks)}"
    )

    print(
        "\nVector database saved inside:"
    )

    print(
        "vector_db/"
    )


if __name__ == "__main__":
    main()