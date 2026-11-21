"""Clean the loaded text before chunking."""

import re

from src.load import load_documents


WRAPPED_LINE_LENGTH = 70
POSITION_TOLERANCE = 2


def fix_bullets(text):
    """Swap bullet symbols at line starts for a dash."""
    pattern = r"^[ \t]*[^\w\s\x21-\x7e][ \t]+"
    return re.sub(pattern, "- ", text, flags=re.MULTILINE)


def find_segments(line):
    """Split a line into pieces, with start positions."""
    segments = []
    for match in re.finditer(r"\S+(?: \S+)*", line):
        segments.append((match.start(), match.group()))
    return segments


def find_column(start, column_starts):
    """Find which column a piece starts in."""
    column = 0
    for index in range(len(column_starts)):
        if start + POSITION_TOLERANCE >= column_starts[index]:
            column = index
    return column


def fits_column(start, text, column, column_starts):
    """Check that a piece stays inside its column."""
    if column == len(column_starts) - 1:
        return True
    end = start + len(text)
    next_start = column_starts[column + 1]
    return end <= next_start + POSITION_TOLERANCE


def is_continuation(segments, column_starts):
    """Check if a line holds only wrapped cells."""
    if len(column_starts) == 0:
        return False
    for start, text in segments:
        column = find_column(start, column_starts)
        fits = fits_column(start, text, column, column_starts)
        if not fits:
            return False
    first_column = find_column(segments[0][0], column_starts)
    if first_column == 0 and len(segments) >= 2:
        return False
    return True


def add_to_row(row, segments, column_starts):
    """Add wrapped pieces to the right cells."""
    for start, text in segments:
        column = find_column(start, column_starts)
        while len(row) <= column:
            row.append("")
        if row[column] == "":
            row[column] = text
        else:
            row[column] = row[column] + " " + text


def place_cells(segments, column_spans):
    """Put each piece under the column it is closest to."""
    row = [""] * len(column_spans)
    for start, text in segments:
        center = start + len(text) / 2
        best_column = 0
        best_gap = None
        for index in range(len(column_spans)):
            span_start, span_end = column_spans[index]
            column_center = (span_start + span_end) / 2
            gap = abs(center - column_center)
            if best_gap is None or gap < best_gap:
                best_column = index
                best_gap = gap
        if row[best_column] == "":
            row[best_column] = text
        else:
            row[best_column] = row[best_column] + " " + text
    return row


def rebuild_tables(text):
    """Rebuild table rows, with wrapped cells put back."""
    lines = text.split("\n")
    output_lines = []
    column_starts = []
    column_spans = []
    row = []
    can_continue = False

    for line in lines:
        segments = find_segments(line)

        if len(segments) == 0:
            if len(row) > 0:
                output_lines.append(" | ".join(row))
                row = []
            output_lines.append("")
            can_continue = False
            continue

        continues = can_continue and is_continuation(
            segments, column_starts
        )
        if continues:
            add_to_row(row, segments, column_starts)
            continue

        if len(row) > 0:
            output_lines.append(" | ".join(row))
            row = []

        if len(segments) >= 2:
            if len(column_starts) == 0:
                for start, cell in segments:
                    column_starts.append(start)
                    end = start + len(cell)
                    column_spans.append((start, end))
            if len(segments) < len(column_spans):
                row = place_cells(segments, column_spans)
            else:
                for start, cell in segments:
                    row.append(cell)
            can_continue = True
        else:
            output_lines.append(line)
            column_starts = []
            column_spans = []
            can_continue = False

    if len(row) > 0:
        output_lines.append(" | ".join(row))

    return "\n".join(output_lines)


def strip_lines(text):
    """Remove spaces at both ends of each line."""
    lines = text.split("\n")
    stripped_lines = []
    for line in lines:
        stripped_lines.append(line.strip())
    return "\n".join(stripped_lines)


def is_table_row(line):
    """Check if a line is a table row."""
    return " | " in line


def should_join(previous, line):
    """Decide if a line continues the one before."""
    if previous == "" or line == "":
        return False
    if is_table_row(previous) or is_table_row(line):
        return False
    if line.startswith("- "):
        return False
    if previous.endswith((".", "!", "?", ":", ";")):
        return False
    if line[0].islower():
        return True
    return len(previous) >= WRAPPED_LINE_LENGTH


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
            if is_table_row(before) and is_table_row(after):
                continue
        kept_lines.append(line)
    return "\n".join(kept_lines)


def clean_pdf_text(text):
    """Run every cleaning step a PDF page needs."""
    text = text.replace("\r\n", "\n")
    text = fix_bullets(text)
    text = rebuild_tables(text)
    text = strip_lines(text)
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