"""Save each question and visit choice to a log file."""

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

LOG_FOLDER = Path(os.environ.get("SEISMO_LOG_FOLDER", "logs"))
LOG_FILE = LOG_FOLDER / "usage.jsonl"


def new_visit_id():
    """Make a random, anonymous ID for one visit."""
    return uuid.uuid4().hex[:12]


def write_event(event):
    """Add one event to the end of the log, one JSON line each."""
    LOG_FOLDER.mkdir(parents=True, exist_ok=True)
    event["time"] = datetime.now(timezone.utc).isoformat(
        timespec="seconds"
    )
    with open(LOG_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(event) + "\n")


def log_question(visit_id, question, details, citations):
    """Save what was asked and how Seismo handled it."""
    cited_sources = []
    for citation in citations:
        if citation["source"] not in cited_sources:
            cited_sources.append(citation["source"])

    event = {
        "type": "question",
        "visit_id": visit_id,
        "question": question,
        "search_text": details.get("search_text", ""),
        "status": details.get("status", ""),
        "top_similarity": round(details.get("top_similarity", 0), 3),
        "passages_read": details.get("rerank_pool", 0),
        "sources_cited": cited_sources,
        "rewrite_seconds": round(details.get("rewrite_seconds", 0), 2),
        "search_seconds": round(
            details.get("embed_seconds", 0)
            + details.get("search_seconds", 0), 2
        ),
        "rerank_seconds": round(details.get("rerank_seconds", 0), 2),
        "write_seconds": round(details.get("write_seconds", 0), 2),
        "total_seconds": round(details.get("total_seconds", 0), 2),
    }
    write_event(event)


def log_found_via(visit_id, choice):
    """Save where a visitor said they found Seismo."""
    event = {
        "type": "found_via",
        "visit_id": visit_id,
        "choice": choice,
    }
    write_event(event)


def read_events():
    """Read every event in the log, skipping any broken lines."""
    if not LOG_FILE.exists():
        return []
    events = []
    with open(LOG_FILE, encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if line == "":
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events