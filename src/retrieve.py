"""Find the chunks most similar to a question."""

import re
import sys
import time

from openai import OpenAI

from src.embed import (
    EMBEDDING_MODEL,
    embed_texts,
    get_api_key,
    get_collection,
)
from src.rerank import rerank


TOP_K = 5
CANDIDATES = 20
MAX_SOURCES_PER_SECTION = 2
SEATS_PER_MONTH = 2
MONTH_CANDIDATES = 6
MAX_MONTHS = 6
RERANK_KEEP = 6
RERANK_MIN_SCORE = 2
DEFAULT_YEARS = ["2025", "2024"]

STRONG_SCORE = 0.50
POTENTIAL_SCORE = 0.35
WEAK_SCORE = 0.25
THRESHOLD = POTENTIAL_SCORE

MONTH_WORDS = {
    "january": ["01"], "jan": ["01"],
    "february": ["02"], "feb": ["02"],
    "march": ["03"], "mar": ["03"],
    "april": ["04"], "apr": ["04"],
    "may": ["05"],
    "june": ["06"], "jun": ["06"],
    "july": ["07"], "jul": ["07"],
    "august": ["08"], "aug": ["08"],
    "september": ["09"], "sept": ["09"], "sep": ["09"],
    "october": ["10"], "oct": ["10"],
    "november": ["11"], "nov": ["11"],
    "december": ["12"], "dec": ["12"],
}
PERIOD_WORDS = {
    "q1": ["01", "02", "03"],
    "first quarter": ["01", "02", "03"],
    "q2": ["04", "05", "06"],
    "second quarter": ["04", "05", "06"],
    "q3": ["07", "08", "09"],
    "third quarter": ["07", "08", "09"],
    "q4": ["10", "11", "12"],
    "fourth quarter": ["10", "11", "12"],
    "h1": ["01", "02", "03", "04", "05", "06"],
    "first half": ["01", "02", "03", "04", "05", "06"],
    "h2": ["07", "08", "09", "10", "11", "12"],
    "second half": ["07", "08", "09", "10", "11", "12"],
    "spring": ["03", "04"],
    "summer": ["06", "07", "08"],
    "autumn": ["09", "10", "11"],
    "in the fall": ["09", "10", "11"],
    "winter": ["12", "01", "02"],
    "early season": ["10", "11", "12"],
    "end-of-season sale": ["05", "06", "07", "08"],
    "end of season sale": ["05", "06", "07", "08"],
    "black friday": ["11"],
    "cyber monday": ["11", "12"],
    "bfcm": ["11", "12"],
    "holiday": ["12"],
}
FOLLOW_UP_STARTS = (
    "what about", "how about", "and ", "same for", "what if",
)
FOLLOW_UP_WORDS = ["it", "that", "this", "they", "those", "them"]


def classify_score(similarity):
    """Label a similarity score with a relevance tier."""
    if similarity >= STRONG_SCORE:
        return "Strongly relevant"
    if similarity >= POTENTIAL_SCORE:
        return "Potentially relevant"
    if similarity >= WEAK_SCORE:
        return "Weakly relevant"
    return "Irrelevant"


def add_months(found_months, new_months):
    """Add months to a list, skipping ones already in it."""
    for month in new_months:
        if month not in found_months:
            found_months.append(month)


def find_question_months(question):
    """Find the months a question asks about, like 2025-03."""
    lowered = question.lower()
    month_numbers = []

    for phrase in PERIOD_WORDS:
        if re.search(r"\b" + phrase + r"\b", lowered):
            add_months(month_numbers, PERIOD_WORDS[phrase])

    for word in MONTH_WORDS:
        pattern = r"\b" + word + r"\b"
        if word == "may":
            if re.search(r"\bMay\b", question):
                add_months(month_numbers, MONTH_WORDS[word])
        elif re.search(pattern, lowered):
            add_months(month_numbers, MONTH_WORDS[word])

    years = re.findall(r"\b(20\d{2})\b", question)
    if len(years) == 0:
        years = DEFAULT_YEARS

    months = []
    for number in month_numbers[:MAX_MONTHS]:
        labels = []
        for year in years:
            labels.append(f"{year}-{number}")
        months.append(labels)
    return months


def is_follow_up(question):
    """Guess whether a question depends on the one before."""
    lowered = question.lower().strip()
    words = re.findall(r"[a-z0-9']+", lowered)
    if len(words) <= 6:
        return True
    if lowered.startswith(FOLLOW_UP_STARTS):
        return True
    for word in FOLLOW_UP_WORDS:
        if word in words:
            return True
    return False


def build_search_text(question, previous_question):
    """Add the previous question to a follow-up question."""
    if previous_question == "":
        return question
    if is_follow_up(question):
        return previous_question + " " + question
    return question


def build_results(found, month_match):
    """Turn a ChromaDB search into a list of results."""
    results = []
    for index in range(len(found["ids"][0])):
        distance = found["distances"][0][index]
        similarity = 1 - distance
        result = {
            "chunk_id": found["ids"][0][index],
            "text": found["documents"][0][index],
            "metadata": found["metadatas"][0][index],
            "distance": distance,
            "similarity": similarity,
            "tier": classify_score(similarity),
            "month_match": month_match,
        }
        results.append(result)
    return results


def get_similarity(result):
    """Return a result's similarity, for sorting."""
    return result["similarity"]


def pick_varied(results, top_k):
    """Pick the top results, from at most 2 files per section."""
    picked = []
    section_sources = {}
    for result in results:
        section = result["metadata"]["section"]
        source = result["metadata"]["source"]
        sources = section_sources.get(section, [])
        if source not in sources:
            if len(sources) >= MAX_SOURCES_PER_SECTION:
                continue
            sources.append(source)
            section_sources[section] = sources
        picked.append(result)
        if len(picked) == top_k:
            break
    return picked


