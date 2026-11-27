"""The How It Works tab: what Seismo is and how it answers."""

from pathlib import Path

import pandas as pd
import streamlit as st

from src.tiles import show_tile_grid

RETRIEVAL_RESULTS = Path("eval/results/results-round6.csv")
ANSWER_RESULTS = Path("eval/results/answers-round4.csv")
GITHUB_URL = "https://github.com/pizzamonstr/seismo"
STEPS_PER_ROW = 4
TILES_PER_ROW = 4
COST_PER_QUESTION = "1¢ CAD"

WHAT_IT_IS = (
    "Seismo is a retrieval-augmented generation (RAG) chatbot built "
    "on 59 of Tephra's documents from 2025, including agency "
    "reports, change logs, Slack exports and meeting notes. Tephra "
    "is a fictional backcountry ski brand. Ask Seismo why a metric "
    "moved, and it answers in plain language and cites the exact "
    "documents it used."
)

PIPELINE_STEPS = [
    ("Question", "Receives the question as typed, including any "
                 "misspellings."),
    ("Input Check", "Rejects empty or overlong questions and runs "
                    "moderation to decline harmful ones."),
    ("Query Rewrite", "Fixes spelling, rewrites follow-ups as "
                      "standalone questions and expands "
                      "abbreviations using a glossary."),
    ("Semantic Search", "Embeds the query and runs a stratified "
                        "vector search by month, folder and likely "
                        "cause."),
    ("Threshold Filter", "Stops the question if no chunk reaches "
                         "the 0.32 similarity threshold."),
    ("Re-rank", "Scores up to 70 candidate chunks from 0 to 3 and "
                "keeps up to 8 that score 2 or higher."),
    ("Generate", "Writes a grounded answer from only the kept "
                 "chunks."),
    ("Cite", "Numbers each cited source and shows it in View "
             "Sources."),
]

CARD_STYLE = """
<style>
.step-row {
    display: grid;
    grid-template-columns: 1fr 2rem 1fr 2rem 1fr 2rem 1fr;
    margin-bottom: 1rem;
}
.card {
    border: 1px solid #7aa7d6;
    border-radius: 0.6rem;
    padding: 0.9rem 1rem;
}
.card-title {
    display: flex;
    align-items: flex-start;
    line-height: 1.5rem;
    color: #7aa7d6;
    font-weight: 600;
    margin-bottom: 0.5rem;
}
.card-number {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 1.5rem;
    height: 1.5rem;
    border: 1px solid #7aa7d6;
    border-radius: 50%;
    flex-shrink: 0;
    font-size: 0.8rem;
    margin-right: 0.5rem;
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
@media (max-width: 640px) {
    .step-row {
        grid-template-columns: 1fr;
        gap: 1rem;
    }
    .step-arrow {
        display: none;
    }
}
</style>
"""


def build_card(title, text, number):
    """Build one numbered, bordered card with a short text."""
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


def load_scores():
    """Read the latest evaluation results, if they are present."""
    if not RETRIEVAL_RESULTS.exists() or not ANSWER_RESULTS.exists():
        return None, None
    retrieval = pd.read_csv(RETRIEVAL_RESULTS)
    answers = pd.read_csv(ANSWER_RESULTS)
    return retrieval, answers


def build_score_tiles(retrieval, answers):
    """Work out the eight headline results."""
    answerable = retrieval[retrieval["should_reject"] == False]
    answerable_answers = answers[answers["should_reject"] == False]
    rejects = answers[answers["should_reject"] == True]
    wrong = (answers["verdict"] == "wrong").mean()
    return [
        ("Expected Source Retrieved",
         f"{answerable['source_found'].mean():.0%}"),
        ("Answer Score", f"{answers['points'].mean():.0%}"),
        ("Wrong Answers", f"{wrong:.0%}"),
        ("Grounded Answers", f"{answers['grounded'].mean():.0%}"),
        ("Expected Source Cited",
         f"{answerable_answers['cited_expected'].mean():.0%}"),
        ("Correct Rejections", f"{rejects['points'].mean():.0%}"),
        ("Average Answer Time",
         f"{answers['total_seconds'].mean():.1f} s"),
        ("Cost per Question", COST_PER_QUESTION),
    ]


def build_proof_line():
    """Sum up the evaluation in one line for the page header."""
    retrieval, answers = load_scores()
    if answers is None:
        return ""
    score = answers["points"].mean()
    wrong = (answers["verdict"] == "wrong").sum()
    wrong_text = "no wrong answers"
    if wrong == 1:
        wrong_text = "1 wrong answer"
    elif wrong > 1:
        wrong_text = f"{wrong} wrong answers"
    seconds = answers["total_seconds"].mean()
    return (
        f"Tested on {len(answers)} questions: {score:.0%} answer "
        f"score, {wrong_text}, {seconds:.1f} s average answer "
        "time."
    )


def show_evaluation():
    """Show the headline evaluation results as tiles."""
    st.subheader("Evaluation")
    retrieval, answers = load_scores()
    if retrieval is None:
        st.caption("Evaluation results aren't available here.")
        return
    st.markdown(
        "Seismo was tested on 54 questions with known answers, "
        "including facts, diagnoses, red herrings, misspellings, "
        "paraphrases and irrelevant questions it should reject."
    )
    tiles = build_score_tiles(retrieval, answers)
    show_tile_grid(tiles, TILES_PER_ROW)


def show_how_it_works():
    """Draw the whole How It Works tab."""
    st.subheader("What Seismo Is")
    st.markdown(WHAT_IT_IS)

    st.subheader("The RAG Pipeline")
    st.html(build_steps_html())

    show_evaluation()

    st.markdown(
        "For the full write-up, including design choices, "
        f"limitations and the code, see the [README on GitHub]"
        f"({GITHUB_URL})."
    )