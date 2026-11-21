"""Seismo: a metric investigation assistant for Tephra."""

import streamlit as st
from openai import OpenAI

from src.embed import get_api_key, get_collection
from src.generate import (
    EMPTY_MESSAGE,
    ERROR_MESSAGE,
    TOO_LONG_MESSAGE,
    build_fallback_text,
    find_citations,
    prepare,
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
STARTER_QUESTIONS = [
    "Why did Meta ROAS jump to 5.4 in September 2025?",
    "Did the GA4 consent mode change in May 2025 cause lost sales?",
    "Why was October 2025 revenue down 18% year over year?",
    "What tracking or measurement problems did Tephra have in 2025?",
]


@st.cache_resource
def load_resources():
    """Open the OpenAI client and database once for every visitor."""
    openai_client = OpenAI(api_key=get_api_key())
    collection = get_collection()
    return openai_client, collection


def start_session():
    """Set up this visitor's chat history."""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "previous_question" not in st.session_state:
        st.session_state.previous_question = ""
    if "starter" not in st.session_state:
        st.session_state.starter = ""


def show_sources(citations):
    """List the cited sources in a fold-out panel."""
    if len(citations) == 0:
        return
    with st.expander("View sources"):
        for citation in citations:
            line = (
                f"**[S{citation['number']}]** {citation['title']} "
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


def answer_in_chat(question, openai_client, collection):
    """Retrieve with status steps, stream the answer, show sources."""
    status = st.status(STEP_LABELS["rewrite"], expanded=False)
    question, results, details = prepare(
        question, openai_client, collection,
        st.session_state.previous_question,
        report=make_reporter(status),
    )

    if len(results) == 0:
        status.update(label="No matching documents", state="complete")
        text = fallback_text(details)
        st.markdown(text)
        return text, [], details

    status.update(label=STEP_LABELS["write"])
    status.write(STEP_LABELS["write"])
    search_text = details.get("search_text", question)
    text = st.write_stream(
        stream_answer(search_text, results, openai_client)
    )
    checked = details.get("rerank_pool", len(results))
    summary = f"Read {checked} passages, kept {len(results)}"
    status.update(label=summary, state="complete")

    citations = find_citations(text, results)
    show_sources(citations)
    return text, citations, details


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
            st.markdown(message["content"])
            show_sources(message.get("citations", []))


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


def clear_chat():
    """Start a fresh conversation."""
    st.session_state.messages = []
    st.session_state.previous_question = ""


def chat_tab(openai_client, collection):
    """The main chat: history, input and new answers."""
    top = st.container()
    conversation = st.container()
    question = st.chat_input("Ask why a Tephra metric moved")
    if st.session_state.starter != "":
        question = st.session_state.starter
        st.session_state.starter = ""

    with conversation:
        show_history()
        if question:
            ask_seismo(question, openai_client, collection)
        elif len(st.session_state.messages) == 0:
            show_starters()

    if len(st.session_state.messages) > 0:
        top.button("Clear chat", on_click=clear_chat)


def ask_seismo(question, openai_client, collection):
    """Show a new question and Seismo's answer, and save both."""
    st.session_state.messages.append(
        {"role": "user", "content": question}
    )
    with st.chat_message("user", avatar=VISITOR_AVATAR):
        st.markdown(question)

    with st.chat_message("assistant", avatar=SEISMO_AVATAR):
        try:
            text, citations, details = answer_in_chat(
                question, openai_client, collection
            )
            if details["status"] == "ok":
                st.session_state.previous_question = (
                    details["search_text"]
                )
        except Exception:
            text = ERROR_MESSAGE
            citations = []
            st.markdown(text)

    st.session_state.messages.append(
        {"role": "assistant", "content": text, "citations": citations}
    )


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