def search(collection, embedding, count, where=None):
    """Run one ChromaDB search, with an optional filter."""
    if where is None:
        return collection.query(
            query_embeddings=[embedding],
            n_results=count,
            include=["documents", "metadatas", "distances"],
        )
    return collection.query(
        query_embeddings=[embedding],
        n_results=count,
        where=where,
        include=["documents", "metadatas", "distances"],
    )


def get_rank_key(result):
    """Sort by re-rank score first, then by similarity."""
    return (result["rerank_score"], result["similarity"])


def build_pool(collection, embedding, months):
    """Gather candidates: the top overall, plus each month's."""
    found = search(collection, embedding, CANDIDATES)
    pool = build_results(found, False)

    seen_ids = []
    for result in pool:
        seen_ids.append(result["chunk_id"])

    for labels in months:
        where = {"month": {"$in": labels}}
        count = MONTH_CANDIDATES + len(seen_ids)
        month_found = search(collection, embedding, count, where)
        added = 0
        for result in build_results(month_found, True):
            if added == MONTH_CANDIDATES:
                break
            if result["chunk_id"] not in seen_ids:
                pool.append(result)
                seen_ids.append(result["chunk_id"])
                added = added + 1

    return sorted(pool, key=get_similarity, reverse=True)


def pick_without_rerank(passed, month_count):
    """Backup choice if re-ranking fails: varied top results."""
    general = []
    month_results = []
    for result in passed:
        if result["month_match"]:
            month_results.append(result)
        else:
            general.append(result)
    picked = pick_varied(general, TOP_K)
    seats = SEATS_PER_MONTH * month_count
    picked = picked + month_results[:seats]
    return sorted(picked, key=get_similarity, reverse=True)


def pick_after_rerank(passed):
    """Keep the most useful results, by re-rank score."""
    ranked = sorted(passed, key=get_rank_key, reverse=True)
    picked = []
    for result in ranked:
        if result["rerank_score"] < RERANK_MIN_SCORE:
            break
        picked.append(result)
        if len(picked) == RERANK_KEEP:
            break
    return picked


def retrieve(question, openai_client, collection,
             previous_question="", model=EMBEDDING_MODEL):
    """Find the chunks that best answer a question."""
    question = question.strip()
    if question == "":
        raise ValueError("Please type a question first.")
    if collection.count() == 0:
        raise RuntimeError("The knowledge base is empty.")

    search_text = build_search_text(question, previous_question)
    months = find_question_months(question)
    if len(months) == 0 and search_text != question:
        months = find_question_months(previous_question)

    details = {
        "search_text": search_text,
        "months": months,
        "status": "ok",
        "reranked": False,
        "rerank_error": "",
        "rerank_seconds": 0,
    }

    embed_start = time.perf_counter()
    embedding = embed_texts(openai_client, [search_text], model)[0]
    details["embed_seconds"] = time.perf_counter() - embed_start

    search_start = time.perf_counter()
    pool = build_pool(collection, embedding, months)
    details["search_seconds"] = time.perf_counter() - search_start
    details["pool_size"] = len(pool)

    passed = filter_results(pool)
    details["passed_threshold"] = len(passed)
    if len(passed) == 0:
        details["status"] = "no_match"
        return [], details

    rerank_start = time.perf_counter()
    try:
        rerank(search_text, passed, openai_client)
        results = pick_after_rerank(passed)
        details["reranked"] = True
    except Exception as error:
        details["rerank_error"] = str(error)
        results = pick_without_rerank(passed, len(months))
    details["rerank_seconds"] = time.perf_counter() - rerank_start

    if len(results) == 0:
        details["status"] = "not_found"
    return results, details


def filter_results(results, threshold=THRESHOLD):
    """Keep only results at or above the threshold."""
    kept = []
    for result in results:
        if result["similarity"] >= threshold:
            kept.append(result)
    return kept


def print_results(question, results, details):
    """Print each result's scores, tier and source."""
    print(f"Question: {question}")
    print(f"Searched for: {details['search_text']}")
    print(f"Months found: {details['months']}")
    print(f"Candidates: {details['pool_size']}")
    print(f"Passed threshold: {details['passed_threshold']}")
    print(f"Re-ranked: {details['reranked']}")
    if details["rerank_error"] != "":
        print(f"Re-rank error: {details['rerank_error']}")
    print(f"Status: {details['status']}")
    print()
    for result in results:
        metadata = result["metadata"]
        label = result["tier"]
        if result["month_match"]:
            label = label + " (month)"
        score = result.get("rerank_score", "-")
        print(f"{result['similarity']:.3f} | rerank {score} | {label}")
        print(f"   {metadata['source']}")
        print(f"   Section: {metadata['section']}")
    print()
    embed_ms = details["embed_seconds"] * 1000
    search_ms = details["search_seconds"] * 1000
    rerank_ms = details["rerank_seconds"] * 1000
    print(f"Question embedding: {embed_ms:.0f} ms")
    print(f"Search: {search_ms:.0f} ms")
    print(f"Re-ranking: {rerank_ms:.0f} ms")


if __name__ == "__main__":
    words = sys.argv[1:]
    previous_question = ""
    if "--after" in words:
        position = words.index("--after")
        previous_question = " ".join(words[position + 1:])
        words = words[:position]
    question = " ".join(words)

    openai_client = OpenAI(api_key=get_api_key())
    collection = get_collection()
    results, details = retrieve(
        question, openai_client, collection, previous_question
    )
    print_results(question, results, details)