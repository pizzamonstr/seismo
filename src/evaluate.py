"""Score Seismo's retrieval on the eval questions."""

import re
import sys
from pathlib import Path

import altair as alt
import pandas as pd
from openai import OpenAI

from src.embed import EMBEDDING_MODEL, get_api_key, get_collection
from src.retrieve import THRESHOLD, retrieve


QUESTIONS_FILE = Path("eval/eval-questions.csv")
RESULTS_FOLDER = Path("eval/results")
REJECT_TYPES = ["unanswerable", "irrelevant"]
REJECT_STATUSES = ["no_match", "not_found"]


def read_expected_sources(cell):
    """Find every file name in a source_documents cell."""
    if pd.isna(cell):
        return []
    pattern = r"[\w\-.]+\.(?:md|pdf|txt)"
    sources = []
    for name in re.findall(pattern, str(cell)):
        if name not in sources:
            sources.append(name)
    return sources


def is_required(value):
    """A question is required if required_set has any value."""
    if pd.isna(value):
        return False
    return str(value).strip() != ""


def score_question(row, openai_client, collection, model):
    """Run one question and score what retrieval found."""
    expected = read_expected_sources(row["source_documents"])
    should_reject = row["question_type"] in REJECT_TYPES

    record = {
        "id": row["id"],
        "question_type": row["question_type"],
        "required_set": is_required(row["required_set"]),
        "question": row["question"],
        "expected_sources": "; ".join(expected),
        "should_reject": should_reject,
    }

    try:
        results, details = retrieve(
            row["question"], openai_client, collection, model=model
        )
    except Exception as error:
        record["status"] = "error"
        record["error"] = str(error)
        record["correct"] = False
        return record

    found = []
    for result in results:
        source = result["metadata"]["source"]
        if source not in found:
            found.append(source)

    matched = 0
    in_pool = False
    for source in expected:
        if source in found:
            matched = matched + 1
        if source in details["pool_sources"]:
            in_pool = True

    coverage = 0
    if len(expected) > 0:
        coverage = matched / len(expected)

    if should_reject:
        rejected = details["status"] in REJECT_STATUSES
        correct = rejected or matched > 0
    else:
        correct = matched > 0

    record["status"] = details["status"]
    record["search_text"] = details["search_text"]
    record["error"] = details["rerank_error"]
    record["found_sources"] = "; ".join(found)
    record["source_found"] = matched > 0
    record["coverage"] = round(coverage, 2)
    record["in_pool"] = in_pool
    record["correct"] = correct
    record["top_similarity"] = round(details["top_similarity"], 3)
    record["rewrite_ms"] = round(details["rewrite_seconds"] * 1000)
    record["embed_ms"] = round(details["embed_seconds"] * 1000)
    record["search_ms"] = round(details["search_seconds"] * 1000)
    record["rerank_ms"] = round(details["rerank_seconds"] * 1000)
    return record


def print_summary(scores):
    """Print overall and per-type results."""
    answerable = scores[scores["should_reject"] == False]
    rejects = scores[scores["should_reject"] == True]
    required = scores[scores["required_set"] == True]

    print()
    print(f"Questions: {len(scores)}")
    print(f"Overall correct: {scores['correct'].mean():.0%}")
    print(f"Required 10 correct: {required['correct'].mean():.0%}")
    print()
    print("Answerable questions:")
    print(f"  Source found: {answerable['source_found'].mean():.0%}")
    print(f"  Average coverage: {answerable['coverage'].mean():.0%}")
    print(f"  Source in candidates: {answerable['in_pool'].mean():.0%}")
    print()
    print("Questions that should be rejected:")
    print(f"  Correctly rejected: {rejects['correct'].mean():.0%}")
    print()

    by_type = scores.groupby("question_type").agg(
        questions=("id", "count"),
        correct=("correct", "mean"),
        coverage=("coverage", "mean"),
    )
    print(by_type.round(2).to_string())
    print()

    timing_columns = ["rewrite_ms", "embed_ms", "search_ms", "rerank_ms"]
    for column in timing_columns:
        print(f"Average {column}: {scores[column].mean():.0f}")

    wrong = scores[scores["correct"] == False]
    if len(wrong) > 0:
        print()
        print("Questions to look at:")
        for index, row in wrong.iterrows():
            print(f"  {row['id']} ({row['question_type']}): "
                  f"{row['status']}")


def make_threshold_chart(scores, label):
    """Chart top similarity for answerable vs reject questions."""
    chart_data = scores.copy()
    chart_data["Group"] = "Answerable"
    chart_data.loc[chart_data["should_reject"], "Group"] = "Should reject"

    points = alt.Chart(chart_data).mark_circle(size=80).encode(
        x=alt.X("top_similarity:Q", title="Top Similarity",
                scale=alt.Scale(domain=[0, 1])),
        y=alt.Y("Group:N", title=None),
        color=alt.Color("Group:N", legend=None),
        tooltip=["id", "question", "top_similarity", "status"],
    )
    line = alt.Chart(pd.DataFrame({"x": [THRESHOLD]})).mark_rule(
        strokeDash=[4, 4]
    ).encode(x="x:Q")

    chart = (points + line).properties(
        title=f"Where Good and Bad Matches Separate ({label})",
        width=600,
        height=150,
    )
    chart_path = RESULTS_FOLDER / f"threshold-chart-{label}.html"
    chart.save(chart_path)
    return chart_path


def run_evaluation(model=EMBEDDING_MODEL, label="before"):
    """Run every eval question and save the results."""
    questions = pd.read_csv(QUESTIONS_FILE)
    openai_client = OpenAI(api_key=get_api_key())
    collection = get_collection(model)
    RESULTS_FOLDER.mkdir(parents=True, exist_ok=True)

    records = []
    for index, row in questions.iterrows():
        print(f"Running {row['id']}...")
        record = score_question(row, openai_client, collection, model)
        records.append(record)

    scores = pd.DataFrame(records)
    results_path = RESULTS_FOLDER / f"results-{label}.csv"
    scores.to_csv(results_path, index=False)

    print_summary(scores)
    chart_path = make_threshold_chart(scores, label)
    print()
    print(f"Saved: {results_path}")
    print(f"Saved: {chart_path}")


if __name__ == "__main__":
    model = EMBEDDING_MODEL
    label = "before"
    if len(sys.argv) > 1:
        model = sys.argv[1]
    if len(sys.argv) > 2:
        label = sys.argv[2]
    run_evaluation(model, label)