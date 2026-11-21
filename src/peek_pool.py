"""Print every candidate in the pool with its re-rank score."""

import sys

from openai import OpenAI

from src.embed import get_api_key, get_collection
from src.rerank import rerank
from src.retrieve import (
    WEAK_SCORE,
    filter_results,
    gather_pool,
    get_rank_key,
)
from src.rewrite import rewrite_question

question = " ".join(sys.argv[1:])
openai_client = OpenAI(api_key=get_api_key())
collection = get_collection()

search_text = rewrite_question(question, "", openai_client)
pool, plan = gather_pool(search_text, openai_client, collection)
passed = filter_results(pool, WEAK_SCORE)
rerank(search_text, passed, openai_client)
ranked = sorted(passed, key=get_rank_key, reverse=True)

print(f"Searched for: {search_text}")
if len(plan["search_texts"]) > 1:
    print(f"Cause search: {plan['search_texts'][1]}")
print(f"Months: {plan['months']}")
print(f"Pool: {len(ranked)} candidates (C = from cause search)\n")
for position, result in enumerate(ranked, start=1):
    metadata = result["metadata"]
    score = result["rerank_score"]
    similarity = result["similarity"]
    marker = " "
    if result["cause_match"]:
        marker = "C"
    print(f"{position:>2}. {marker} rerank {score} | "
          f"{similarity:.3f} | {metadata['source']}")
    print(f"    Section: {metadata['section']}")