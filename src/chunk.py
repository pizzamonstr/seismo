"""Cut cleaned documents into chunks with metadata."""

import re
import sys
from datetime import datetime
from pathlib import Path

from src.clean import clean_documents, is_table_row
from src.load import load_documents


MAX_CHUNK_CHARS = 1500
HEADING_MAX_LENGTH = 70
OVERVIEW_MAX_CHARS = 300
MONTHS = (
    "January|February|March|April|May|June|July"
    "|August|September|October|November|December"
)


def parse_written_date(text):
    """Turn a date like 'April 10, 2025' into 2025-04-10."""
    pattern = "(" + MONTHS + r") \d{1,2}, \d{4}"
    match = re.search(pattern, text)
    if match is None:
        return ""
    found = datetime.strptime(match.group(), "%B %d, %Y")
    return found.strftime("%Y-%m-%d")


def date_from_filename(source):
    """Find a YYYY-MM-DD or YYYY-MM date in a file name."""
    full_date = re.search(r"\d{4}-\d{2}-\d{2}", source)
    if full_date is not None:
        return full_date.group()
    month = re.search(r"\d{4}-(0[1-9]|1[0-2])\b", source)
    if month is not None:
        return month.group()
    return ""


def find_document_date(text, source):
    """Find a date from a 'Date:' line, or the file name."""
    lines = text.split("\n")
    for line in lines[:10]:
        if "Date:" in line:
            date = parse_written_date(line)
            if date != "":
                return date
    return date_from_filename(source)


def find_heading_date(heading):
    """Find a date at the start of a heading, if any."""
    iso_date = re.match(r"\d{4}-\d{2}-\d{2}", heading)
    if iso_date is not None:
        return iso_date.group()
    written_date = parse_written_date(heading)
    if written_date != "":
        return written_date
    pattern = "(" + MONTHS + r") (\d{4})"
    month_year = re.search(pattern, heading)
    if month_year is not None:
        found = datetime.strptime(month_year.group(), "%B %Y")
        return found.strftime("%Y-%m")
    return ""


def make_chunk_text(title, section, body):
    """Put the title and section above the chunk's text."""
    return f"{title}\nSection: {section}\n\n{body}"


def find_last_table_header(body):
    """Find the header row of the last table in a body."""
    header = ""
    previous = ""
    for line in body.split("\n"):
        if is_table_row(line) and not is_table_row(previous):
            header = line
        previous = line
    return header


def split_cells(line):
    """Split a table row into its cells."""
    cells = []
    for cell in line.split("|"):
        cells.append(cell.strip())
    return cells


def row_to_sentence(headers, cells):
    """Turn a table row into a plain-language line."""
    parts = []
    for index in range(1, len(cells)):
        if cells[index] == "":
            continue
        label = ""
        if index < len(headers):
            label = headers[index]
        parts.append((label + " " + cells[index]).strip())
    if len(parts) == 0:
        return cells[0]
    return cells[0] + ": " + "; ".join(parts) + "."


def tables_to_sentences(body):
    """Rewrite table rows as sentences, and list the rows."""
    output_lines = []
    row_sentences = []
    headers = []
    previous = ""
    for line in body.split("\n"):
        if is_table_row(line):
            cells = split_cells(line)
            if not is_table_row(previous):
                headers = cells
            else:
                sentence = row_to_sentence(headers, cells)
                output_lines.append(sentence)
                row_sentences.append(sentence)
        else:
            output_lines.append(line)
        previous = line
    return "\n".join(output_lines), row_sentences


def split_long_text(body):
    """Split text over the size limit into pieces."""
    if len(body) <= MAX_CHUNK_CHARS:
        return [body]

    pieces = []
    current_lines = []
    current_size = 0
    table_header = ""
    previous = ""

    for line in body.split("\n"):
        if is_table_row(line) and not is_table_row(previous):
            table_header = line

        too_big = current_size + len(line) > MAX_CHUNK_CHARS
        if too_big and len(current_lines) > 0:
            pieces.append("\n".join(current_lines))
            current_lines = []
            current_size = 0
            if is_table_row(line) and line != table_header:
                current_lines.append(table_header)
            elif previous != "":
                current_lines.append(previous)
            for kept in current_lines:
                current_size = current_size + len(kept) + 1

        current_lines.append(line)
        current_size = current_size + len(line) + 1
        previous = line

    pieces.append("\n".join(current_lines))
    return pieces


