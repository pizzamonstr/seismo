"""Print one file's cleaned pages, for checking."""

import sys

from src.clean import clean_documents
from src.load import load_documents


def peek(source):
    """Print every cleaned page of one file."""
    documents, failed_files = load_documents()
    cleaned = clean_documents(documents)

    for document in cleaned:
        metadata = document["metadata"]
        if metadata["source"] == source:
            page = metadata.get("page", "none")
            print(f"===== {source}, page {page} =====")
            print(document["text"])
            print()


if __name__ == "__main__":
    peek(sys.argv[1])