"""The Analytics tab: how Seismo is being used."""

import os

import altair as alt
import pandas as pd
import streamlit as st

from src.analytics import (
    add_themes,
    average_step_times,
    build_question_table,
    count_cited_sources,
    count_outcomes,
    count_themes,
    find_gaps,
    load_found_via,
    load_questions,
    summarize,
)
from src.themes import SMALL_THEME_NAME, find_themes
from src.tiles import show_tile_grid

BLUE = "#7aa7d6"
AMBER = "#d9a54a"
LABEL_GREY = "#9aa4b2"
GREY = "#6b7280"
STEP_BLUES = ["#c3d8ef", "#9fc0e3", "#7aa7d6", "#4f86c2"]
OUTCOME_COLOURS = {
    "Answered": BLUE,
    "Related but Unanswered": AMBER,
    "Not About Tephra": GREY,
}
OUTCOME_STAGES = {
    "Answered": "Passed every step",
    "Related but Unanswered": "Passed the threshold, cut at "
                              "re-rank",
    "Not About Tephra": "Stopped at the threshold filter",
    "Declined by Moderation": "Stopped at the input check",
    "Too Long": "Stopped at the input check",
    "Empty": "Stopped at the input check",
    "Error": "Hit an error",
}
ROW_HEIGHT = 30
CHART_PADDING = {"top": 0, "bottom": 0, "left": 0, "right": 0}
BAR_THICKNESS = 12
SPLIT_BAR_HEIGHT = 14
LABELLED_BAR_HEIGHT = 84
LABEL_OFFSET = 26
LEADER_LENGTH = 12
SEGMENT_GAP = 0.004
LAST_LABELS = [SMALL_THEME_NAME, "Other"]


def sort_labels(data, value, label):
    """Order bars from biggest to smallest, with catch-alls last."""
    ordered = data.sort_values(value, ascending=False)
    labels = []
    last = []
    for name in ordered[label]:
        if name in LAST_LABELS:
            last.append(name)
        else:
            labels.append(name)
    return labels + last


def bar_chart(data, value, label, color=BLUE, number_format="d"):
    """Draw clean horizontal bars with the number at each end."""
    largest = data[value].max()
    base = alt.Chart(data).encode(
        y=alt.Y(
            f"{label}:N",
            sort=sort_labels(data, value, label),
            title=None,
            axis=alt.Axis(
                labelLimit=320, domain=False, ticks=False,
                labelPadding=8,
            ),
        ),
        x=alt.X(
            f"{value}:Q", axis=None,
            scale=alt.Scale(domain=[0, largest * 1.15]),
        ),
    )
    bars = base.mark_bar(
        color=color, cornerRadiusEnd=3, size=BAR_THICKNESS,
    ).encode(
        tooltip=[label, value],
    )
    numbers = base.mark_text(
        align="left", dx=6, color=LABEL_GREY,
    ).encode(text=alt.Text(f"{value}:Q", format=number_format))
    chart = (bars + numbers).properties(
        height=alt.Step(ROW_HEIGHT), padding=CHART_PADDING,
    )
    chart = chart.configure_view(stroke=None)
    st.altair_chart(chart, width="stretch")


