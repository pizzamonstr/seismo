"""Seismo: a metric investigation assistant for Tephra."""

import time
from datetime import date

import openai
import streamlit as st
from openai import OpenAI

from src.embed import get_api_key, get_collection
from src.generate import (
    EMPTY_MESSAGE,
    ERROR_MESSAGE,
    TOO_LONG_MESSAGE,
    build_fallback_text,
    citations_from_mapping,
    prepare,
    renumber_stream,
    stream_answer,
)

st.set_page_config(page_title="Seismo", layout="centered")

SEISMO_AVATAR = ":material/earthquake:"
VISITOR_AVATAR = ":material/person:"
GREETING = (
    "Hey, I'm Seismo. I help the Tephra team figure out why the "
    "numbers moved, like a jump in ad costs or a slow sales month. "
    "I dig through Tephra's reports, change logs and team notes, "
    "and I show you exactly where each answer came from. What "
    "would you like to look into?"
)
STEP_LABELS = {
    "rewrite": "Listening for the tremor...",
    "search": "Reading the seismographs: reports, change logs "
              "and Slack...",
    "rerank": "Tracing the fault line...",
    "write": "Writing it up...",
}
MAX_QUESTIONS_PER_SESSION = 15
DAILY_QUESTION_CAP = 300
SESSION_LIMIT_MESSAGE = (
    "That's 15 questions for this visit, which is my limit. Thanks "
    "for digging in with me."
)
DAILY_LIMIT_MESSAGE = (
    "I've answered all the questions I can for today, so I'm taking "
    "a breather. Please check back tomorrow."
)
ERROR_MESSAGES = {
    "key": "I can't reach my tools right now. That's on my end, "
           "not yours. Please try again later.",
    "busy": "Lots of people are asking at once. Give it a few "
            "seconds and try again?",
    "connection": "I lost my connection for a moment. Try that "
                  "again?",
    "library": "My document library isn't loaded right now. Please "
               "try again in a few minutes.",
}
FOUND_VIA_OPTIONS = [
    "LinkedIn", "Portfolio site", "UBC class", "Somewhere else",
]
STARTER_QUESTIONS = [
    "Why did Meta ROAS jump to 5.4 in September 2025?",
    "Did the GA4 consent mode change in May 2025 cause lost sales?",
    "Why was October 2025 revenue down 18% year over year?",
    "What tracking or measurement problems did Tephra have in 2025?",
]
MORE_QUESTIONS = STARTER_QUESTIONS + [
    "Was creative fatigue the reason Meta retargeting performance "
    "fell in March 2025?",
    "Why did revenue drop so much in May 2025?",
    "What decision was made based on the inflated September Meta "
    "numbers, and what did it cost?",
    "Why wasn't the Fissile splitboard in the Black Friday 2025 sale?",
    "Was December 2025 a bad month, since revenue was lower than "
    "November?",
    "Why did summer 2025 AOV go up compared with a normal "
    "off-season?",
]


@st.cache_resource
def load_resources():
    """Open the OpenAI client and database once for every visitor."""
    openai_client = OpenAI(api_key=get_api_key())
    collection = get_collection()
    return openai_client, collection


@st.cache_resource
def daily_counter():
    """Count questions across all visitors, reset each day."""
    return {"date": "", "count": 0}


def daily_cap_reached():
    """Check the shared daily count, starting fresh each new day."""
    counter = daily_counter()
    today = str(date.today())
    if counter["date"] != today:
        counter["date"] = today
        counter["count"] = 0
    return counter["count"] >= DAILY_QUESTION_CAP


def count_question():
    """Add one question to this session and to today's total."""
    st.session_state.questions_asked += 1
    daily_counter()["count"] += 1


def session_limit_reached():
    """Check whether this visitor has used all their questions."""
    used = st.session_state.questions_asked
    return used >= MAX_QUESTIONS_PER_SESSION


def friendly_error(error):
    """Turn a technical error into a message in Seismo's voice."""
    if isinstance(error, openai.AuthenticationError):
        return ERROR_MESSAGES["key"]
    if isinstance(error, openai.RateLimitError):
        return ERROR_MESSAGES["busy"]
    if isinstance(error, openai.APIConnectionError):
        return ERROR_MESSAGES["connection"]
    if "knowledge base is empty" in str(error):
        return ERROR_MESSAGES["library"]
    return ERROR_MESSAGE


