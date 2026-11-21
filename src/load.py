"""Load the Tephra documents into one shape."""

from pathlib import Path

from pypdf import PdfReader


DOCS_FOLDER = Path("data/docs")
SUPPORTED_TYPES = [".pdf", ".md", ".txt"]


def make_title(file_path):
    """Turn a file name into a readable title."""
    name = file_path.stem
    name = name.replace("-", " ")
    return name.title()


def make_metadata(file_path):
    """Build the labels every document gets."""
    metadata = {
        "source": file_path.name,
        "folder": file_path.parent.name,
        "file_type": file_path.suffix.lstrip("."),
        "title": make_title(file_path),
    }
    return metadata


def load_text_file(file_path):
    """Load a markdown or .txt file as one document."""
    text = file_path.read_text(encoding="utf-8")

    if text.strip() == "":
        raise ValueError("File is empty")

    document = {
        "text": text,
        "metadata": make_metadata(file_path),
    }
    return [document]


def load_pdf_file(file_path):
    """Load a PDF as one document per page."""
    reader = PdfReader(file_path)
    documents = []

    for index in range(len(reader.pages)):
        page = reader.pages[index]
        page_number = index + 1
        text = page.extract_text()

        if text is None or text.strip() == "":
            continue

        metadata = make_metadata(file_path)
        metadata["page"] = page_number

        document = {
            "text": text,
            "metadata": metadata,
        }
        documents.append(document)

    if len(documents) == 0:
        raise ValueError("No readable text in PDF")

    return documents


def load_documents(docs_folder=DOCS_FOLDER):
    """Load every supported file in the folder."""
    if not docs_folder.exists():
        message = f"Folder not found: {docs_folder}"
        raise FileNotFoundError(message)

    documents = []
    failed_files = []
    file_paths = sorted(docs_folder.rglob("*"))

    for file_path in file_paths:
        if not file_path.is_file():
            continue
        if file_path.suffix not in SUPPORTED_TYPES:
            continue

        try:
            if file_path.suffix == ".pdf":
                new_documents = load_pdf_file(file_path)
            else:
                new_documents = load_text_file(file_path)
            documents.extend(new_documents)
        except Exception as error:
            failed_files.append((file_path.name, str(error)))

    return documents, failed_files


def print_summary(documents, failed_files):
    """Print what loaded and what failed."""
    loaded_sources = []
    for document in documents:
        source = document["metadata"]["source"]
        if source not in loaded_sources:
            loaded_sources.append(source)

    print(f"Files loaded: {len(loaded_sources)}")
    print(f"Documents created: {len(documents)}")
    print(f"Files failed: {len(failed_files)}")

    for file_name, error in failed_files:
        print(f"  {file_name}: {error}")


if __name__ == "__main__":
    documents, failed_files = load_documents()
    print_summary(documents, failed_files)

    if len(documents) > 0:
        print()
        print("First document's metadata:")
        print(documents[0]["metadata"])
        print()
        print("First 300 characters:")
        print(documents[0]["text"][:300])