"""
CityU Student Assistant — Streamlit chat frontend.

Run with:
    streamlit run frontend/app.py

Environment variables (optional):
    STREAMLIT_API_URL — base URL of the FastAPI backend (default: http://localhost:8000)
"""

import os
import uuid
from typing import Optional

import httpx
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE_URL: str = os.getenv("STREAMLIT_API_URL", "http://localhost:8000").rstrip("/")
REQUEST_TIMEOUT: float = 120.0  # seconds — LLM inference can be slow

SAMPLE_QUESTIONS: list[str] = [
    "What are the prerequisites for AI620?",
    "What courses are required for the MSAI program?",
    "How do I apply for financial aid at CityU?",
]

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="CityU Student Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------


def _init_session_state() -> None:
    """Initialise Streamlit session state keys on first load."""
    if "session_id" not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "messages" not in st.session_state:
        # Each message: {"role": "user"|"assistant", "content": str, "sources": list[str]}
        st.session_state.messages = []
    if "pending_question" not in st.session_state:
        st.session_state.pending_question = None


_init_session_state()


# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def _fetch_health() -> dict:
    """Call GET /health and return the JSON payload, or a fallback dict."""
    try:
        resp = httpx.get(f"{API_BASE_URL}/health", timeout=5.0)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return {"status": "unavailable", "llm_provider": "unknown"}


def _send_chat(query: str, session_id: str) -> dict:
    """Post a chat message and return ``{"answer": str, "sources": list[str]}``.

    Parameters
    ----------
    query : str
        The student's question.
    session_id : str
        Current session UUID.

    Returns
    -------
    dict
        Parsed JSON response body.

    Raises
    ------
    RuntimeError
        If the API returns a non-2xx status or is unreachable.
    """
    try:
        resp = httpx.post(
            f"{API_BASE_URL}/chat",
            json={"query": query, "session_id": session_id},
            timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        raise RuntimeError(
            f"API error {exc.response.status_code}: {exc.response.text}"
        ) from exc
    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Could not reach the backend at {API_BASE_URL}. "
            "Make sure the API server is running."
        ) from exc


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def _render_sidebar() -> None:
    """Render the sidebar with status info and controls."""
    with st.sidebar:
        st.image(
            "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/City_University_of_Seattle_logo.png/320px-City_University_of_Seattle_logo.png",
            use_column_width=True,
        )
        st.title("CityU Student Assistant")
        st.markdown("---")

        # --- Service status ---
        health = _fetch_health()
        status_color = "🟢" if health.get("status") == "ok" else "🔴"
        st.markdown(f"**Status:** {status_color} {health.get('status', 'unknown').capitalize()}")
        st.markdown(f"**LLM Provider:** `{health.get('llm_provider', 'unknown')}`")
        st.markdown(f"**Session ID:**")
        st.code(st.session_state.session_id, language=None)

        st.markdown("---")

        # --- Sample questions ---
        st.markdown("#### 💡 Sample Questions")
        for question in SAMPLE_QUESTIONS:
            if st.button(question, key=f"sample_{hash(question)}", use_container_width=True):
                st.session_state.pending_question = question

        st.markdown("---")

        # --- Clear chat ---
        if st.button("🗑️ Clear Chat", use_container_width=True, type="secondary"):
            st.session_state.messages = []
            st.session_state.session_id = str(uuid.uuid4())
            st.session_state.pending_question = None
            st.rerun()

        st.markdown("---")
        st.markdown(
            "<small>Powered by LangChain · ChromaDB · FastAPI</small>",
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# Chat rendering helpers
# ---------------------------------------------------------------------------


def _render_message(role: str, content: str, sources: Optional[list[str]] = None) -> None:
    """Render a single chat message bubble.

    Parameters
    ----------
    role : str
        ``"user"`` or ``"assistant"``.
    content : str
        The message text.
    sources : list[str], optional
        Source document names to display in an expander below the message.
    """
    with st.chat_message(role):
        st.markdown(content)
        if sources and role == "assistant":
            with st.expander("📚 Sources"):
                for src in sources:
                    st.markdown(f"- `{src}`")


def _render_history() -> None:
    """Render all messages stored in session state."""
    for msg in st.session_state.messages:
        _render_message(
            role=msg["role"],
            content=msg["content"],
            sources=msg.get("sources"),
        )


# ---------------------------------------------------------------------------
# Core interaction logic
# ---------------------------------------------------------------------------


def _handle_query(query: str) -> None:
    """Process a user query: update state, call API, and render response.

    Parameters
    ----------
    query : str
        The student's question (already validated as non-empty).
    """
    # Add user message to history and render it immediately
    st.session_state.messages.append({"role": "user", "content": query})
    _render_message("user", query)

    # Call API with a loading spinner
    with st.chat_message("assistant"):
        with st.spinner("Agent is thinking…"):
            try:
                result = _send_chat(
                    query=query,
                    session_id=st.session_state.session_id,
                )
                answer = result.get("answer", "Sorry, I received an empty response.")
                sources = result.get("sources", [])
            except RuntimeError as exc:
                answer = f"⚠️ **Error:** {exc}"
                sources = []

        st.markdown(answer)
        if sources:
            with st.expander("📚 Sources"):
                for src in sources:
                    st.markdown(f"- `{src}`")

    # Persist to session state
    st.session_state.messages.append(
        {"role": "assistant", "content": answer, "sources": sources}
    )


# ---------------------------------------------------------------------------
# Main layout
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point for the Streamlit application."""
    _render_sidebar()

    # Page header
    st.markdown("## 🎓 CityU Student Assistant")
    st.markdown(
        "Ask me anything about City University of Seattle — "
        "courses, prerequisites, degree requirements, or campus policies."
    )
    st.markdown("---")

    # Render existing conversation history
    _render_history()

    # Handle a sample-question button click (set in sidebar)
    if st.session_state.pending_question:
        pending = st.session_state.pending_question
        st.session_state.pending_question = None
        _handle_query(pending)

    # Chat input at the bottom of the page
    if user_input := st.chat_input("Type your question here…"):
        _handle_query(user_input)


if __name__ == "__main__":
    main()
