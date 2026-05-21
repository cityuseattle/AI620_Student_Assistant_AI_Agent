"""
Integration tests for the FastAPI backend.

Uses FastAPI's TestClient and mocks the agent executor so no LLM or
external database is required during testing.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def client():
    """Return a FastAPI TestClient with the agent executor mocked out."""
    # Mock run_agent before importing the app so the LLM is never invoked
    mock_result = {
        "answer": "AI620 requires AI510 as a prerequisite.",
        "sources": ["course_catalog.pdf"],
    }

    with patch("api.routes.chat.run_agent", return_value=mock_result):
        with patch("agent.vector_store.get_vector_store"):  # skip ChromaDB init
            from api.main import app
            yield TestClient(app)


# ---------------------------------------------------------------------------
# /health Tests
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_returns_200(self, client: TestClient) -> None:
        """Health endpoint should return HTTP 200."""
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_response_has_status_ok(self, client: TestClient) -> None:
        """Response body should contain status='ok'."""
        response = client.get("/health")
        data = response.json()
        assert data["status"] == "ok"

    def test_health_response_has_llm_provider(self, client: TestClient) -> None:
        """Response body should include llm_provider field."""
        response = client.get("/health")
        data = response.json()
        assert "llm_provider" in data
        assert isinstance(data["llm_provider"], str)
        assert len(data["llm_provider"]) > 0

    def test_health_content_type_is_json(self, client: TestClient) -> None:
        """Response Content-Type should be application/json."""
        response = client.get("/health")
        assert "application/json" in response.headers["content-type"]


# ---------------------------------------------------------------------------
# /chat Tests
# ---------------------------------------------------------------------------


class TestChatEndpoint:
    """Tests for POST /chat."""

    def test_chat_returns_200(self, client: TestClient) -> None:
        """Valid chat request should return HTTP 200."""
        with patch(
            "api.routes.chat.run_agent",
            return_value={"answer": "Test answer.", "sources": []},
        ):
            response = client.post(
                "/chat",
                json={"query": "What is AI620?", "session_id": "test-session-1"},
            )
        assert response.status_code == 200

    def test_chat_response_has_answer(self, client: TestClient) -> None:
        """Response body should include a non-empty 'answer' field."""
        with patch(
            "api.routes.chat.run_agent",
            return_value={
                "answer": "AI620 requires AI510 as a prerequisite.",
                "sources": ["catalog.pdf"],
            },
        ):
            response = client.post(
                "/chat",
                json={"query": "Prerequisites for AI620?", "session_id": "test-session-2"},
            )
        data = response.json()
        assert "answer" in data
        assert len(data["answer"]) > 0

    def test_chat_response_includes_sources(self, client: TestClient) -> None:
        """Response body should include a 'sources' list."""
        with patch(
            "api.routes.chat.run_agent",
            return_value={
                "answer": "Here is the info.",
                "sources": ["doc1.pdf", "doc2.txt"],
            },
        ):
            response = client.post(
                "/chat",
                json={"query": "Tell me about MSAI.", "session_id": "test-session-3"},
            )
        data = response.json()
        assert "sources" in data
        assert isinstance(data["sources"], list)

    def test_chat_response_echoes_session_id(self, client: TestClient) -> None:
        """Response should echo back the session_id from the request."""
        session_id = "my-unique-session-xyz"
        with patch(
            "api.routes.chat.run_agent",
            return_value={"answer": "Test.", "sources": []},
        ):
            response = client.post(
                "/chat",
                json={"query": "Hello", "session_id": session_id},
            )
        data = response.json()
        assert data["session_id"] == session_id

    def test_chat_missing_query_returns_422(self, client: TestClient) -> None:
        """Request without 'query' field should return HTTP 422."""
        response = client.post(
            "/chat",
            json={"session_id": "test-session"},
        )
        assert response.status_code == 422

    def test_chat_missing_session_id_returns_422(self, client: TestClient) -> None:
        """Request without 'session_id' field should return HTTP 422."""
        response = client.post(
            "/chat",
            json={"query": "What is AI620?"},
        )
        assert response.status_code == 422

    def test_chat_empty_query_returns_422(self, client: TestClient) -> None:
        """Empty query string should fail Pydantic min_length validation."""
        response = client.post(
            "/chat",
            json={"query": "", "session_id": "test-session"},
        )
        assert response.status_code == 422

    def test_chat_agent_error_returns_500(self, client: TestClient) -> None:
        """An exception from run_agent should result in HTTP 500."""
        with patch(
            "api.routes.chat.run_agent",
            side_effect=Exception("LLM crashed"),
        ):
            response = client.post(
                "/chat",
                json={"query": "What courses does CityU offer?", "session_id": "err-session"},
            )
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# /sessions/{session_id}/history Tests
# ---------------------------------------------------------------------------


class TestSessionHistoryEndpoint:
    """Tests for GET /sessions/{session_id}/history."""

    def test_history_returns_200(self, client: TestClient) -> None:
        """History endpoint should return HTTP 200."""
        response = client.get("/sessions/new-empty-session/history")
        assert response.status_code == 200

    def test_history_empty_for_new_session(self, client: TestClient) -> None:
        """A brand-new session should have no messages."""
        response = client.get("/sessions/brand-new-session-abc/history")
        data = response.json()
        assert data["messages"] == []

    def test_history_echoes_session_id(self, client: TestClient) -> None:
        """Response should echo back the session_id path parameter."""
        session_id = "history-test-session"
        response = client.get(f"/sessions/{session_id}/history")
        data = response.json()
        assert data["session_id"] == session_id

    def test_history_after_chat(self, client: TestClient) -> None:
        """Session history should reflect messages after a chat call."""
        session_id = "history-after-chat-session"

        with patch(
            "api.routes.chat.run_agent",
            return_value={"answer": "AI620 info here.", "sources": []},
        ):
            client.post(
                "/chat",
                json={"query": "Tell me about AI620.", "session_id": session_id},
            )

        response = client.get(f"/sessions/{session_id}/history")
        data = response.json()

        # Should have at least the human message and AI response
        assert len(data["messages"]) >= 2
        roles = {m["role"] for m in data["messages"]}
        assert "human" in roles
        assert "ai" in roles


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------


class TestRootEndpoint:
    """Tests for GET /."""

    def test_root_returns_200(self, client: TestClient) -> None:
        response = client.get("/")
        assert response.status_code == 200

    def test_root_response_has_message(self, client: TestClient) -> None:
        response = client.get("/")
        data = response.json()
        assert "message" in data
