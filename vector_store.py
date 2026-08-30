import os
import pickle
import faiss
import numpy as np


VECTOR_DB_PATH = "vector_db"
INDEX_PATH = os.path.join(
    VECTOR_DB_PATH,
    "index.faiss"
)

METADATA_PATH = os.path.join(
    VECTOR_DB_PATH,
    "metadata.pkl"
)


def create_vector_store(embeddings, chunks):

    os.makedirs(VECTOR_DB_PATH, exist_ok=True)

    embeddings = np.asarray(
        embeddings,
        dtype="float32"
    )

    dimension = embeddings.shape[1]

    index = faiss.IndexFlatIP(dimension)

    index.add(embeddings)

    faiss.write_index(
        index,
        INDEX_PATH
    )

    with open(METADATA_PATH, "wb") as file:
        pickle.dump(chunks, file)

    return index


def load_vector_store():

    if not os.path.exists(INDEX_PATH):
        raise FileNotFoundError(
            "FAISS index does not exist."
        )

    index = faiss.read_index(
        INDEX_PATH
    )

    with open(METADATA_PATH, "rb") as file:
        chunks = pickle.load(file)

    return index, chunks