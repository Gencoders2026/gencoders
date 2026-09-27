from pathlib import Path
from pypdf import PdfReader


def load_pdf(file_path):
    """
    Extract text from a PDF while preserving page-level information.
    """

    reader = PdfReader(file_path)
    documents = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""

        documents.append({
            "text": text,
            "metadata": {
                "source": Path(file_path).name,
                "page": page_number,
                "file_type": "pdf"
            }
        })

    return documents


def load_txt(file_path):
    """
    Load a text document.
    """

    text = Path(file_path).read_text(
        encoding="utf-8",
        errors="ignore"
    )

    return [{
        "text": text,
        "metadata": {
            "source": Path(file_path).name,
            "page": None,
            "file_type": "txt"
        }
    }]


def load_document(file_path):
    """
    Load PDF or TXT document based on file extension.
    """

    extension = Path(file_path).suffix.lower()

    if extension == ".pdf":
        return load_pdf(file_path)

    elif extension == ".txt":
        return load_txt(file_path)

    else:
        raise ValueError(
            f"Unsupported file type: {extension}"
        )