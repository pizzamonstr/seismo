"""The How It Works tab: what Seismo is and how it was built."""

from pathlib import Path

import pandas as pd
import streamlit as st

RETRIEVAL_RESULTS = Path("eval/results/results-round6.csv")
ANSWER_RESULTS = Path("eval/results/answers-round4.csv")
GITHUB_URL = "https://github.com/pizzamonstr/seismo"
STEPS_PER_ROW = 4

WHAT_IT_IS = (
    "When a marketing metric moves, the reason is usually scattered "
    "across agency reports, change logs, Slack threads and meeting "
    "notes. Often it shows up as a gap between what an ad platform "
    "reports and what the business actually saw in Shopify.\n\n"
    "Seismo reads all of those documents for Tephra, a fictional "
    "backcountry ski brand, and answers \"why did this move?\" in "
    "plain language, citing the exact documents it used."
)

PIPELINE_STEPS = [
    ("Question", "Ask in your own words, typos and all."),
    ("Check", "Too long or harmful questions are turned away."),
    ("Rewrite", "Fixes spelling, follow-ups and jargon."),
    ("Search", "Looks by topic, month, folder and cause."),
    ("Gate", "Questions not about Tephra stop here."),
    ("Re-rank", "Scores up to 70 passages and keeps 8."),
    ("Write", "Answers only from those 8 sources."),
    ("Cite", "Numbers each source so you can check it."),
]

DESIGN_CHOICES = [
    (
        "Format-aware chunking",
        "PDF tables are rebuilt from text positions, so a single row, "
        "like Meta CPA in January 2025, can be found on its own.",
    ),
    (
        "A metric map",
        "A glossary plus the usual causes behind each metric, so "
        "\"why\" questions get a second search for likely causes.",
    ),
    (
        "Fair seats in the search",
        "Agency reports are 63% of the chunks, so every folder and "
        "month in the question gets its own seats in the search.",
    ),
    (
        "Re-ranking",
        "A small model scores every candidate from 0 to 3 in "
        "parallel batches, so the answer model reads only the best 8.",
    ),
    (
        "Guardrails",
        "Answers come only from sources, sources are treated as "
        "data, harmful questions are declined and visits have limits.",
    ),
    (
        "Tested after every change",
        "54 questions with known answers were rerun after each "
        "change, so every fix was measured instead of guessed.",
    ),
]

LIMITATIONS = [
    "Seismo finds the best evidence, not all of it. Questions that "
    "need every month added up, or a full list of everything, can "
    "come back incomplete.",
    "The same model family writes the answers and grades them, so "
    "the answer scores may be a little generous.",
    "The evaluation questions were written alongside Seismo, so the "
    "scores show it works on this storyline, not on any brand.",
    "Ask about the same thing twice and the wording can differ, "
    "because the models are not fully deterministic.",
]

TECH_STACK = [
    "Python, pandas and Altair",
    "OpenAI text-embedding-3-small for search",
    "ChromaDB for the vector database",
    "GPT-6 Luna for rewriting, re-ranking and themes",
    "GPT-6.1 Terra for answers",
    "Streamlit for the app, hosted on Render",
]

CARD_STYLE = """
<style>
.step-row {
    display: grid;
    grid-template-columns: 1fr 2rem 1fr 2rem 1fr 2rem 1fr;
    margin-bottom: 1rem;
}
.card-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1rem;
    margin-bottom: 1rem;
}
.card {
    border: 1px solid #7aa7d6;
    border-radius: 0.6rem;
    padding: 0.9rem 1rem;
}
.card-title {
    color: #7aa7d6;
    font-weight: 600;
    margin-bottom: 0.35rem;
}
.card-number {
    font-size: 0.8rem;
    opacity: 0.75;
    margin-right: 0.35rem;
}
.card-text {
    font-size: 0.9rem;
    line-height: 1.45;
}
.step-arrow {
    color: #8a8f98;
    align-self: center;
    text-align: center;
}
</style>
"""


