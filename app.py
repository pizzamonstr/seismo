"""Seismo: a metric investigation assistant for Tephra."""

import time
from datetime import date

import openai
import streamlit as st
from openai import OpenAI

from src.analytics_tab import show_analytics
from src.embed import get_api_key, get_collection
from src.generate import (
    EMPTY_MESSAGE,
    ERROR_MESSAGE,
    MAX_QUESTION_CHARS,
    TOO_LONG_MESSAGE,
    build_fallback_text,
    citations_from_mapping,
    prepare,
    renumber_stream,
    stream_answer,
)
from src.how_it_works import build_proof_line, show_how_it_works
from src.usage_log import log_found_via, log_question, new_visit_id

st.set_page_config(page_title="Seismo", layout="centered")

SEISMO_AVATAR = ":material/earthquake:"
VISITOR_AVATAR = ":material/person:"
GREETING = (
    "Hey, I'm Seismo. I help the Tephra team figure out why their "
    "numbers moved, like a jump in ad costs or a slow sales month. "
    "I dig through Tephra's 2025 reports, change logs and team "
    "notes, and I show you exactly where each answer came from. "
    "What would you like to look into?"
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
OPENAI_TIMEOUT_SECONDS = 45
OPENAI_RETRIES = 1
SPEND_LIMIT_CODES = [
    "insufficient_quota",
    "project_spend_limit_exceeded",
    "organization_spend_limit_exceeded",
]
INTERRUPTED_MESSAGE = (
    "That answer got cut off because a new question came in. Ask "
    "it again anytime."
)
SESSION_LIMIT_MESSAGE = (
    "That's 15 questions for this visit, which is my limit. Thanks "
    "for digging in with me, and you're welcome back another time."
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
    "resting": "I've used up my answers for this month, so I'm "
               "resting until next month. The How It Works tab "
               "still shows what I can do.",
    "startup": "I couldn't start up properly, so I can't answer "
               "questions right now. That's on my end, not yours. "
               "The How It Works tab still shows what I can do.",
}
STYLES = """
<style>
div[data-testid="stSelectbox"] input[role="combobox"] {
    padding-left: 1.5rem;
}
.st-key-chat_box {
    padding: 1rem !important;
}
div[data-testid="stChatMessage"] {
    padding: 1rem !important;
}
div[data-testid="stExpander"] details {
    border-color: #7aa7d6;
    border-radius: 0.6rem;
}
.st-key-chat_box,
div[class*="st-key-card-"] {
    border-color: #7aa7d6 !important;
}
div[data-testid="stChatInput"] > div {
    border-color: #7aa7d6;
}
div[class*="st-key-user-msg-"] div[data-testid="stChatMessage"] {
    background-color: rgba(122, 167, 214, 0.2) !important;
}
div[class*="st-key-starter-"] button,
div[class*="st-key-starter-"] button:hover {
    border-color: #7aa7d6;
    color: #ffffff;
}
div[class*="st-key-starter-"] button {
    height: auto;
    max-width: 100%;
    text-align: left;
}
div[class*="st-key-starter-"] button * {
    white-space: normal;
    overflow: visible;
    text-overflow: clip;
}
div[data-testid="stSelectbox"] div[role="group"] {
    border-color: #7aa7d6;
}
div[data-testid="stTab"] p {
    font-size: 1rem;
}
div[data-testid="stExpander"] blockquote {
    margin: 0;
}
.outcome-numbers {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));
    gap: 1rem;
}
.outcome-block {
    display: flex;
    flex-direction: column;
}
.outcome-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.9rem;
    margin-bottom: 0.25rem;
}
.outcome-marker {
    width: 0.6rem;
    height: 0.6rem;
    border-radius: 2px;
}
.outcome-stage {
    font-size: 0.8rem;
    color: #9aa4b2;
    margin-bottom: 0.5rem;
}
.outcome-number {
    margin-top: auto;
    font-size: 2rem;
    line-height: 1;
}
.outcome-share {
    font-size: 0.9rem;
    color: #9aa4b2;
    margin-left: 0.5rem;
}
</style>
"""
TAGLINE = (
    "A RAG chatbot that explains why a brand's marketing metrics "
    "moved, with citations."
)
PROFILE_LINKS = [
    ("Portfolio", "https://nullhypothesis.ca"),
    ("GitHub", "https://github.com/pizzamonstr/seismo"),
    ("LinkedIn", ""),
]
FOUND_VIA_OPTIONS = [
    "LinkedIn", "Portfolio Site", "UBC Class", "Somewhere Else",
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


def build_links():
    """Join the profile links that have an address."""
    links = []
    for name, url in PROFILE_LINKS:
        if url != "":
            links.append(f"[{name}]({url})")
    return " | ".join(links)


@st.cache_resource
def load_resources():
    """Open the OpenAI client and database once for every visitor."""
    openai_client = OpenAI(
        api_key=get_api_key(),
        timeout=OPENAI_TIMEOUT_SECONDS,
        max_retries=OPENAI_RETRIES,
    )
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
    if getattr(error, "code", "") in SPEND_LIMIT_CODES:
        return ERROR_MESSAGES["resting"]
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
    if "visit_id" not in st.session_state:
        st.session_state.visit_id = new_visit_id()


def describe_source(citation):
    """Build the location line and the score line for one source."""
    location = [f"File: {citation['source']}"]
    if citation.get("page", "") not in ["", None]:
        location.append(f"Page {citation['page']}")
    if citation.get("chunk_id", "") != "":
        location.append(f"Chunk ID: {citation['chunk_id']}")

    scores = []
    if "similarity" in citation:
        tier = citation.get("tier", "")
        scores.append(
            f"Similarity {citation['similarity']:.2f} ({tier})"
        )
    if citation.get("distance") is not None:
        scores.append(f"Cosine distance {citation['distance']:.2f}")
    if citation.get("rerank_score") is not None:
        scores.append(f"Re-rank score {citation['rerank_score']} of 3")

    lines = [" | ".join(location)]
    if len(scores) > 0:
        lines.append(" | ".join(scores))
    return "  \n".join(lines)


def quote_text(text):
    """Show retrieved text as a quote, line by line."""
    lines = []
    for line in text.split("\n"):
        lines.append("> " + line + "  ")
    return "\n".join(lines)


def show_sources(citations):
    """List the cited sources in a fold-out panel."""
    if len(citations) == 0:
        return
    with st.expander("View Sources"):
        for citation in citations:
            line = (
                f"**[{citation['number']}]** {citation['title']} "
                f"> {citation['section']}"
            )
            source = st.container(gap="small")
            source.markdown(line)
            source.caption(describe_source(citation))
            if citation.get("text", "") != "":
                source.markdown(quote_text(citation["text"]))


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
        status.caption(label)
    return report


def build_timings(details, write_seconds, total_seconds):
    """List how long each step took, for the status panel."""
    search_seconds = (
        details.get("embed_seconds", 0)
        + details.get("search_seconds", 0)
    )
    return [
        f"Rewrite: {details.get('rewrite_seconds', 0):.1f} s",
        f"Search: {search_seconds:.1f} s",
        f"Re-rank: {details.get('rerank_seconds', 0):.1f} s",
        f"Generate: {write_seconds:.1f} s",
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
            summary = "No Matching Documents"
            if details["status"] in ["flagged", "guarded"]:
                summary = "Declined"
            status.update(label=summary, state="complete")
            details["total_seconds"] = time.perf_counter() - start
            text = fallback_text(details)
            st.markdown(text)
            return text, [], details, summary, []

        status.update(label=STEP_LABELS["write"])
        status.caption(STEP_LABELS["write"])
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
        summary = "Hit a Snag"
        status.update(label=summary, state="error")
        text = friendly_error(error)
        st.markdown(text)
        return text, [], {"status": "error"}, summary, []

    total_seconds = time.perf_counter() - start
    details["write_seconds"] = write_seconds
    details["total_seconds"] = total_seconds
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


def mark_interrupted():
    """Add a note where an answer was cut off by a new question."""
    messages = st.session_state.messages
    if len(messages) > 0 and messages[-1]["role"] == "user":
        messages.append(
            {"role": "assistant", "content": INTERRUPTED_MESSAGE}
        )


def show_history(with_starters):
    """Show the greeting and every earlier message."""
    with st.chat_message("assistant", avatar=SEISMO_AVATAR):
        st.markdown(GREETING)
        if with_starters:
            show_starters()
    for index, message in enumerate(st.session_state.messages):
        role = message["role"]
        holder = st.container(key=f"{role}-msg-{index}")
        with holder.chat_message(role, avatar=pick_avatar(role)):
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
    st.caption(
        "Quick question, totally optional: where did you find Seismo?"
    )
    picked = st.pills(
        "Where did you find Seismo?",
        FOUND_VIA_OPTIONS,
        selection_mode="single",
        label_visibility="collapsed",
        key="found_via_pick",
    )
    if picked is not None:
        st.session_state.found_via = picked
        try:
            log_found_via(st.session_state.visit_id, picked)
        except Exception as error:
            print(f"Logging error: {error}")
        st.rerun()


def pick_starter(question):
    """Remember which starter question was clicked."""
    st.session_state.starter = question


def show_starters():
    """Offer example questions while the chat is empty."""
    st.caption("Not sure where to start? Try one of these:")
    row = st.container(horizontal=True, wrap=True)
    for question in STARTER_QUESTIONS:
        row.button(
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
    conversation = st.container(
        border=True, gap="small", key="chat_box"
    )
    top = conversation.container(
        horizontal=True, horizontal_alignment="right"
    )

    limit_text = ""
    if session_limit_reached():
        limit_text = SESSION_LIMIT_MESSAGE
    elif daily_cap_reached():
        limit_text = DAILY_LIMIT_MESSAGE

    question = st.chat_input(
        "Ask why a Tephra metric moved",
        max_chars=MAX_QUESTION_CHARS,
        disabled=limit_text != "",
    )
    below = st.container()
    if st.session_state.starter != "":
        question = st.session_state.starter
        st.session_state.starter = ""

    mark_interrupted()
    no_messages = len(st.session_state.messages) == 0
    with_starters = no_messages and not question and limit_text == ""

    with conversation:
        show_history(with_starters)
        if limit_text != "":
            with st.chat_message("assistant", avatar=SEISMO_AVATAR):
                st.markdown(limit_text)
        elif question:
            ask_seismo(question, openai_client, collection)

    if len(st.session_state.messages) > 0:
        top.button(
            "New Chat", icon=":material/refresh:", type="tertiary",
            on_click=clear_chat,
        )
        if limit_text == "":
            with below:
                show_more_questions()


def save_to_log(question, details, citations):
    """Log the question, without ever breaking the chat."""
    try:
        log_question(
            st.session_state.visit_id, question, details, citations
        )
    except Exception as error:
        print(f"Logging error: {error}")


def ask_seismo(question, openai_client, collection):
    """Show a new question and Seismo's answer, and save both."""
    count_question()
    st.session_state.messages.append(
        {"role": "user", "content": question}
    )
    index = len(st.session_state.messages) - 1
    holder = st.container(key=f"user-msg-{index}")
    with holder.chat_message("user", avatar=VISITOR_AVATAR):
        st.markdown(question)

    with st.chat_message("assistant", avatar=SEISMO_AVATAR):
        text, citations, details, summary, timings = answer_in_chat(
            question, openai_client, collection
        )
    if details["status"] == "ok":
        st.session_state.previous_question = details["search_text"]
    save_to_log(question, details, citations)

    st.session_state.messages.append({
        "role": "assistant",
        "content": text,
        "citations": citations,
        "summary": summary,
        "timings": timings,
    })


st.html(STYLES)
start_session()
show_found_via()
st.title("Seismo")
st.markdown(TAGLINE)
proof_line = build_proof_line()
if proof_line != "":
    st.markdown(proof_line)
st.caption(
    "A portfolio project by Kaiya Sjoholm: " + build_links()
    + "  \nTephra isn't a real brand. Its documents and data were "
    "created for this project."
)

try:
    openai_client, collection = load_resources()
except Exception as error:
    print(f"Startup error: {error}")
    openai_client, collection = None, None

chat, how_it_works, analytics = st.tabs([
    ":material/forum: Chat",
    ":material/account_tree: How It Works",
    ":material/monitoring: Analytics",
])
with chat:
    if openai_client is None:
        with st.chat_message("assistant", avatar=SEISMO_AVATAR):
            st.markdown(ERROR_MESSAGES["startup"])
    else:
        chat_tab(openai_client, collection)
with how_it_works:
    show_how_it_works()
with analytics:
    show_analytics(openai_client)