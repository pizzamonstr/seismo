"""Grade Seismo's full answers against the answer key."""

import json
import re
import sys
import time

import pandas as pd
from openai import OpenAI

from src.embed import get_api_key, get_collection
from src.evaluate import (
    QUESTIONS_FILE,
    REJECT_STATUSES,
    REJECT_TYPES,
    RESULTS_FOLDER,
    is_required,
    read_expected_sources,
)
from src.generate import (
    CITATION_PATTERN,
    answer_question,
    build_sources,
)

GRADER_MODEL = "gpt-6.1-terra"
GRADER_EFFORT = "low"
VERDICT_POINTS = {"correct": 1.0, "partial": 0.5, "wrong": 0.0}

GRADER_INSTRUCTIONS = """You grade answers from Seismo, a \
chatbot that answers questions using a brand's documents.

You get the question, the expected answer from an answer key, \
Seismo's answer and the sources Seismo was given.

Give a verdict:
- "correct": it states the key facts of the expected answer. \
Extra true detail is fine. Wording can differ.
- "partial": it gets some key facts but misses or blurs others.
- "wrong": it misses the main point, gets a key fact wrong, or \
answers when it should have declined.

If the expected answer says the documents don't cover the \
question, or that Seismo should decline, the answer is \
"correct" when it says it can't find or doesn't know, and \
invents nothing. A short fallback message counts as correct.

Also check grounding. Set "grounded" to false if the answer \
states a number, date, name or cause that is not in the \
sources. Fallback messages with no sources are grounded.

Reply with JSON only, in this shape:
{"verdict": "correct", "grounded": true, "reason": "one short \
sentence"}"""


def grade_answer(row, answer, openai_client):
    """Ask the grader model to judge one answer."""
    sources = "No sources (fallback message)."
    if len(answer["results"]) > 0:
        sources = build_sources(answer["results"])

    message = (
        f"Question: {row['question']}\n\n"
        f"Expected answer: {row['expected_answer']}\n\n"
        f"Seismo's answer:\n{answer['text']}\n\n"
        f"Sources:\n{sources}"
    )
    response = openai_client.chat.completions.create(
        model=GRADER_MODEL,
        reasoning_effort=GRADER_EFFORT,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": GRADER_INSTRUCTIONS},
            {"role": "user", "content": message},
        ],
    )
    grade = json.loads(response.choices[0].message.content)
    verdict = str(grade.get("verdict", "wrong")).lower()
    if verdict not in VERDICT_POINTS:
        verdict = "wrong"
    grade["verdict"] = verdict
    return grade


def count_bad_citations(answer):
    """Count citation numbers that point at no source."""
    bad = 0
    for found in re.findall(CITATION_PATTERN, answer["text"]):
        number = int(found)
        if number < 1 or number > len(answer["results"]):
            bad = bad + 1
    return bad


def run_question(row, openai_client, collection):
    """Answer one question, grade it and record the results."""
    expected = read_expected_sources(row["source_documents"])
    should_reject = row["question_type"] in REJECT_TYPES
    record = {
        "id": row["id"],
        "question_type": row["question_type"],
        "required_set": is_required(row["required_set"]),
        "question": row["question"],
        "should_reject": should_reject,
    }

    start = time.perf_counter()
    try:
        answer = answer_question(
            row["question"], openai_client, collection
        )
    except Exception as error:
        record["verdict"] = "wrong"
        record["points"] = 0.0
        record["reason"] = f"Error: {error}"
        return record
    record["total_seconds"] = round(time.perf_counter() - start, 1)

    found = []
    for result in answer["results"]:
        source = result["metadata"]["source"]
        if source not in found:
            found.append(source)
    cited = []
    for citation in answer["citations"]:
        if citation["source"] not in cited:
            cited.append(citation["source"])

    retrieved = False
    cited_expected = False
    for source in expected:
        if source in found:
            retrieved = True
        if source in cited:
            cited_expected = True

    try:
        grade = grade_answer(row, answer, openai_client)
    except Exception as error:
        grade = {
            "verdict": "wrong",
            "grounded": False,
            "reason": f"Grader error: {error}",
        }

    record["status"] = answer["details"]["status"]
    record["rejected"] = record["status"] in REJECT_STATUSES
    record["retrieved_expected"] = retrieved
    record["cited_expected"] = cited_expected
    record["citation_count"] = len(answer["citations"])
    record["bad_citations"] = count_bad_citations(answer)
    record["verdict"] = grade["verdict"]
    record["points"] = VERDICT_POINTS[grade["verdict"]]
    record["grounded"] = bool(grade.get("grounded", False))
    record["reason"] = grade.get("reason", "")
    record["answer"] = answer["text"]
    record["expected_answer"] = row["expected_answer"]
    record["cited_sources"] = "; ".join(cited)
    return record


def print_required_table(scores):
    """Print the course's required 10 test record."""
    required = scores[scores["required_set"] == True]
    columns = [
        "id", "question_type", "retrieved_expected", "verdict",
        "cited_expected", "rejected",
    ]
    print("Required 10:")
    print(required[columns].to_string(index=False))


def print_summary(scores):
    """Print answer quality, grounding and citation results."""
    answerable = scores[scores["should_reject"] == False]
    rejects = scores[scores["should_reject"] == True]
    counts = scores["verdict"].value_counts(normalize=True)

    print()
    print(f"Questions: {len(scores)}")
    print(f"Answer score: {scores['points'].mean():.0%}")
    for verdict in VERDICT_POINTS:
        print(f"  {verdict}: {counts.get(verdict, 0):.0%}")
    print(f"Grounded: {scores['grounded'].mean():.0%}")
    print()
    print("Answerable questions:")
    has_citation = answerable["citation_count"] > 0
    print(f"  Has a citation: {has_citation.mean():.0%}")
    print(f"  Cites an expected source: "
          f"{answerable['cited_expected'].mean():.0%}")
    bad = answerable["bad_citations"].sum()
    print(f"  Bad citation numbers: {bad}")
    print()
    print(f"Should-reject answer score: {rejects['points'].mean():.0%}")
    print(f"Average total time: {scores['total_seconds'].mean():.1f} s")
    print()

    by_type = scores.groupby("question_type").agg(
        questions=("id", "count"),
        score=("points", "mean"),
        grounded=("grounded", "mean"),
    )
    print(by_type.round(2).to_string())
    print()
    print_required_table(scores)

    to_check = scores[
        (scores["verdict"] != "correct") | (scores["grounded"] == False)
    ]
    if len(to_check) > 0:
        print()
        print("Answers to look at:")
        for index, row in to_check.iterrows():
            print(f"  {row['id']} ({row['verdict']}, grounded "
                  f"{row['grounded']}): {row['reason']}")


def run_grading(label="answers"):
    """Answer and grade every eval question, then save results."""
    questions = pd.read_csv(QUESTIONS_FILE)
    openai_client = OpenAI(api_key=get_api_key())
    collection = get_collection()
    RESULTS_FOLDER.mkdir(parents=True, exist_ok=True)

    records = []
    for index, row in questions.iterrows():
        print(f"Answering {row['id']}...")
        records.append(run_question(row, openai_client, collection))

    scores = pd.DataFrame(records)
    results_path = RESULTS_FOLDER / f"answers-{label}.csv"
    scores.to_csv(results_path, index=False)
    print_summary(scores)
    print()
    print(f"Saved: {results_path}")


if __name__ == "__main__":
    label = "answers"
    if len(sys.argv) > 1:
        label = sys.argv[1]
    run_grading(label)