def build_card(title, text, number=None):
    """Build one bordered card with a title and a short text."""
    label = title
    if number is not None:
        label = f'<span class="card-number">{number}</span>{title}'
    return (
        f'<div class="card"><div class="card-title">{label}</div>'
        f'<div class="card-text">{text}</div></div>'
    )


def build_steps_html():
    """Build the numbered step cards, four to a row with arrows."""
    rows = []
    for start in range(0, len(PIPELINE_STEPS), STEPS_PER_ROW):
        row = PIPELINE_STEPS[start:start + STEPS_PER_ROW]
        cells = []
        for position, (title, text) in enumerate(row):
            number = start + position + 1
            cells.append(build_card(title, text, number))
            if position < len(row) - 1:
                cells.append('<div class="step-arrow">&#8594;</div>')
        rows.append(f'<div class="step-row">{"".join(cells)}</div>')
    return CARD_STYLE + "".join(rows)


def build_choices_html():
    """Build the design choice cards, two to a row."""
    cards = []
    for title, text in DESIGN_CHOICES:
        cards.append(build_card(title, text))
    return CARD_STYLE + f'<div class="card-grid">{"".join(cards)}</div>'


def load_scores():
    """Read the latest evaluation results, if they are present."""
    if not RETRIEVAL_RESULTS.exists() or not ANSWER_RESULTS.exists():
        return None, None
    retrieval = pd.read_csv(RETRIEVAL_RESULTS)
    answers = pd.read_csv(ANSWER_RESULTS)
    return retrieval, answers


def build_score_tiles(retrieval, answers):
    """Work out the six headline results."""
    answerable = retrieval[retrieval["should_reject"] == False]
    rejects = answers[answers["should_reject"] == True]
    wrong = (answers["verdict"] == "wrong").mean()
    return [
        ("Sources found", f"{answerable['source_found'].mean():.0%}"),
        ("Answer score", f"{answers['points'].mean():.0%}"),
        ("Wrong answers", f"{wrong:.0%}"),
        ("Grounded", f"{answers['grounded'].mean():.0%}"),
        ("Off-topic handled", f"{rejects['points'].mean():.0%}"),
        ("Average answer", f"{answers['total_seconds'].mean():.1f} s"),
    ]


def build_required_table(answers):
    """Show the course's required 10 test questions."""
    required = answers[answers["required_set"] == True]
    yes_no = {True: "Yes", False: "No"}
    table = pd.DataFrame({
        "Question": required["question"],
        "Type": required["question_type"].str.title(),
        "Retrieved": required["retrieved_expected"].map(yes_no),
        "Answer": required["verdict"].str.title(),
        "Cited": required["cited_expected"].map(yes_no),
        "Rejected": required["rejected"].map(yes_no),
    })
    return table


def show_evaluation():
    """Show the evaluation results, read from the saved files."""
    st.subheader("How Well It Works")
    retrieval, answers = load_scores()
    if retrieval is None:
        st.caption("Evaluation results aren't available here.")
        return
    st.markdown(
        "Seismo was tested on 54 questions with known answers: facts, "
        "diagnoses, red herrings, misspellings, paraphrases and "
        "questions it should turn down."
    )
    tiles = build_score_tiles(retrieval, answers)
    for start in range(0, len(tiles), 3):
        columns = st.columns(3)
        for column, (label, value) in zip(columns, tiles[start:]):
            column.metric(label, value)

    with st.expander("See the required 10 test questions"):
        st.table(build_required_table(answers), hide_index=True)


def show_lists():
    """Show limitations and the tech stack side by side."""
    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Limitations")
        for item in LIMITATIONS:
            st.markdown(f"- {item}")
    with right:
        st.subheader("Built With")
        for item in TECH_STACK:
            st.markdown(f"- {item}")
        st.markdown(f"[View the code on GitHub]({GITHUB_URL})")


def show_how_it_works():
    """Draw the whole How It Works tab."""
    st.subheader("What Seismo Is")
    st.markdown(WHAT_IT_IS)

    st.subheader("How a Question Becomes an Answer")
    st.html(build_steps_html())

    st.subheader("Design Choices That Mattered")
    st.html(build_choices_html())

    show_evaluation()
    show_lists()