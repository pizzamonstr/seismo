"""Clean the loaded text before chunking."""

import re

from src.load import load_documents


def strip_lines(text):
    """Remove spaces at both ends of each line."""
    lines = text.split("\n")
    stripped_lines = []
    for line in lines:
        stripped_lines.append(line.strip())
    return "\n".join(stripped_lines)


def fix_bullets(text):
    """Swap font bullet symbols for a dash."""
    return re.sub(r"[\ue000-\uf8ff]\s*", "- ", text)


def mark_table_columns(text):
    """Swap runs of 2+ spaces for ' | '."""
    return re.sub(r" {2,}", " | ", text)


def should_join(previous, line):
    """Decide if a line continues the one before."""
    if previous == "" or line == "":
        return False
    if " | " in previous or " | " in line:
        return False
    if previous.endswith((".", "!", "?", ":", ";")):
        return False
    return line[0].islower()


def join_broken_lines(text):
    """Rejoin sentences split across lines."""
    lines = text.split("\n")
    joined_lines = []
    for line in lines:
        if len(joined_lines) > 0:
            previous = joined_lines[-1]
            if should_join(previous, line):
                joined_lines[-1] = previous + " " + line
                continue
        joined_lines.append(line)
    return "\n".join(joined_lines)


def remove_extra_blank_lines(text):
    """Shrink 2+ blank lines in a row to 1."""
    return re.sub(r"\n{3,}", "\n\n", text)


def remove_blank_lines_in_tables(text):
    """Drop blank lines between two table rows."""
    lines = text.split("\n")
    kept_lines = []
    for index in range(len(lines)):
        line = lines[index]
        is_middle = index > 0 and index < len(lines) - 1
        if line == "" and is_middle:
            before = lines[index - 1]
            after = lines[index + 1]
            if " | " in before and " | " in after:
                continue
        kept_lines.append(line)
    return "\n".join(kept_lines)
            

def clean_pdf_text(text):
    """Run every cleaning step a PDF page needs."""
    text = text.replace("\r\n", "\n")
    text = strip_lines(text)
    text = fix_bullets(text)
    text = mark_table_columns(text)
    text = join_broken_lines(text)
    text = remove_extra_blank_lines(text)
    text = remove_blank_lines_in_tables(text)
    return text.strip()


def clean_plain_text(text):
    """Light cleaning for markdown and .txt files."""
    text = text.replace("\r\n", "\n")
    lines = text.split("\n")
    trimmed_lines = []
    for line in lines:
        trimmed_lines.append(line.rstrip())
    text = "\n".join(trimmed_lines)
    text = remove_extra_blank_lines(text)
    return text.strip()


def clean_documents(documents):
    """Clean every document and keep its metadata."""
    cleaned_documents = []
    for document in documents:
        file_type = document["metadata"]["file_type"]

        if file_type == "pdf":
            text = clean_pdf_text(document["text"])
        else:
            text = clean_plain_text(document["text"])

        if text == "":
            continue

        cleaned_document = {
            "text": text,
            "metadata": document["metadata"],
        }
        cleaned_documents.append(cleaned_document)

    return cleaned_documents


if __name__ == "__main__":
    documents, failed_files = load_documents()
    cleaned = clean_documents(documents)

    print(f"Documents before cleaning: {len(documents)}")
    print(f"Documents after cleaning: {len(cleaned)}")
    print()
    print(cleaned[0]["text"])