def split_bar(parts, show_labels):
    """Draw one thin bar split into parts.

    parts is a table with value, colour and label columns. When
    show_labels is on, labels sit above and below the bar in turn,
    so short parts next to each other don't overlap.
    """
    parts = parts.reset_index(drop=True)
    total = parts["value"].sum()
    parts["end"] = parts["value"].cumsum()
    parts["start"] = parts["end"] - parts["value"] + total * SEGMENT_GAP
    parts["middle"] = (parts["start"] + parts["end"]) / 2
    x_scale = alt.Scale(domain=[0, total])

    bars = alt.Chart(parts).mark_bar(height=SPLIT_BAR_HEIGHT).encode(
        x=alt.X("start:Q", axis=None, scale=x_scale),
        x2="end:Q",
        color=alt.Color("colour:N", scale=None),
        tooltip=["label:N"],
    )
    layers = [bars]
    height = SPLIT_BAR_HEIGHT + 8
    if show_labels:
        height = LABELLED_BAR_HEIGHT
        centre = height / 2
        bar_top = centre - SPLIT_BAR_HEIGHT / 2
        bar_bottom = centre + SPLIT_BAR_HEIGHT / 2
        above = parts[parts.index % 2 == 0]
        below = parts[parts.index % 2 == 1]
        above_line = (bar_top - LEADER_LENGTH, bar_top)
        below_line = (bar_bottom, bar_bottom + LEADER_LENGTH)
        placements = [
            (above, -LABEL_OFFSET, above_line),
            (below, LABEL_OFFSET, below_line),
        ]
        for chosen, offset, (line_start, line_end) in placements:
            text = alt.Chart(chosen).mark_text(
                dy=offset, color=LABEL_GREY, fontSize=12,
            ).encode(x=alt.X("middle:Q", scale=x_scale), text="label:N")
            leader = alt.Chart(chosen).mark_rule(
                color=LABEL_GREY, strokeWidth=1,
            ).encode(
                x=alt.X("middle:Q", scale=x_scale),
                y=alt.value(line_start),
                y2=alt.value(line_end),
            )
            layers.append(leader)
            layers.append(text)

    chart = alt.layer(*layers).properties(
        height=height, padding=CHART_PADDING,
    )
    chart = chart.configure_view(stroke=None)
    st.altair_chart(chart, width="stretch")


def timing_chart(steps):
    """Show how long each step takes, as one labelled split bar."""
    labels = []
    for step, seconds in zip(steps["Step"], steps["Seconds"]):
        labels.append(f"{step} {seconds:.1f} s")
    parts = pd.DataFrame({
        "value": list(steps["Seconds"]),
        "colour": STEP_BLUES[:len(steps)],
        "label": labels,
    })
    split_bar(parts, show_labels=True)
    total = steps["Seconds"].sum()
    st.caption(
        f"These four steps take {total:.1f} seconds on average. The "
        "rest of the Average Answer Time goes mostly to the input "
        "check and moderation."
    )


def build_outcome_block(outcome, count, share):
    """Build one outcome: a label, its pipeline stage, a number."""
    colour = OUTCOME_COLOURS.get(outcome, GREY)
    stage = OUTCOME_STAGES.get(outcome, "")
    return (
        '<div class="outcome-block">'
        '<div class="outcome-label">'
        f'<span class="outcome-marker" '
        f'style="background-color:{colour}"></span>'
        f"{outcome}</div>"
        f'<div class="outcome-stage">{stage}</div>'
        f'<div class="outcome-number">{count}'
        f'<span class="outcome-share">{share:.0%}</span></div>'
        "</div>"
    )


def outcome_numbers(outcomes):
    """Show how questions were handled, as one number each."""
    total = outcomes["Questions"].sum()
    blocks = ""
    for outcome, count in zip(
        outcomes["Outcome"], outcomes["Questions"]
    ):
        blocks = blocks + build_outcome_block(
            outcome, count, count / total
        )
    st.html(f'<div class="outcome-numbers">{blocks}</div>')


def chart_card(title, caption):
    """Start a bordered card with a title and a short caption."""
    key = "card-" + title.lower().replace(" ", "-")
    card = st.container(border=True, key=key)
    card.markdown(f"**{title}**")
    if caption != "":
        card.caption(caption)
    return card


@st.cache_data(show_spinner="Sorting questions into themes...")
def cached_themes(question_list, _openai_client):
    """Find themes once per set of questions, then reuse them."""
    try:
        return find_themes(list(question_list), _openai_client)
    except Exception as error:
        print(f"Theme error: {error}")
        return {}


def get_analytics_password():
    """Find the analytics password in Render or local secrets."""
    password = os.environ.get("ANALYTICS_PASSWORD", "")
    if password != "":
        return password
    try:
        return st.secrets.get("ANALYTICS_PASSWORD", "")
    except Exception:
        return ""


def show_tiles(questions):
    """Show three headline numbers: volume and speed."""
    summary = summarize(questions)
    tiles = [
        ("Questions", summary["questions"]),
        ("Visits", summary["visits"]),
        ("Average Answer Time", f"{summary['average_seconds']:.1f} s"),
    ]
    show_tile_grid(tiles, 3)


