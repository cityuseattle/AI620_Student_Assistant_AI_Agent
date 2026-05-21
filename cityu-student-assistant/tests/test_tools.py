"""
Tests for the three LangChain tools: rag_search, course_lookup, faq_search.

All tests use temporary SQLite databases and mocked ChromaDB retrievers so
no external services are required.
"""

import sqlite3
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    """Create a temporary SQLite database with the CityU schema and test data."""
    schema_path = PROJECT_ROOT / "db" / "schema.sql"
    db_path = tmp_path / "test_cityu.db"

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    schema_sql = schema_path.read_text(encoding="utf-8")
    conn.executescript(schema_sql)

    # Insert test courses
    conn.execute(
        "INSERT INTO courses (code, title, credits, description, semester, professor) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("AI510", "Foundations of AI", 3, "Intro to AI concepts.", "Fall 2025", "Dr. Test"),
    )
    conn.execute(
        "INSERT INTO courses (code, title, credits, description, semester, professor) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("AI620", "Machine Learning for AI", 3, "ML concepts and practice.", "Fall 2025", "Dr. Test"),
    )
    conn.execute(
        "INSERT INTO prerequisites (course_code, prereq_code) VALUES (?, ?)",
        ("AI620", "AI510"),
    )
    conn.execute(
        "INSERT INTO degree_requirements (program, requirement_type, course_code, notes) "
        "VALUES (?, ?, ?, ?)",
        ("MSAI", "Core", "AI620", "Required for all MSAI students."),
    )
    conn.execute(
        "INSERT INTO faqs (question, answer, category) VALUES (?, ?, ?)",
        (
            "How do I register for classes?",
            "Log in to the student portal at my.cityu.edu to register.",
            "Registration",
        ),
    )
    conn.execute(
        "INSERT INTO faqs (question, answer, category) VALUES (?, ?, ?)",
        (
            "What is the tuition cost?",
            "Tuition is available on the CityU website.",
            "Financial Aid",
        ),
    )
    conn.commit()
    conn.close()

    return db_path


# ---------------------------------------------------------------------------
# RAG Search Tool Tests
# ---------------------------------------------------------------------------


class TestRagSearchTool:
    """Tests for the rag_search_tool."""

    def test_returns_string(self) -> None:
        """rag_search_tool should always return a string."""
        from agent.tools import _rag_search

        mock_doc = MagicMock()
        mock_doc.page_content = "AI620 is a core machine learning course."
        mock_doc.metadata = {"source": "catalog.pdf", "chunk_index": 0}

        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [mock_doc]

        with patch("agent.tools.get_retriever", return_value=mock_retriever):
            result = _rag_search("What is AI620?")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_includes_source_citation(self) -> None:
        """RAG result should include the source document filename."""
        from agent.tools import _rag_search

        mock_doc = MagicMock()
        mock_doc.page_content = "AI620 covers supervised learning."
        mock_doc.metadata = {"source": "course_catalog.pdf", "chunk_index": 2}

        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = [mock_doc]

        with patch("agent.tools.get_retriever", return_value=mock_retriever):
            result = _rag_search("machine learning course")

        assert "course_catalog.pdf" in result

    def test_empty_results_returns_no_results_message(self) -> None:
        """When retriever returns no docs, return a helpful message."""
        from agent.tools import _rag_search

        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = []

        with patch("agent.tools.get_retriever", return_value=mock_retriever):
            result = _rag_search("xyzzy nonexistent query")

        assert "No relevant documents" in result

    def test_retriever_exception_returns_error_message(self) -> None:
        """Exceptions in the retriever should return a graceful error string."""
        from agent.tools import _rag_search

        mock_retriever = MagicMock()
        mock_retriever.invoke.side_effect = RuntimeError("ChromaDB unavailable")

        with patch("agent.tools.get_retriever", return_value=mock_retriever):
            result = _rag_search("any query")

        assert "unable to search" in result.lower()

    def test_multiple_docs_all_included(self) -> None:
        """All returned documents should be included in the output."""
        from agent.tools import _rag_search

        docs = [
            MagicMock(
                page_content=f"Chunk {i} content.",
                metadata={"source": f"file{i}.txt", "chunk_index": i},
            )
            for i in range(3)
        ]
        mock_retriever = MagicMock()
        mock_retriever.invoke.return_value = docs

        with patch("agent.tools.get_retriever", return_value=mock_retriever):
            result = _rag_search("course info")

        assert "Result 1" in result
        assert "Result 2" in result
        assert "Result 3" in result


# ---------------------------------------------------------------------------
# Course Lookup Tool Tests
# ---------------------------------------------------------------------------


