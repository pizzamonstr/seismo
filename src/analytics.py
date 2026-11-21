"""Turn the usage log into tables for the Analytics tab."""

import re

import pandas as pd

from src.usage_log import LOG_FILE, SAMPLE_FILE, read_events

STATUS_NAMES = {
    "ok": "Answered",
    "no_match": "Not about Tephra",
    "not_found": "Related, but no answer",
    "flagged": "Declined (moderation)",
    "too_long": "Too long",
    "empty": "Empty",
    "error": "Error",
}
UPPER_WORDS = ["qbr", "ga4", "capi", "pmax", "v2.2"]
STEP_COLUMNS = {
    "rewrite_seconds": "Understanding the question",
    "search_seconds": "Searching the documents",
    "rerank_seconds": "Weighing the evidence",
    "write_seconds": "Writing the answer",
}


def readable_name(source):
    """Turn a file name into a short, readable document name."""
    stem = source.rsplit(".", 1)[0]
    report = re.match(r"tarn-digital-tephra-report-(\d{4})-\d{2}-(\w+)",
                      stem)
    if report:
        return f"Agency report, {report.group(2).title()} " \
               f"{report.group(1)}"
    words = []
    for word in stem.split("-"):
        if word in UPPER_WORDS or re.fullmatch(r"q\d", word):
            word = word.upper()
        words.append(word)
    name = " ".join(words)
    return name[0].upper() + name[1:]


def load_questions(include_sample):
    """Read logged questions as a table, with or without samples."""
    events = read_events(LOG_FILE)
    if include_sample:
        events = events + read_events(SAMPLE_FILE)

    rows = []
    for event in events:
        if event.get("type") == "question":
            rows.append(event)
    questions = pd.DataFrame(rows)
    if len(questions) == 0:
        return questions

    questions["outcome"] = questions["status"].map(STATUS_NAMES)
    questions["outcome"] = questions["outcome"].fillna("Other")
    return questions


def load_found_via():
    """Count where real visitors said they found Seismo."""
    rows = []
    for event in read_events(LOG_FILE):
        if event.get("type") == "found_via":
            rows.append(event)
    found_via = pd.DataFrame(rows)
    if len(found_via) == 0:
        return found_via
    counts = found_via["choice"].value_counts().reset_index()
    counts.columns = ["Where", "Visitors"]
    return counts


def count_real_visits(questions):
    """Count real visits, leaving out the sample questions."""
    real = questions[questions["visit_id"] != "sample"]
    return real["visit_id"].nunique()


def summarize(questions):
    """Work out the headline numbers for the top of the tab."""
    answered = questions[questions["status"] == "ok"]
    summary = {
        "questions": len(questions),
        "visits": count_real_visits(questions),
        "answered_share": len(answered) / len(questions),
        "average_seconds": answered["total_seconds"].mean(),
    }
    if len(answered) == 0:
        summary["average_seconds"] = 0
    return summary


def count_outcomes(questions):
    """Count how each question was handled."""
    counts = questions["outcome"].value_counts().reset_index()
    counts.columns = ["Outcome", "Questions"]
    return counts


def count_cited_sources(questions, top=8):
    """Count the documents cited most often in answers."""
    cited = questions[["sources_cited"]].explode("sources_cited")
    cited = cited.dropna()
    names = cited["sources_cited"].map(readable_name)
    counts = names.value_counts().head(top)
    counts = counts.reset_index()
    counts.columns = ["Document", "Times cited"]
    return counts


def average_step_times(questions):
    """Average how long each step took for answered questions."""
    answered = questions[questions["status"] == "ok"]
    rows = []
    for column in STEP_COLUMNS:
        if column in answered.columns:
            seconds = answered[column].mean()
        else:
            seconds = 0
        rows.append({"Step": STEP_COLUMNS[column], "Seconds": seconds})
    return pd.DataFrame(rows)