def start_session():
    """Set up this visitor's chat history."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "previous_question" not in st.session_state:
        st.session_state.previous_question = ""
    if "starter" not in st.session_state:
        st.session_state.starter = ""
    if "questions_asked" not in st.session_state:
        st.session_state.questions_asked = 0
    if "found_via" not in st.session_state:
        st.session_state.found_via = ""


def show_sources(citations):
    """List the cited sources in a fold-out panel."""
    if len(citations) == 0:
        return
    with st.expander("View sources"):
        for citation in citations:
            line = (
                f"**[{citation['number']}]** {citation['title']} "
                f"> {citation['section']}"
            )
            st.markdown(line)
            st.caption(citation["source"])


def fallback_text(details):
    """Pick the message to show when there is no answer to write."""
    if details["status"] == "empty":
        return EMPTY_MESSAGE
    if details["status"] == "too_long":
        return TOO_LONG_MESSAGE
    return build_fallback_text(details)


def make_reporter(status):
    """Build a function that shows each retrieval step."""
    def report(step):
        label = STEP_LABELS[step]
        status.update(label=label)
        status.write(label)
    return report


def build_timings(details, write_seconds, total_seconds):
    """List how long each step took, for the status panel."""
    search_seconds = (
        details.get("embed_seconds", 0)
        + details.get("search_seconds", 0)
    )
    return [
        f"Understanding the question: "
        f"{details.get('rewrite_seconds', 0):.1f} s",
        f"Searching the documents: {search_seconds:.1f} s",
        f"Weighing the evidence: "
        f"{details.get('rerank_seconds', 0):.1f} s",
        f"Writing the answer: {write_seconds:.1f} s",
        f"Total: {total_seconds:.1f} s",
    ]


def show_timings(status, timings):
    """Add the step timings inside a status panel."""
    if len(timings) == 0:
        return
    status.caption("  \n".join(timings))


def answer_in_chat(question, openai_client, collection):
    """Retrieve with status steps, stream the answer, show sources."""
    start = time.perf_counter()
    status = st.status(STEP_LABELS["rewrite"], expanded=False)
    try:
        question, results, details = prepare(
            question, openai_client, collection,
            st.session_state.previous_question,
            report=make_reporter(status),
        )
        if len(results) == 0:
            summary = "No matching documents"
            if details["status"] == "flagged":
                summary = "Declined"
            status.update(label=summary, state="complete")
            text = fallback_text(details)
            st.markdown(text)
            return text, [], details, summary, []

        status.update(label=STEP_LABELS["write"])
        status.write(STEP_LABELS["write"])
        write_start = time.perf_counter()
        search_text = details.get("search_text", question)
        mapping = {}
        pieces = stream_answer(search_text, results, openai_client)
        text = st.write_stream(
            renumber_stream(pieces, mapping, len(results))
        )
        write_seconds = time.perf_counter() - write_start
    except Exception as error:
        print(f"Seismo error: {error}")
        summary = "Hit a snag"
        status.update(label=summary, state="error")
        text = friendly_error(error)
        st.markdown(text)
        return text, [], {"status": "error"}, summary, []

    total_seconds = time.perf_counter() - start
    timings = build_timings(details, write_seconds, total_seconds)
    show_timings(status, timings)
    checked = details.get("rerank_pool", len(results))
    summary = (
        f"Read {checked} passages, kept {len(results)} "
        f"({total_seconds:.1f} s)"
    )
    status.update(label=summary, state="complete")
    citations = citations_from_mapping(mapping, results)
    show_sources(citations)
    return text, citations, details, summary, timings


def pick_avatar(role):
    """Return the icon for Seismo or the visitor."""
    if role == "assistant":
        return SEISMO_AVATAR
    return VISITOR_AVATAR


def show_history():
    """Show the greeting and every earlier message."""
    with st.chat_message("assistant", avatar=SEISMO_AVATAR):
        st.markdown(GREETING)
    for message in st.session_state.messages:
        role = message["role"]
        with st.chat_message(role, avatar=pick_avatar(role)):
            summary = message.get("summary", "")
            if summary != "":
                status = st.status(
                    summary, state="complete", expanded=False
                )
                show_timings(status, message.get("timings", []))
            st.markdown(message["content"])
            show_sources(message.get("citations", []))


def show_found_via():
    """Ask, once and optionally, how the visitor found Seismo."""
    if st.session_state.found_via != "":
        return
    picked = st.pills(
        "Quick question, totally optional: where did you find Seismo?",
        FOUND_VIA_OPTIONS,
        selection_mode="single",
        key="found_via_pick",
    )
    if picked is not None:
        st.session_state.found_via = picked
        st.rerun()


def pick_starter(question):
    """Remember which starter question was clicked."""
    st.session_state.starter = question


def show_starters():
    """Offer example questions while the chat is empty."""
    st.caption("Not sure where to start? Try one of these:")
    for question in STARTER_QUESTIONS:
        st.button(
            question, on_click=pick_starter, args=[question],
            key=f"starter-{question}",
        )


def pick_from_dropdown():
    """Ask the question picked in the dropdown, then reset it."""
    picked = st.session_state.more_questions
    if picked is not None:
        st.session_state.starter = picked
    st.session_state.more_questions = None


def show_more_questions():
    """Offer a dropdown of example questions not asked yet."""
    asked = []
    for message in st.session_state.messages:
        asked.append(message["content"])
    options = []
    for question in MORE_QUESTIONS:
        if question not in asked:
            options.append(question)
    if len(options) == 0:
        return
    st.selectbox(
        "More questions to try",
        options,
        index=None,
        placeholder="Or pick a suggested question",
        label_visibility="collapsed",
        key="more_questions",
        on_change=pick_from_dropdown,
    )


def clear_chat():
    """Start a fresh conversation."""
    st.session_state.messages = []
    st.session_state.previous_question = ""


def chat_tab(openai_client, collection):
    """The main chat: history, input and new answers."""
    top = st.container()
    conversation = st.container()

    limit_text = ""
    if session_limit_reached():
        limit_text = SESSION_LIMIT_MESSAGE
    elif daily_cap_reached():
        limit_text = DAILY_LIMIT_MESSAGE

    question = st.chat_input(
        "Ask why a Tephra metric moved",
        disabled=limit_text != "",
    )
    below = st.container()
    if st.session_state.starter != "":
        question = st.session_state.starter
        st.session_state.starter = ""

    with conversation:
        show_history()
        if limit_text != "":
            with st.chat_message("assistant", avatar=SEISMO_AVATAR):
                st.markdown(limit_text)
        elif question:
            ask_seismo(question, openai_client, collection)
        elif len(st.session_state.messages) == 0:
            show_found_via()
            show_starters()

    if len(st.session_state.messages) > 0:
        top.button("Clear chat", on_click=clear_chat)
        if limit_text == "":
            with below:
                show_more_questions()


def ask_seismo(question, openai_client, collection):
    """Show a new question and Seismo's answer, and save both."""
    count_question()
    st.session_state.messages.append(
        {"role": "user", "content": question}
    )
    with st.chat_message("user", avatar=VISITOR_AVATAR):
        st.markdown(question)

    with st.chat_message("assistant", avatar=SEISMO_AVATAR):
        text, citations, details, summary, timings = answer_in_chat(
            question, openai_client, collection
        )
    if details["status"] == "ok":
        st.session_state.previous_question = details["search_text"]

    st.session_state.messages.append({
        "role": "assistant",
        "content": text,
        "citations": citations,
        "summary": summary,
        "timings": timings,
    })


st.title("Seismo")
st.caption(
    "A portfolio project by Kaiya Sjoholm. Tephra is a fictional "
    "brand, and all of its data is made up."
)

start_session()
openai_client, collection = load_resources()

chat, how_it_works, analytics = st.tabs(
    ["Chat", "How It Works", "Analytics"]
)
with chat:
    chat_tab(openai_client, collection)
with how_it_works:
    st.write("Coming soon.")
with analytics:
    st.write("Coming soon.")