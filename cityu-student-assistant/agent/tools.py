"""
LangChain tools for the CityU Student Assistant.

Three tools are exposed:

1. ``rag_search_tool``   — semantic search over CityU documents in ChromaDB.
2. ``course_lookup_tool`` — structured query against the SQLite courses table.
3. ``faq_tool``          — keyword-based FAQ search against the SQLite faqs table.
"""

import logging
import sqlite3
from pathlib import Path
from typing import Optional

#from langchain.tools import Tool  # type: ignore
from langchain_core.tools import Tool

from agent.vector_store import get_retriever

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "cityu.db"


# ---------------------------------------------------------------------------
# Helper: SQLite connection
# ---------------------------------------------------------------------------


def _get_db_connection() -> sqlite3.Connection:
    """Open a SQLite connection to the CityU database.

    Returns
    -------
    sqlite3.Connection
        A connection with ``row_factory`` set to ``sqlite3.Row`` for
        dict-like row access.

    Raises
    ------
    FileNotFoundError
        If the database file does not exist (hint: run seed_database.py).
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. "
            "Please run: python scripts/seed_database.py"
        )
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Tool 1: RAG Search
# ---------------------------------------------------------------------------


def _rag_search(query: str) -> str:
    """Retrieve relevant CityU document chunks from ChromaDB.

    Parameters
    ----------
    query : str
        The student's natural-language question.

    Returns
    -------
    str
        Formatted context passages with source citations, or a "no results"
        message if the collection is empty.
    """
    logger.debug("RAG search query: %s", query)
    try:
        retriever = get_retriever(k=4)
        docs = retriever.invoke(query)
    except Exception as exc:
        logger.error("RAG retriever error: %s", exc)
        return "I was unable to search the document store right now. Please try again."

    if not docs:
        return (
            "No relevant documents were found in the CityU knowledge base for "
            f"the query: '{query}'."
        )

    parts: list[str] = []
    for idx, doc in enumerate(docs, start=1):
        source = doc.metadata.get("source", "unknown source")
        chunk = doc.metadata.get("chunk_index", "")
        citation = f"[{source}" + (f", chunk {chunk}]" if chunk != "" else "]")
        parts.append(f"--- Result {idx} {citation} ---\n{doc.page_content.strip()}")

    logger.debug("RAG returned %d documents.", len(docs))
    return "\n\n".join(parts)


rag_search_tool = Tool(
    name="rag_search",
    description=(
        "Search the CityU internal knowledge base (course catalogs, syllabi, "
        "academic policies, and student handbooks) for information about City "
        "University of Seattle programs, courses, policies, and procedures. "
        "Use this tool when the student asks a general question about CityU "
        "that is not a specific course code lookup or FAQ. "
        "Input: a natural-language search query string."
    ),
    func=_rag_search,
)


# ---------------------------------------------------------------------------
# Tool 2: Course Lookup
# ---------------------------------------------------------------------------


def _course_lookup(course_code: str) -> str:
    """Look up a specific course by code in the SQLite database.

    Parameters
    ----------
    course_code : str
        The course code to look up, e.g. ``"AI620"`` or ``"ai620"``
        (case-insensitive).

    Returns
    -------
    str
        A formatted string with course details and prerequisites, or
        ``"Course not found."`` if the code is not in the database.
    """
    code = course_code.strip().upper()
    logger.debug("Course lookup: %s", code)

    try:
        conn = _get_db_connection()
    except FileNotFoundError as exc:
        return str(exc)

    try:
        cursor = conn.cursor()

        # Fetch course record
        cursor.execute(
            "SELECT code, title, credits, description, semester, professor "
            "FROM courses WHERE UPPER(code) = ?",
            (code,),
        )
        row = cursor.fetchone()

        if row is None:
            return f"Course not found. No course with code '{code}' exists in the database."

        # Fetch prerequisites
        cursor.execute(
            "SELECT prereq_code FROM prerequisites WHERE course_code = ?",
            (row["code"],),
        )
        prereqs = [r["prereq_code"] for r in cursor.fetchall()]

        # Fetch degree programs that require this course
        cursor.execute(
            "SELECT program, requirement_type, notes "
            "FROM degree_requirements WHERE course_code = ?",
            (row["code"],),
        )
        programs = cursor.fetchall()

        lines = [
            f"Course: {row['code']} — {row['title']}",
            f"Credits: {row['credits']}",
            f"Semester: {row['semester'] or 'Not specified'}",
            f"Professor: {row['professor'] or 'TBA'}",
            f"Description: {row['description'] or 'No description available.'}",
            f"Prerequisites: {', '.join(prereqs) if prereqs else 'None'}",
        ]

        if programs:
            prog_lines = [
                f"  • {p['program']} ({p['requirement_type']})"
                + (f": {p['notes']}" if p["notes"] else "")
                for p in programs
            ]
            lines.append("Part of degree programs:\n" + "\n".join(prog_lines))

        return "\n".join(lines)

    except sqlite3.Error as exc:
        logger.error("SQLite error during course lookup: %s", exc)
        return "A database error occurred while looking up the course. Please try again."
    finally:
        conn.close()


course_lookup_tool = Tool(
    name="course_lookup",
    description=(
        "Look up detailed information about a specific CityU course by its "
        "course code (e.g. 'AI620', 'CS510', 'MBA501'). Returns the course "
        "title, credits, description, professor, semester, and prerequisites. "
        "Use this tool when the student asks about a specific course by code "
        "or wants to know the prerequisites for a particular course. "
        "Input: the course code as a string (e.g. 'AI620')."
    ),
    func=_course_lookup,
)


# ---------------------------------------------------------------------------
# Tool 3: FAQ Search
# ---------------------------------------------------------------------------


def _faq_search(question: str) -> str:
    """Search the FAQ table using SQL LIKE keyword matching.

    Parameters
    ----------
    question : str
        The student's question or a relevant keyword phrase.

    Returns
    -------
    str
        The best-matching FAQ answer, or ``"No FAQ found."`` if there is no
        close match.
    """
    logger.debug("FAQ search: %s", question)

    try:
        conn = _get_db_connection()
    except FileNotFoundError as exc:
        return str(exc)

    try:
        cursor = conn.cursor()

        # Build keyword tokens for a broad LIKE search
        keywords = [w.strip() for w in question.split() if len(w.strip()) > 2]
        if not keywords:
            keywords = [question.strip()]

        # Search with each keyword, accumulate all matches, deduplicate by id
        seen_ids: set[int] = set()
        results: list[sqlite3.Row] = []

        for keyword in keywords:
            pattern = f"%{keyword}%"
            cursor.execute(
                "SELECT id, question, answer, category "
                "FROM faqs WHERE question LIKE ? OR answer LIKE ? "
                "LIMIT 5",
                (pattern, pattern),
            )
            for row in cursor.fetchall():
                if row["id"] not in seen_ids:
                    seen_ids.add(row["id"])
                    results.append(row)

        if not results:
            return (
                "No FAQ found for your question. "
                "Please contact the CityU academic advising office for assistance."
            )

        # Return the first (most relevant) match
        best = results[0]
        response = (
            f"FAQ ({best['category'] or 'General'}):\n"
            f"Q: {best['question']}\n"
            f"A: {best['answer']}"
        )

        if len(results) > 1:
            response += (
                f"\n\n(Found {len(results)} related FAQ entries. "
                "Ask a more specific question if this doesn't answer your query.)"
            )

        return response

    except sqlite3.Error as exc:
        logger.error("SQLite error during FAQ search: %s", exc)
        return "A database error occurred while searching FAQs. Please try again."
    finally:
        conn.close()


faq_tool = Tool(
    name="faq_search",
    description=(
        "Search the CityU Frequently Asked Questions database for answers to "
        "common student questions about admissions, registration, financial aid, "
        "graduation requirements, campus policies, student services, and general "
        "university procedures. Use this tool when the student asks a common "
        "administrative or procedural question that is not about a specific course "
        "code. Input: the student's question or relevant keywords as a string."
    ),
    func=_faq_search,
)


# ---------------------------------------------------------------------------
# Tool 4: Suggest Course Update
# ---------------------------------------------------------------------------


def _suggest_course_update(suggestion: str) -> str:
    """Log a suggested course information update with reasoning for human review.

    Parameters
    ----------
    suggestion : str
        Description of the suggested update with reasoning (e.g.,
        "AI620: Add prerequisites AI500, AI600 based on course content analysis.
         Reasoning: Course covers machine learning, deep learning, and NLP which
         are taught in AI500 and AI600.").

    Returns
    -------
    str
        Confirmation message with next steps.
    """
    from datetime import datetime

    log_file = PROJECT_ROOT / "suggested_updates.log"
    timestamp = datetime.now().isoformat()

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"\n[{timestamp}]\n{suggestion}\n" + "="*80 + "\n")
        logger.info("Update suggestion logged: %s", suggestion[:100])
        return (
            f"✓ Suggestion logged for human review:\n{suggestion}\n\n"
            "A human will verify and update the database accordingly."
        )
    except Exception as exc:
        logger.error("Failed to log suggestion: %s", exc)
        return f"Could not log suggestion. Error: {exc}"


suggest_update_tool = Tool(
    name="suggest_course_update",
    description=(
        "Log a suggested course information update (e.g., corrected prerequisites, "
        "missing course details). Use this when you find inconsistencies between "
        "sources or when course information seems incomplete. A human will review "
        "and approve updates to the database. "
        "Input: a clear description of the suggested update."
    ),
    func=_suggest_course_update,
)


# ---------------------------------------------------------------------------
# Exported tool list
# ---------------------------------------------------------------------------

ALL_TOOLS: list[Tool] = [rag_search_tool, course_lookup_tool, faq_tool, suggest_update_tool]
