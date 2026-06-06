"""
Chat and session-history endpoints.

``POST /chat``
    Accepts a student query and session_id, runs the agent, and returns the
    answer plus any source citations.

``GET /sessions/{session_id}/history``
    Returns the last 10 conversation turns for the given session.
"""

import logging

from fastapi import APIRouter, HTTPException, status

from agent.agent_executor import run_agent
from agent.memory import get_history, get_memory
from api.schemas import (
    ChatRequest,
    ChatResponse,
    HistoryMessage,
    SessionHistoryResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Send a message to the CityU Student Assistant",
    tags=["Chat"],
    status_code=status.HTTP_200_OK,
)
async def chat(request: ChatRequest) -> ChatResponse:
    """Process a student query and return the agent's answer.

    Parameters
    ----------
    request : ChatRequest
        ``{"query": str, "session_id": str}``

    Returns
    -------
    ChatResponse
        ``{"answer": str, "sources": list[str], "session_id": str}``

    Raises
    ------
    HTTPException (422)
        If the request body is invalid (handled automatically by FastAPI).
    HTTPException (500)
        If the agent encounters an unrecoverable error.
    """
    logger.info(
        "POST /chat | session=%s | query=%s",
        request.session_id,
        request.query[:80],
    )

    try:
        result = run_agent(query=request.query, session_id=request.session_id)
    except Exception as exc:
        logger.error(
            "Unhandled error in POST /chat | session=%s | error=%s",
            request.session_id,
            exc,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The agent encountered an unexpected error. Please try again.",
        ) from exc

    memory = get_memory(request.session_id)
    memory.save_context(
        inputs={"input": request.query},
        outputs={"output": result["answer"]},
    )

    # Add smart analysis suggestion
    answer = result["answer"]
    if "prerequisite" in request.query.lower() and "no prerequisite" in answer.lower():
        answer += "\n\n💡 **Want deeper analysis?** Ask me to \"analyze prerequisites for AI620\" and I'll examine course content and dependencies intelligently."

    return ChatResponse(
        answer=answer,
        sources=result["sources"],
        session_id=request.session_id,
    )


@router.get(
    "/sessions/{session_id}/history",
    response_model=SessionHistoryResponse,
    summary="Retrieve conversation history for a session",
    tags=["Chat"],
)
async def get_session_history(session_id: str) -> SessionHistoryResponse:
    """Return the last 10 conversation turns for *session_id*.

    Parameters
    ----------
    session_id : str
        The session identifier.

    Returns
    -------
    SessionHistoryResponse
        ``{"session_id": str, "messages": [{"role": str, "content": str}, ...]}``
    """
    logger.info("GET /sessions/%s/history", session_id)
    history = get_history(session_id=session_id, max_turns=10)
    messages = [HistoryMessage(role=m["role"], content=m["content"]) for m in history]
    return SessionHistoryResponse(session_id=session_id, messages=messages)
