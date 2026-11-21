"""Score retrieved chunks with a chat model."""

import json

RERANK_MODEL = "gpt-6-luna"
RERANK_EFFORT = "none"
MAX_PASSAGE_CHARS = 1200

RERANK_INSTRUCTIONS = """You help an assistant answer questions \
about Tephra, a backcountry ski gear brand, using its reports, \
change logs, tracking docs and team notes.

Score how useful each passage is for answering the question:
3 = directly answers it, or is key evidence for it
2 = useful supporting context
1 = loosely related
0 = not useful

Rules:
- Pay close attention to exact channels, metrics, products, \
people and time periods. A passage about the wrong month or \
the wrong channel is not useful, even if the topic matches.
- Prefer passages that directly state what was asked, such as \
a name, date or number, over passages that only describe the \
topic. For "who" or "when" questions, messages and meeting \
notes where people report what happened are often the answer.
- For full-year or annual questions, prefer passages that state \
full-year or year-to-date totals over single-month figures. \
Single-month figures are supporting context, so score them 2 \
at most for a full-year question.

Reply with JSON only, in this shape:
{"scores": [{"id": "P1", "score": 3}, {"id": "P2", "score": 0}]}
Score every passage."""


def build_passages(results):
    """Number each result as P1, P2 and so on for the prompt."""
    lines = []
    for index in range(len(results)):
        text = results[index]["text"][:MAX_PASSAGE_CHARS]
        lines.append(f"[P{index + 1}]\n{text}")
    return "\n\n".join(lines)


def read_scores(reply, count):
    """Turn the model's JSON reply into a list of scores."""
    data = json.loads(reply)
    scores = [0] * count
    for item in data["scores"]:
        number = int(str(item["id"]).lstrip("P")) - 1
        if 0 <= number < count:
            scores[number] = int(item["score"])
    return scores


def rerank(question, results, openai_client):
    """Add a 0 to 3 usefulness score to each result."""
    if len(results) == 0:
        return results

    message = (
        f"Question: {question}\n\n"
        f"Passages:\n\n{build_passages(results)}"
    )
    response = openai_client.chat.completions.create(
        model=RERANK_MODEL,
        reasoning_effort=RERANK_EFFORT,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": RERANK_INSTRUCTIONS},
            {"role": "user", "content": message},
        ],
    )
    reply = response.choices[0].message.content
    scores = read_scores(reply, len(results))

    for index in range(len(results)):
        results[index]["rerank_score"] = scores[index]
    return results