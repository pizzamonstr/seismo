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


def answer_in_chat(question, openai_client, collection):
    """Retrieve, stream the answer and show its sources."""
    with st.spinner("Searching Tephra's documents..."):
        question, results, details = prepare(
            question, openai_client, collection,
            st.session_state.previous_question,
        )

    if len(results) == 0:
        text = fallback_text(details)
        st.markdown(text)
        return text, [], details

    search_text = details.get("search_text", question)
    text = st.write_stream(
        stream_answer(search_text, results, openai_client)
    )
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


def clear_chat():
    """Start a fresh conversation."""
    st.session_state.messages = []
    st.session_state.previous_question = ""


def chat_tab(openai_client, collection):
    """The main chat: history, input and new answers."""
    top = st.container()
    conversation = st.container()
    question = st.chat_input("Ask why a Tephra metric moved")

    with conversation:
        show_history()
        if question:
            ask_seismo(question, openai_client, collection)

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