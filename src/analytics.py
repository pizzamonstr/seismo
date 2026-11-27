"""Turn the usage log into tables for the Analytics tab."""

import re

import pandas as pd

from src.usage_log import LOG_FILE, SAMPLE_FILE, read_events

STATUS_NAMES = {
    "ok": "Answered",
    "no_match": "Not About Tephra",
    "not_found": "Related but Unanswered",
    "flagged": "Declined by Moderation",
    "too_long": "Too Long",
    "empty": "Empty",
    "error": "Error",
}
GAP_STATUSES = ["no_match", "not_found"]
PACIFIC = "America/Vancouver"
MONTH_NAMES = {
    "01": "January", "02": "February", "03": "March",
    "04": "April", "05": "May", "06": "June", "07": "July",
    "08": "August", "09": "September", "10": "October",
    "11": "November", "12": "December",
}
NAME_PATTERNS = [
    (r"tarn-digital-tephra-report-(?P<year>\d{4})-(?P<month>\d{2})"
     r"-\w+", "Agency report, {month} {year}"),
    (r"slack-marketing-(?P<year>\d{4})-(?P<month>\d{2})",
     "Slack #marketing, {month} {year}"),
    (r"qbr-(?P<year>\d{4})-(?P<period>q\d)-notes",
     "QBR notes, {period} {year}"),
    (r"site-tracking-changelog-(?P<year>\d{4})-(?P<period>q\d)",
     "Tracking change log, {period} {year}"),
    (r"customer-service-summary-(?P<year>\d{4})-(?P<period>q\d)",
     "Customer service summary, {period} {year}"),
    (r"klaviyo-email-performance-(?P<year>\d{4})-(?P<period>h\d)",
     "Klaviyo email performance, {period} {year}"),
    (r"conditions-watch-(?P<year>\d{4})-(?P<period>\w+)",
     "Conditions watch, {period} {year}"),
    (r"weekly-standup-(?P<year>\d{4})-(?P<month>\d{2})"
     r"-(?P<day>\d{2})", "Weekly standup, {month} {day}, {year}"),
    (r"inventory-update-(?P<year>\d{4})-(?P<month>\d{2})"
     r"-(?P<day>\d{2})", "Inventory update, {month} {day}, {year}"),
]
PROPER_WORDS = [
    "tephra", "fissile", "mackenzie", "klaviyo", "meta", "cerise",
    "black", "friday", "july",
]
UPPER_WORDS = ["qbr", "ga4", "capi", "pmax", "v2.2"]
STEP_COLUMNS = {
    "rewrite_seconds": "Rewrite",
    "search_seconds": "Search",
    "rerank_seconds": "Re-rank",
    "write_seconds": "Generate",
}


def readable_name(source):
    """Turn a file name into a short, readable document name."""
    stem = source.rsplit(".", 1)[0]
    for pattern, template in NAME_PATTERNS:
        match = re.fullmatch(pattern, stem)
        if match:
            return template.format(**fill_parts(match.groupdict()))

    stem = readable_dates(stem)
    words = []
    for word in stem.split("-"):
        if word in UPPER_WORDS or re.fullmatch(r"q\d", word):
            word = word.upper()
        elif word in PROPER_WORDS:
            word = word.title()
        words.append(word)
    name = " ".join(words)
    return name[0].upper() + name[1:]


def swap_date(match):
    """Turn 2025-10-24 into October 24, 2025."""
    month = MONTH_NAMES[match.group(2)]
    return f"{month} {int(match.group(3))}, {match.group(1)}"


def swap_two_parts(match):
    """Turn 2025-26 into 2025/26, or 2025-08 into August 2025."""
    first = match.group(1)
    second = match.group(2)
    if int(second) == int(first[2:]) + 1:
        return f"{first}/{second}"
    if second in MONTH_NAMES:
        return f"{MONTH_NAMES[second]} {first}"
    return match.group(0)


def readable_dates(stem):
    """Rewrite dates inside a file name so they read naturally."""
    stem = re.sub(r"(\d{4})-(\d{2})-(\d{2})", swap_date, stem)
    stem = re.sub(r"(\d{4})-(\d{2})(?=-|$)", swap_two_parts, stem)
    return stem


def fill_parts(parts):
    """Make matched name parts readable: months, periods, days."""
    readable = {}
    for key in parts:
        value = parts[key]
        if key == "month":
            value = MONTH_NAMES[value]
        elif key == "day":
            value = str(int(value))
        elif key == "period":
            if value[1:].isdigit():
                value = value.upper()
            else:
                value = value.title()
        readable[key] = value
    return readable


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


def add_themes(questions, themes):
    """Label each question with its theme name."""
    labelled = questions.copy()
    labelled["theme"] = labelled["question"].map(themes)
    labelled["theme"] = labelled["theme"].fillna("Unsorted")
    return labelled


def count_themes(questions):
    """Count questions per theme and how many were answered."""
    rows = []
    for theme, group in questions.groupby("theme"):
        answered = group[group["status"] == "ok"]
        rows.append({
            "Theme": theme,
            "Questions": len(group),
            "Answered": len(answered) / len(group),
        })
    return pd.DataFrame(rows)


def find_gaps(questions):
    """Keep questions Seismo looked for but could not answer."""
    return questions[questions["status"].isin(GAP_STATUSES)]


def build_question_table(questions):
    """Make a readable table of questions, newest first."""
    table = questions.copy()
    times = pd.to_datetime(table["time"], utc=True)
    table["When (Pacific)"] = times.dt.tz_convert(PACIFIC)
    table["When (Pacific)"] = table["When (Pacific)"].dt.strftime(
        "%Y-%m-%d %H:%M"
    )
    table = table.sort_values("time", ascending=False)
    columns = {
        "When (Pacific)": "When (Pacific)",
        "question": "Question",
        "theme": "Theme",
        "outcome": "Outcome",
        "total_seconds": "Seconds",
    }
    table = table[list(columns)].rename(columns=columns)
    return table