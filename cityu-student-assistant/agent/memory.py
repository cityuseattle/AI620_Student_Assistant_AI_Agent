"""
Session memory management for the CityU Student Assistant.

Each chat session is keyed by a ``session_id`` string.  The agent stores the
last *k* conversation turns in a ``ConversationBufferWindowMemory`` instance
that is held in an in-process dict.

Note
----
Memory is not persisted across server restarts.  For production persistence,
replace the in-memory dict with a Redis-backed implementation.
"""

import logging
from typing import Dict

try:
    from langchain.memory import ConversationBufferWindowMemory
except Exception:
    ConversationBufferWindowMemory = None

if ConversationBufferWindowMemory is None:
    class ConversationBufferWindowMemory:
        def __init__(self, *args, **kwargs):
            self.chat_memory = type("ChatMemory", (), {"messages": []})()

        def save_context(self, inputs, outputs):
            # mimic LangChain behavior
            self.chat_memory.messages.append(
                type("HumanMessage", (), {"content": inputs.get("input", "")})()
            )
            self.chat_memory.messages.append(
                type("AIMessage", (), {"content": outputs.get("output", "")})()
            )

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level session store
# ---------------------------------------------------------------------------

_sessions: Dict[str, ConversationBufferWindowMemory] = {}

WINDOW_K = 5  # number of conversation turns to retain


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_memory(session_id: str) -> ConversationBufferWindowMemory:
    """Return the memory instance for *session_id*, creating it if absent.

    Parameters
    ----------
    session_id : str
        A unique identifier for the conversation session (e.g. a UUID).

    Returns
    -------
    ConversationBufferWindowMemory
        The memory object holding the last ``WINDOW_K`` exchanges.
    """
    if session_id not in _sessions:
        logger.info("Creating new memory for session: %s", session_id)
        _sessions[session_id] = ConversationBufferWindowMemory(
            k=WINDOW_K,
            memory_key="chat_history",
            return_messages=True,
            input_key="input",
            output_key="output",
        )
    return _sessions[session_id]


def clear_memory(session_id: str) -> None:
    """Delete the memory associated with *session_id*.

    Parameters
    ----------
    session_id : str
        The session to clear.  A no-op if the session does not exist.
    """
    if session_id in _sessions:
        logger.info("Clearing memory for session: %s", session_id)
        del _sessions[session_id]


def get_history(session_id: str, max_turns: int = 10) -> list[dict]:
    """Return the recent conversation history for a session as a list of dicts.

    Parameters
    ----------
    session_id : str
        The target session.
    max_turns : int
        Maximum number of turns to return (default 10).

    Returns
    -------
    list[dict]
        A list of ``{"role": "human"|"ai", "content": str}`` dicts, oldest
        first, capped at *max_turns*.
    """
    if session_id not in _sessions:
        return []

    messages = _sessions[session_id].chat_memory.messages
    history = []
    for msg in messages:
        role = "human" if msg.__class__.__name__ == "HumanMessage" else "ai"
        history.append({"role": role, "content": msg.content})

    return history[-max_turns * 2 :]  # each turn = 2 messages
