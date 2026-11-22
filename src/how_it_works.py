"""The How It Works tab: what Seismo is and how it was built."""

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
    "When a marketing metric moves, the reason is rarely in one "
    "place. It's spread across agency reports, change logs, Slack "
    "threads and meeting notes, and it often shows up as a gap "
    "between what an ad platform reports and what actually happened "
    "in Shopify.\n\n"
    "Seismo is a retrieval-augmented generation (RAG) chatbot built "
    "on 59 of those documents from Tephra, a fictional backcountry "
    "ski brand, covering all of 2025. Ask it why a metric moved, and "
    "it answers in plain language, citing the exact documents it "
    "used.\n\n"
    "Try it in the Chat tab."
)

WHY_I_BUILT_IT = (
    "I've spent about eight years in marketing, and the hardest "
    "part of the job is rarely the numbers themselves. It's "
    "finding out why they moved. The answer is usually buried in a "
    "change log, a Slack thread or an agency report, and digging it "
    "out can take hours. I built Seismo to do that digging."
)

HARDEST_PROBLEM = (
    "Asked why Meta retargeting fell apart in March 2025, Seismo "
    "repeated the agency's answer: creative fatigue. The real cause "
    "was a tracking script removed in a February 11 theme migration, "
    "and it was sitting in the change log and Slack. It just never "
    "made it into the candidate pool.\n\n"
    "Two things kept it out. Agency reports make up 63% of the "
    "chunks, so they crowded out every other folder. And the cause "
    "happened a month before the month in the question.\n\n"
    "I fixed it with reserved seats for every folder and month, a "
    "look-back to the month before, and a second search for likely "
    "causes from the metric map. Now Seismo names the removed script "
    "and explains why the creative fatigue story doesn't hold up."
)

PIPELINE_STEPS = [
    ("Question", "Takes your question in your own words, typos "
                 "and all."),
    ("Check", "Moderation turns away questions that are too long "
              "or harmful."),
    ("Rewrite", "Fixes spelling, completes follow-ups and expands "
                "jargon with a glossary."),
    ("Search", "Runs a vector search by topic, month, folder and "
               "likely cause."),
    ("Gate", "Stops questions with no chunk above the similarity "
             "threshold."),
    ("Re-rank", "Scores up to 70 candidate chunks and keeps the "
                "top 8."),
    ("Write", "Generates the answer using only those 8 chunks."),
    ("Cite", "Numbers each source so you can check it."),
]

DESIGN_CHOICES = [
    (
        "Format-Aware Chunking",
        "PDF tables are rebuilt from text positions, so a single "
        "row, like Meta's CPA in January 2025, can be retrieved on "
        "its own.",
    ),
    (
        "A Metric Map",
        "A glossary plus the usual causes behind each metric. For "
        "\"why\" questions, Seismo runs a second search for those "
        "likely causes, not just the symptom.",
    ),
    (
        "Fair Seats in the Search",
        "Agency reports make up 63% of the chunks, so every folder "
        "and every month in the question gets reserved seats in the "
        "candidate pool.",
    ),
    (
        "Re-ranking",
        "A smaller model scores up to 70 candidates from 0 to 3 in "
        "parallel batches. Only the top 8 go on to the model that "
        "generates the answer.",
    ),
    (
        "Guardrails",
        "Seismo answers only from retrieved sources and treats them "
        "as data, not instructions, to guard against prompt "
        "injection. Moderation declines harmful questions, and each "
        "visit has a question limit.",
    ),
    (
        "Tested After Every Change",
        "54 evaluation questions with known answers were rerun after "
        "each change, so every fix was measured, not guessed.",
    ),
]

LIMITATIONS = [
    "Retrieval finds the best evidence, not all of it. Questions "
    "that need every month aggregated, or an exhaustive list, can "
    "come back incomplete.",
    "The same model family generates and grades the answers, so "
    "the scores may be a little generous.",
    "The evaluation questions were written alongside Seismo, so the "
    "scores show it works on this storyline, not that it would "
    "generalize to any brand.",
    "Ask the same thing twice and the wording can change, because "
    "the models are not fully deterministic.",
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
    display: flex;
    align-items: center;
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
    .step-row,
    .card-grid {
        grid-template-columns: 1fr;
        gap: 1rem;
    }
    .step-arrow {
        display: none;
    }
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
    """Work out the eight headline results."""
    answerable = retrieval[retrieval["should_reject"] == False]
    answerable_answers = answers[answers["should_reject"] == False]
    rejects = answers[answers["should_reject"] == True]
    wrong = (answers["verdict"] == "wrong").mean()
    return [
        ("Sources Found", f"{answerable['source_found'].mean():.0%}"),
        ("Answer Score", f"{answers['points'].mean():.0%}"),
        ("Wrong Answers", f"{wrong:.0%}"),
        ("Grounded", f"{answers['grounded'].mean():.0%}"),
        ("Right Source Cited",
         f"{answerable_answers['cited_expected'].mean():.0%}"),
        ("Off-Topic Handled", f"{rejects['points'].mean():.0%}"),
        ("Average Answer", f"{answers['total_seconds'].mean():.1f} s"),
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
        f"score, {wrong_text}, {seconds:.1f} s average answer."
    )


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
    show_tile_grid(tiles, TILES_PER_ROW)

    with st.expander("See the Required 10 Test Questions"):
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

    st.subheader("Why I Built It")
    st.markdown(WHY_I_BUILT_IT)

    st.subheader("How a Question Becomes an Answer")
    st.html(build_steps_html())

    st.subheader("Design Choices That Mattered")
    st.html(build_choices_html())

    st.subheader("The Hardest Problem")
    st.markdown(HARDEST_PROBLEM)

    show_evaluation()
    show_lists()