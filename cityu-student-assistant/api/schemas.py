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


# ---------------------------------------------------------------------------
# Prerequisite updates
# ---------------------------------------------------------------------------


class PrereqUpdateEntry(BaseModel):
    """A single prerequisite-change record from the audit log."""

    id: str
    course_code: str
    prereqs: list[str]
    status: str = Field(..., description="pending | applied | approved | rejected")
    mode: str = Field(..., description="approval | auto")
    reasoning: str = ""
    source: str = "agent"
    unknown_prereqs: list[str] = Field(default_factory=list)
    created_at: str = ""


class PrereqUpdateList(BaseModel):
    """A list of prerequisite-change records."""

    mode: str
    entries: list[PrereqUpdateEntry]


class ModeRequest(BaseModel):
    """Body for setting the prerequisite update mode."""

    mode: str = Field(..., description="'approval' or 'auto'.", examples=["approval"])


class ModeResponse(BaseModel):
    """Current prerequisite update mode."""

    mode: str


class ActionResponse(BaseModel):
    """Result of approving/rejecting a change."""

    status: str
    message: str
    id: str | None = None