def add_chunks(chunks, document, title, section, body, date,
               counters, chunk_type="section"):
    """Turn one section into chunks and add them."""
    body = body.strip()
    if body == "":
        return

    source = document["metadata"]["source"]
    stem = Path(source).stem

    for piece in split_long_text(body):
        counters[source] = counters.get(source, 0) + 1
        number = counters[source]

        metadata = dict(document["metadata"])
        metadata["title"] = title.split("\n")[0]
        metadata["section"] = section
        metadata["date"] = date
        metadata["month"] = date[:7]
        metadata["chunk_type"] = chunk_type
        metadata["chunk_id"] = f"{stem}-{number:03d}"

        chunk = {
            "text": make_chunk_text(title, section, piece),
            "metadata": metadata,
        }
        chunks.append(chunk)


def split_markdown(text):
    """Split markdown into its title and ## sections."""
    title = ""
    sections = []
    heading = "Overview"
    parent_heading = "Overview"
    section_lines = []

    for line in text.split("\n"):
        if line.startswith("# ") and title == "":
            title = line[2:].strip()
            continue
        if line.startswith("## "):
            body = "\n".join(section_lines)
            sections.append({"heading": heading, "body": body})
            parent_heading = line[3:].strip()
            heading = parent_heading
            section_lines = []
            continue
        if line.startswith("### "):
            body = "\n".join(section_lines)
            sections.append({"heading": heading, "body": body})
            sub_heading = line[4:].strip()
            heading = parent_heading + " > " + sub_heading
            section_lines = []
            continue
        if line.strip() == "---":
            continue
        section_lines.append(line)

    body = "\n".join(section_lines)
    sections.append({"heading": heading, "body": body})
    return title, sections


def chunk_markdown(document, chunks, counters):
    """Chunk a markdown file, one chunk per section."""
    text = document["text"]
    metadata = document["metadata"]
    title, sections = split_markdown(text)
    if title == "":
        title = metadata["title"]
    document_date = find_document_date(text, metadata["source"])

    first = sections[0]
    overview = first["body"].replace("*", "").strip()
    short = len(overview) <= OVERVIEW_MAX_CHARS
    if first["heading"] == "Overview" and short:
        if overview != "":
            title = title + "\n" + overview
        sections = sections[1:]

    for section in sections:
        heading = section["heading"]
        date = document_date
        heading_date = find_heading_date(heading)
        if heading_date != "":
            date = heading_date
        add_chunks(chunks, document, title, heading,
                   section["body"], date, counters)


def split_slack(text):
    """Split a Slack export into its header and days."""
    header_lines = []
    days = []

    for line in text.split("\n"):
        match = re.match(r"\[(\d{4}-\d{2}-\d{2})", line)
        if match is None:
            if line == "":
                continue
            if len(days) == 0:
                header_lines.append(line)
            else:
                days[-1]["lines"].append(line)
            continue

        date = match.group(1)
        if len(days) == 0 or days[-1]["date"] != date:
            days.append({"date": date, "lines": []})
        days[-1]["lines"].append(line)

    return header_lines, days


def chunk_slack(document, chunks, counters):
    """Chunk a Slack export, one chunk per day."""
    header_lines, days = split_slack(document["text"])
    title = document["metadata"]["title"]
    if len(header_lines) > 0:
        title = header_lines[0]

    for day in days:
        body = "\n".join(day["lines"])
        add_chunks(chunks, document, title, day["date"],
                   body, day["date"], counters)


def chunk_plain_text(document, chunks, counters):
    """Chunk a .txt file, such as an email, as a whole."""
    text = document["text"]
    metadata = document["metadata"]
    section = "Full text"
    for line in text.split("\n")[:10]:
        if line.startswith("Subject:"):
            section = line[len("Subject:"):].strip()
    date = find_document_date(text, metadata["source"])
    add_chunks(chunks, document, metadata["title"], section,
               text, date, counters)


def is_pdf_heading(lines, index):
    """Check if a PDF line is a section heading."""
    line = lines[index]
    if line == "" or len(line) > HEADING_MAX_LENGTH:
        return False
    if is_table_row(line) or line.startswith("- "):
        return False
    if line.endswith((".", ",", ";")):
        return False
    is_first = index == 0
    is_last = index == len(lines) - 1
    blank_before = is_first or lines[index - 1] == ""
    blank_after = is_last or lines[index + 1] == ""
    return blank_before and blank_after


