"""Rewrite a question into a clear search query."""

from src.metric_map import GLOSSARY

REWRITE_MODEL = "gpt-6-luna"
REWRITE_EFFORT = "none"

REWRITE_INSTRUCTIONS = """You rewrite questions about Tephra, a \
backcountry ski gear brand, into clear search queries.

Rules:
- Fix spelling and grammar.
- If the question is a follow-up, use the previous question to \
make it complete on its own. Example: "What about February?" \
after "What was Meta's CPA in January 2025?" becomes "What was \
Meta's CPA in February 2025?"
- In a follow-up, keep the metric and channel but do not carry \
over a direction like "go up" or "drop". Ask how it changed \
instead. Example: "What about April?" after "Why did Meta CPA \
go up in March 2025?" becomes "How did Meta CPA change in \
April 2025, and why?"
- Keep every channel, metric, product, person and time period \
the user gave. Do not add new facts, dates or details.
- Tephra's product names include Matier, Rohr, Fissile, Pylon, \
Plinth, Bridge, Cerise, Spearhead, Wedge, Portage, Signal Hill, \
Nairn, Pebble, Mackenzie, Owl, Icecap, Joffre, Keyhole, \
Meadows, Spud Valley, One Mile, Birkenhead, Birken, Blowdown, \
Pioneer and Anderson.
- Spell out abbreviations once using the terms below, like \
"CAC (customer acquisition cost)".
- Reply with the rewritten question only.

""" + GLOSSARY


def rewrite_question(question, previous_question, openai_client):
    """Return a clean, standalone version of the question."""
    message = f"Question: {question}"
    if previous_question != "":
        message = (
            f"Previous question: {previous_question}\n"
            f"Question: {question}"
        )

    response = openai_client.chat.completions.create(
        model=REWRITE_MODEL,
        reasoning_effort=REWRITE_EFFORT,
        messages=[
            {"role": "system", "content": REWRITE_INSTRUCTIONS},
            {"role": "user", "content": message},
        ],
    )
    rewritten = response.choices[0].message.content.strip()
    if rewritten == "":
        raise ValueError("The rewrite came back empty.")
    return rewritten