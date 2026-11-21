"""Print every candidate in the pool with its re-rank score."""

import sys

from openai import OpenAI

from src.embed import embed_texts, get_api_key, get_collection
from src.rerank import rerank
from src.retrieve import (
    WEAK_SCORE,
    add_look_back,
    build_pool,
    filter_results,
    find_question_months,
    get_rank_key,
    is_cause_question,
)
from src.rewrite import rewrite_question

question = " ".join(sys.argv[1:])
openai_client = OpenAI(api_key=get_api_key())
collection = get_collection()

search_text = rewrite_question(question, "", openai_client)
months = find_question_months(search_text)
if is_cause_question(search_text):
    months = add_look_back(months)
embedding = embed_texts(openai_client, [search_text])[0]
pool = build_pool(collection, embedding, months)
passed = filter_results(pool, WEAK_SCORE)
rerank(search_text, passed, openai_client)
ranked = sorted(passed, key=get_rank_key, reverse=True)

print(f"Searched for: {search_text}")
print(f"Months: {months}")
print(f"Pool: {len(ranked)} candidates\n")
for position, result in enumerate(ranked, start=1):
    metadata = result["metadata"]
    score = result["rerank_score"]
    similarity = result["similarity"]
    print(f"{position:>2}. rerank {score} | {similarity:.3f} | "
          f"{metadata['source']}")
    print(f"    Section: {metadata['section']}")