import re


def clean_text(text):
    """
    Clean extracted document text.
    """

    # Replace multiple spaces
    text = re.sub(r"\s+", " ", text)

    # Remove unnecessary whitespace
    text = text.strip()

    return text