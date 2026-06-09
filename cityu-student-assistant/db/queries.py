"""
db/queries.py — Reusable SQLite query helpers for the CityU course database.

These functions back ``db/test_locally_db.py`` and can be reused by tools.
All functions accept an optional ``db_path`` so they can target any database
file; by default they use ``db/cityu.db`` next to this module.
"""

import sqlite3
from pathlib import Path
from typing import Optional, Union

DB_FOLDER = Path(__file__).resolve().parent
DEFAULT_DB_PATH = DB_FOLDER / "cityu.db"

PathLike = Union[str, Path]


def _connect(db_path: Optional[PathLike] = None) -> sqlite3.Connection:
    """Open a SQLite connection with dict-like row access."""
    path = Path(db_path) if db_path else DEFAULT_DB_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Database not found at {path}. Run scripts/seed_database.py first."
        )
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    return conn


def get_course_info(code: str, db_path: Optional[PathLike] = None) -> Optional[dict]:
    """Return a single course as a dict, or None if not found."""
    code = code.strip().upper()
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT code, title, credits, description, semester, professor "
            "FROM courses WHERE UPPER(code) = ?",
            (code,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_prerequisites(code: str, db_path: Optional[PathLike] = None) -> list[dict]:
    """Return the direct prerequisites for a course.

    Each item has keys: ``code``, ``title``, ``type``.
    """
    code = code.strip().upper()
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT p.prereq_code AS code,
                   c.title       AS title,
                   p.prereq_type AS type
            FROM prerequisites p
            LEFT JOIN courses c ON UPPER(c.code) = UPPER(p.prereq_code)
            WHERE UPPER(p.course_code) = ?
            ORDER BY p.prereq_code
            """,
            (code,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_prerequisite_chain(
    code: str,
    max_depth: int = 3,
    db_path: Optional[PathLike] = None,
    _depth: int = 0,
    _seen: Optional[set] = None,
) -> dict:
    """Recursively build a prerequisite tree for a course.

    Returns a nested dict: ``{"code", "title", "prerequisites": [...]}``.
    Cycles and depth overflow are guarded against.
    """
    code = code.strip().upper()
    if _seen is None:
        _seen = set()

    info = get_course_info(code, db_path=db_path)
    node = {
        "code": code,
        "title": info["title"] if info else None,
        "prerequisites": [],
    }

    if _depth >= max_depth or code in _seen:
        return node

    _seen.add(code)
    for prereq in get_prerequisites(code, db_path=db_path):
        node["prerequisites"].append(
            get_prerequisite_chain(
                prereq["code"],
                max_depth=max_depth,
                db_path=db_path,
                _depth=_depth + 1,
                _seen=_seen,
            )
        )
    return node


def search_courses(keyword: str, db_path: Optional[PathLike] = None) -> list[dict]:
    """Search courses by code, title, or description substring.

    Each item has keys: ``code``, ``title``, ``credits``.
    """
    like = f"%{keyword.strip()}%"
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """
            SELECT code, title, credits
            FROM courses
            WHERE code LIKE ? OR title LIKE ? OR description LIKE ?
            ORDER BY code
            """,
            (like, like, like),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def course_exists(code: str, db_path: Optional[PathLike] = None) -> bool:
    """Return True if a course with the given code exists."""
    code = code.strip().upper()
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT 1 FROM courses WHERE UPPER(code) = ? LIMIT 1", (code,)
        ).fetchone()
        return row is not None
    finally:
        conn.close()


def add_prerequisites(
    course_code: str,
    prereqs: list[str],
    prereq_type: str = "required",
    notes: Optional[str] = None,
    db_path: Optional[PathLike] = None,
) -> int:
    """Insert prerequisite rows for a course, ignoring duplicates.

    Returns the number of prerequisite rows actually inserted.
    """
    course_code = course_code.strip().upper()
    conn = _connect(db_path)
    try:
        inserted = 0
        for prereq in prereqs:
            prereq = prereq.strip().upper()
            if not prereq or prereq == course_code:
                continue
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO prerequisites
                    (course_code, prereq_code, prereq_type, notes)
                VALUES (?, ?, ?, ?)
                """,
                (course_code, prereq, prereq_type, notes),
            )
            inserted += cur.rowcount
        conn.commit()
        return inserted
    finally:
        conn.close()