def split_pdf_page(text):
    """Split a PDF page into sections by heading."""
    lines = text.split("\n")
    sections = []
    heading = None
    section_lines = []

    for index in range(len(lines)):
        if is_pdf_heading(lines, index):
            body = "\n".join(section_lines)
            sections.append({"heading": heading, "body": body})
            heading = lines[index]
            section_lines = []
        else:
            section_lines.append(lines[index])

    body = "\n".join(section_lines)
    sections.append({"heading": heading, "body": body})
    return sections


def find_pdf_title(text, fallback):
    """Build a title from the first lines of a PDF page."""
    lines = []
    for line in text.split("\n"):
        if line.strip() != "":
            lines.append(line.strip())
    if len(lines) >= 2 and lines[0].isupper():
        return lines[0].title() + ": " + lines[1]
    if len(lines) >= 1:
        return lines[0]
    return fallback


def chunk_pdf_page(document, chunks, counters, carry):
    """Chunk one PDF page, carrying headings across pages."""
    text = document["text"]
    metadata = document["metadata"]
    source = metadata["source"]

    if carry["source"] != source:
        carry["source"] = source
        carry["heading"] = "Overview"
        carry["table_header"] = ""
        carry["title"] = find_pdf_title(text, metadata["title"])

    date = find_document_date(text, source)

    for section in split_pdf_page(text):
        heading = section["heading"]
        body = section["body"].strip()

        if heading is None:
            heading = carry["heading"]
            first_line = body.split("\n")[0]
            header = carry["table_header"]
            continues_table = is_table_row(first_line)
            if continues_table and header != first_line:
                if header != "":
                    body = header + "\n" + body
        else:
            carry["heading"] = heading

        last_header = find_last_table_header(body)
        if last_header != "":
            carry["table_header"] = last_header

        body, row_sentences = tables_to_sentences(body)
        add_chunks(chunks, document, carry["title"],
                   heading, body, date, counters)
        for sentence in row_sentences:
            add_chunks(chunks, document, carry["title"],
                       heading, sentence, date, counters,
                       "table row")


def chunk_documents(documents):
    """Chunk every document with the rule for its format."""
    chunks = []
    counters = {}
    carry = {"source": ""}

    for document in documents:
        metadata = document["metadata"]
        if metadata["file_type"] == "pdf":
            chunk_pdf_page(document, chunks, counters, carry)
        elif metadata["folder"] == "slack":
            chunk_slack(document, chunks, counters)
        elif metadata["file_type"] == "md":
            chunk_markdown(document, chunks, counters)
        else:
            chunk_plain_text(document, chunks, counters)

    return chunks


def print_chunk_summary(chunks):
    """Print chunk counts, sizes and an ID check."""
    sizes = []
    folder_counts = {}
    chunk_ids = []

    for chunk in chunks:
        sizes.append(len(chunk["text"]))
        folder = chunk["metadata"]["folder"]
        folder_counts[folder] = folder_counts.get(folder, 0) + 1
        chunk_ids.append(chunk["metadata"]["chunk_id"])

    print(f"Chunks: {len(chunks)}")
    print(f"Smallest: {min(sizes)} characters")
    print(f"Largest: {max(sizes)} characters")
    print(f"Average: {round(sum(sizes) / len(sizes))} characters")

    if len(set(chunk_ids)) == len(chunk_ids):
        print("Chunk IDs: all unique")
    else:
        print("Chunk IDs: DUPLICATES FOUND")

    print()
    print("Chunks per folder:")
    for folder in sorted(folder_counts):
        print(f"  {folder}: {folder_counts[folder]}")


def print_smallest_chunks(chunks, count=8):
    """Print the smallest chunks, to check for scraps."""
    sizes = []
    for chunk in chunks:
        sizes.append(len(chunk["text"]))
    sizes.sort()
    cutoff = sizes[count - 1]

    print()
    print(f"Smallest {count} chunks:")
    for chunk in chunks:
        if len(chunk["text"]) <= cutoff:
            print(f"--- {chunk['metadata']['chunk_id']}")
            print(chunk["text"])
            print()
                          

if __name__ == "__main__":
    documents, failed_files = load_documents()
    cleaned = clean_documents(documents)
    chunks = chunk_documents(cleaned)
    print_chunk_summary(chunks)
    print_smallest_chunks(chunks)

    if len(sys.argv) > 1:
        source = sys.argv[1]
        for chunk in chunks:
            if chunk["metadata"]["source"] == source:
                print()
                print(f"===== {chunk['metadata']['chunk_id']} =====")
                print(chunk["metadata"])
                print()
                print(chunk["text"])