class TestCourseLookupTool:
    """Tests for the course_lookup_tool."""

    def test_existing_course_returns_details(self, tmp_db: Path) -> None:
        """A known course code should return full course details."""
        from agent.tools import _course_lookup

        with patch("agent.tools.DB_PATH", tmp_db):
            result = _course_lookup("AI620")

        assert "AI620" in result
        assert "Machine Learning for AI" in result
        assert "3" in result  # credits

    def test_prerequisite_listed(self, tmp_db: Path) -> None:
        """The prerequisite AI510 should appear in AI620's details."""
        from agent.tools import _course_lookup

        with patch("agent.tools.DB_PATH", tmp_db):
            result = _course_lookup("AI620")

        assert "AI510" in result

    def test_degree_program_listed(self, tmp_db: Path) -> None:
        """Degree program info should be included when available."""
        from agent.tools import _course_lookup

        with patch("agent.tools.DB_PATH", tmp_db):
            result = _course_lookup("AI620")

        assert "MSAI" in result

    def test_course_not_found(self, tmp_db: Path) -> None:
        """An unknown course code should return 'Course not found'."""
        from agent.tools import _course_lookup

        with patch("agent.tools.DB_PATH", tmp_db):
            result = _course_lookup("ZZZZ999")

        assert "not found" in result.lower()

    def test_case_insensitive_lookup(self, tmp_db: Path) -> None:
        """Course lookup should be case-insensitive."""
        from agent.tools import _course_lookup

        with patch("agent.tools.DB_PATH", tmp_db):
            result = _course_lookup("ai620")

        assert "AI620" in result
        assert "not found" not in result.lower()

    def test_db_not_found_returns_helpful_message(self, tmp_path: Path) -> None:
        """A missing database should return a helpful error message."""
        from agent.tools import _course_lookup

        missing_db = tmp_path / "nonexistent.db"
        with patch("agent.tools.DB_PATH", missing_db):
            result = _course_lookup("AI620")

        assert "seed_database" in result.lower() or "not found" in result.lower()


# ---------------------------------------------------------------------------
# FAQ Tool Tests
# ---------------------------------------------------------------------------


class TestFaqTool:
    """Tests for the faq_tool."""

    def test_matching_keyword_returns_answer(self, tmp_db: Path) -> None:
        """A keyword matching a FAQ question should return the answer."""
        from agent.tools import _faq_search

        with patch("agent.tools.DB_PATH", tmp_db):
            result = _faq_search("register for classes")

        assert "student portal" in result.lower()

    def test_no_match_returns_no_faq_message(self, tmp_db: Path) -> None:
        """A query with no matching FAQs should return a no-FAQ message."""
        from agent.tools import _faq_search

        with patch("agent.tools.DB_PATH", tmp_db):
            result = _faq_search("xyzzy completely unknown topic")

        assert "No FAQ found" in result

    def test_returns_category_in_response(self, tmp_db: Path) -> None:
        """The FAQ response should include the category."""
        from agent.tools import _faq_search

        with patch("agent.tools.DB_PATH", tmp_db):
            result = _faq_search("register")

        assert "Registration" in result

    def test_faq_response_includes_question_and_answer(self, tmp_db: Path) -> None:
        """Response should include both Q and A fields."""
        from agent.tools import _faq_search

        with patch("agent.tools.DB_PATH", tmp_db):
            result = _faq_search("tuition cost")

        assert "Q:" in result
        assert "A:" in result

    def test_db_not_found_returns_helpful_message(self, tmp_path: Path) -> None:
        """A missing database should return a helpful error message."""
        from agent.tools import _faq_search

        missing_db = tmp_path / "nonexistent.db"
        with patch("agent.tools.DB_PATH", missing_db):
            result = _faq_search("registration")

        assert "seed_database" in result.lower() or "not found" in result.lower()


# ---------------------------------------------------------------------------
# Tool metadata tests
# ---------------------------------------------------------------------------


class TestToolMetadata:
    """Ensure all tools have the required LangChain metadata."""

    def test_all_tools_have_names(self) -> None:
        from agent.tools import ALL_TOOLS

        for tool in ALL_TOOLS:
            assert tool.name, f"Tool {tool} has no name."

    def test_all_tools_have_descriptions(self) -> None:
        from agent.tools import ALL_TOOLS

        for tool in ALL_TOOLS:
            assert tool.description and len(tool.description) > 20, (
                f"Tool '{tool.name}' has a missing or too-short description."
            )

    def test_all_tools_are_callable(self) -> None:
        from agent.tools import ALL_TOOLS

        for tool in ALL_TOOLS:
            assert callable(tool.func), f"Tool '{tool.name}' func is not callable."

    def test_expected_tool_names_present(self) -> None:
        from agent.tools import ALL_TOOLS

        names = {t.name for t in ALL_TOOLS}
        assert "rag_search" in names
        assert "course_lookup" in names
        assert "faq_search" in names
