"""Ask Seismo the eval questions once and save them as sample usage."""

import time

import pandas as pd
from openai import OpenAI

from src.embed import get_api_key, get_collection
from src.evaluate import QUESTIONS_FILE
from src.generate import answer_question
from src.usage_log import SAMPLE_FILE, log_question

SAMPLE_VISIT_ID = "sample"


def seed_sample():
    """Answer every eval question and log it to the sample file."""
    questions = pd.read_csv(QUESTIONS_FILE)
    openai_client = OpenAI(api_key=get_api_key())
    collection = get_collection()

    if SAMPLE_FILE.exists():
        SAMPLE_FILE.unlink()

    for index, row in questions.iterrows():
        print(f"Asking {row['id']}...")
        start = time.perf_counter()
        try:
            answer = answer_question(
                row["question"], openai_client, collection
            )
        except Exception as error:
            print(f"  Skipped: {error}")
            continue
        details = answer["details"]
        details["write_seconds"] = answer["generate_seconds"]
        details["total_seconds"] = time.perf_counter() - start
        log_question(
            SAMPLE_VISIT_ID, row["question"], details,
            answer["citations"], path=SAMPLE_FILE,
        )

    print(f"\nSaved: {SAMPLE_FILE}")


if __name__ == "__main__":
    seed_sample()