def show_usage(questions):
    """The Usage section: tiles and how questions were handled."""
    st.subheader("Usage")
    show_tiles(questions)
    with chart_card("How Questions Were Handled", ""):
        outcome_numbers(count_outcomes(questions))


def count_theme_names(themes):
    """Count the named themes, leaving out the catch-all."""
    theme_names = set(themes.values())
    theme_names.discard(SMALL_THEME_NAME)
    return len(theme_names)


def describe_themes(theme_count):
    """Write the caption for the Question Themes card."""
    theme_text = f"{theme_count} themes"
    if theme_count == 1:
        theme_text = "1 theme"
    return (
        f"Seismo found {theme_text} by clustering questions with "
        "embeddings. The model names each theme, so the names never "
        "copy a visitor's words."
    )


def show_what_people_ask(questions, themes):
    """The What People Ask section: themes and content gaps."""
    st.subheader("What People Ask")
    with chart_card(
        "Question Themes",
        describe_themes(count_theme_names(themes)),
    ):
        bar_chart(count_themes(questions), "Questions", "Theme")

    with chart_card(
        "Where Seismo Came Up Short",
        "Questions Seismo couldn't answer from Tephra's documents, "
        "which point to what's missing.",
    ):
        gaps = find_gaps(questions)
        if len(gaps) == 0:
            st.caption("None so far.")
        else:
            bar_chart(
                count_themes(gaps), "Questions", "Theme", color=AMBER
            )


def show_sources_and_speed(questions):
    """The Sources and Speed section."""
    st.subheader("Sources and Speed")
    with chart_card("Most-Cited Documents", ""):
        cited = count_cited_sources(questions)
        if len(cited) == 0:
            st.caption("No citations yet.")
        else:
            bar_chart(cited, "Times cited", "Document")

    with chart_card(
        "Anatomy of an Answer",
        "How long each step takes, on average, for answered "
        "questions.",
    ):
        timing_chart(average_step_times(questions))


def show_visitors():
    """The Visitors section: where people found Seismo."""
    st.subheader("Visitors")
    with chart_card(
        "Where Visitors Found Seismo", "Real visitors only."
    ):
        found_via = load_found_via()
        if len(found_via) == 0:
            st.caption("No one has answered this yet.")
        else:
            bar_chart(found_via, "Visitors", "Where")


def show_private_details(questions):
    """Show raw questions only after the right password."""
    st.subheader("Private")
    card = st.container(border=True, key="card-private")
    card.markdown("**:material/lock: Private Details**")
    password = get_analytics_password()
    if password == "":
        card.caption("Set ANALYTICS_PASSWORD to unlock this section.")
        return
    typed = card.text_input("Password", type="password")
    if typed == "":
        card.caption(
            "Enter the owner's password to see what visitors asked."
        )
        return
    if typed != password:
        card.error("That password isn't right.")
        return

    card.markdown("**Questions Seismo Couldn't Answer**")
    card.dataframe(
        build_question_table(find_gaps(questions)), hide_index=True
    )
    card.markdown("**All Questions**")
    card.dataframe(build_question_table(questions), hide_index=True)


def describe_mix(questions):
    """Say how many sample and real questions are showing."""
    sample = (questions["visit_id"] == "sample").sum()
    real = len(questions) - sample
    real_text = f"{real} real question"
    if real != 1:
        real_text = real_text + "s"
    if sample == 0:
        return f"Showing {real_text}."
    return f"Showing {sample} sample and {real_text}."


def show_analytics(openai_client):
    """Draw the whole Analytics tab."""
    include_sample = st.toggle(
        "Include Sample Questions",
        value=True,
        help="The 54 test questions from Seismo's evaluation, asked "
             "once before launch.",
    )
    questions = load_questions(include_sample)
    if len(questions) == 0:
        st.info("No questions yet. Ask Seismo something in Chat.")
        return
    st.caption(describe_mix(questions))

    themes = cached_themes(tuple(questions["question"]), openai_client)
    questions = add_themes(questions, themes)

    show_usage(questions)
    if len(themes) > 0:
        show_what_people_ask(questions, themes)
    show_sources_and_speed(questions)
    show_visitors()
    show_private_details(questions)