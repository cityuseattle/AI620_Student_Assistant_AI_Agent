"""
Pydantic request and response models for the CityU Student Assistant API.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    """Body for ``POST /chat``."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The student's question.",
        examples=["What are the prerequisites for AI620?"],
    )
    session_id: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="Unique session identifier (UUID recommended).",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )


class ChatResponse(BaseModel):
    """Response from ``POST /chat``."""

    answer: str = Field(..., description="The agent's answer.")
    sources: list[str] = Field(
        default_factory=list,
        description="Source document filenames cited by the RAG tool.",
    )
    session_id: str = Field(..., description="Echo of the request session ID.")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Response from ``GET /health``."""

    status: str = Field(default="ok", description="Service health status.")
    llm_provider: str = Field(..., description="Active LLM provider name.")


# ---------------------------------------------------------------------------
# Session history
# ---------------------------------------------------------------------------


class HistoryMessage(BaseModel):
    """A single message in the conversation history."""

    role: str = Field(..., description="'human' or 'ai'.")
    content: str = Field(..., description="Message text.")


class SessionHistoryResponse(BaseModel):
    """Response from ``GET /sessions/{session_id}/history``."""

    session_id: str
    messages: list[HistoryMessage]


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Generic error response body."""

    detail: str
