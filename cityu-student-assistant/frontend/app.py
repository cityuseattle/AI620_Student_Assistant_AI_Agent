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
REQUEST_TIMEOUT: float = 300.0  # seconds — LLM inference can be slow

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


def _get_update_mode() -> str:
    """Return the current prerequisite update mode ('approval' | 'auto')."""
    try:
        resp = httpx.get(f"{API_BASE_URL}/updates/mode", timeout=5.0)
        resp.raise_for_status()
        return resp.json().get("mode", "approval")
    except Exception:
        return "approval"


def _set_update_mode(mode: str) -> None:
    """Set the prerequisite update mode on the backend."""
    httpx.post(f"{API_BASE_URL}/updates/mode", json={"mode": mode}, timeout=5.0)


def _fetch_updates(status: Optional[str] = None) -> list[dict]:
    """Fetch change-log entries, optionally filtered by status."""
    try:
        params = {"status": status} if status else None
        resp = httpx.get(f"{API_BASE_URL}/updates", params=params, timeout=5.0)
        resp.raise_for_status()
        return resp.json().get("entries", [])
    except Exception:
        return []


def _act_on_update(change_id: str, action: str) -> None:
    """Approve or reject a pending change (action in {'approve', 'reject'})."""
    httpx.post(f"{API_BASE_URL}/updates/{change_id}/{action}", timeout=10.0)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def _render_sidebar() -> None:
    """Render the sidebar with status info and controls."""
    with st.sidebar:
        st.image(
            "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e4/City_University_of_Seattle_logo.png/320px-City_University_of_Seattle_logo.png",
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

        # --- Prerequisite self-update controls ---
        _render_updates_panel()

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


def _render_updates_panel() -> None:
    """Render the prerequisite self-update controls in the sidebar."""
    st.markdown("#### 🛠️ Prerequisite Updates")

    # Mode toggle (approval vs auto).
    current_mode = _get_update_mode()
    mode_labels = {
        "approval": "Approval required",
        "auto": "Auto-apply (no approval)",
    }
    options = ["approval", "auto"]
    selected = st.radio(
        "When the agent infers missing prerequisites:",
        options=options,
        index=options.index(current_mode) if current_mode in options else 0,
        format_func=lambda m: mode_labels[m],
        key="prereq_mode_radio",
    )
    if selected != current_mode:
        try:
            _set_update_mode(selected)
            st.success(f"Mode set to '{mode_labels[selected]}'.")
        except Exception as exc:
            st.error(f"Could not change mode: {exc}")

    # Pending approvals.
    pending = _fetch_updates(status="pending")
    st.markdown(f"**Pending approvals:** {len(pending)}")
    for entry in pending:
        with st.container(border=True):
            st.markdown(
                f"**{entry['course_code']}** ← {', '.join(entry['prereqs'])}"
            )
            if entry.get("reasoning"):
                st.caption(entry["reasoning"])
            if entry.get("unknown_prereqs"):
                st.caption(
                    "⚠️ Not in catalog: " + ", ".join(entry["unknown_prereqs"])
                )
            col_ok, col_no = st.columns(2)
            if col_ok.button("✅ Approve", key=f"appr_{entry['id']}", use_container_width=True):
                _act_on_update(entry["id"], "approve")
                st.rerun()
            if col_no.button("❌ Reject", key=f"rej_{entry['id']}", use_container_width=True):
                _act_on_update(entry["id"], "reject")
                st.rerun()

    # Recently applied / approved changes.
    applied = [
        e for e in _fetch_updates()
        if e.get("status") in ("applied", "approved")
    ][:5]
    if applied:
        with st.expander(f"📝 Recent changes ({len(applied)})"):
            for e in applied:
                st.markdown(
                    f"- **{e['course_code']}** ← {', '.join(e['prereqs'])} "
                    f"_({e['status']})_"
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

    # Call API with a loading spinner and timeout handling
    with st.chat_message("assistant"):
        with st.spinner("Agent is thinking…"):
            try:
                # Track time for timeout message
                import time
                start_time = time.time()

                result = _send_chat(
                    query=query,
                    session_id=st.session_state.session_id,
                )
                elapsed = time.time() - start_time

                answer = result.get("answer", "Sorry, I received an empty response.")
                sources = result.get("sources", [])

                # Show if it took a while
                if elapsed > 10:
                    answer = f"⏱️ *took {elapsed:.0f}s to analyze*\n\n{answer}"

            except RuntimeError as exc:
                error_msg = str(exc)
                if "Could not reach" in error_msg or "timeout" in error_msg.lower():
                    answer = (
                        "⚠️ **Backend is busy or not responding**\n\n"
                        "The API server is either:\n"
                        "- Processing a complex analysis (can take 2-5 minutes)\n"
                        "- Not running\n\n"
                        "**Check your API terminal** to see if it's still running.\n\n"
                        "Tip: Try a simpler question first, or increase the timeout in settings."
                    )
                else:
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

    # If the agent just proposed or applied a prerequisite update, rerun so the
    # sidebar panel (rendered before the query was handled) refreshes with the
    # new pending/applied entry.
    if "📝 Suggested" in answer or "✅ Added" in answer:
        st.rerun()


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
