"""
SQLite database seeding script for the CityU Student Assistant.

Reads ``data/cityu_courses.json`` and inserts all records into the SQLite
database at ``db/cityu.db``.  The operation is idempotent: running this
script multiple times will not create duplicate records.

Expected JSON structure
-----------------------
{
  "courses": [
    {
      "code": "AI620",
      "title": "Machine Learning for AI",
      "credits": 3,
      "description": "...",
      "semester": "Fall 2025",
      "professor": "Dr. Smith",
      "prerequisites": ["AI510", "MATH500"]
    }
  ],
  "degree_requirements": [
    {
      "program": "MSAI",
      "requirement_type": "Core",
      "course_code": "AI620",
      "notes": "Required for all MSAI students."
    }
  ],
  "faqs": [
    {
      "question": "How do I register for classes?",
      "answer": "Log in to the CityU student portal at my.cityu.edu ...",
      "category": "Registration"
    }
  ]
}

Usage
-----
    python scripts/seed_database.py [--data-file PATH] [--db-path PATH]
"""

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("seed_database")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_DATA_FILE = PROJECT_ROOT / "data" / "cityu_courses.json"
DEFAULT_DB_PATH = PROJECT_ROOT / "db" / "cityu.db"
SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------


def init_database(db_path: Path) -> sqlite3.Connection:
    """Create the database and apply the schema if it doesn't exist.

    Parameters
    ----------
    db_path : Path
        Path to the SQLite database file.

    Returns
    -------
    sqlite3.Connection
        Open database connection.

    Raises
    ------
    FileNotFoundError
        If ``db/schema.sql`` is missing.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"Schema file not found: {SCHEMA_PATH}. "
            "Ensure db/schema.sql exists before seeding."
        )

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(schema_sql)
    conn.commit()

    logger.info("Database initialised at: %s", db_path)
    return conn


def seed_courses(conn: sqlite3.Connection, courses: list[dict]) -> tuple[int, int, list]:
    """Insert or ignore course records.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open database connection.
    courses : list[dict]
        List of course dicts from the JSON file.

    Returns
    -------
    tuple[int, int, list]
        (courses_inserted, prereqs_inserted, missing_prereq_warnings)
    """
    courses_inserted = 0
    prereqs_inserted = 0
    warnings = []

    # First pass: collect all course codes
    all_codes = {c.get("code", "").strip().upper() for c in courses if c.get("code", "").strip()}

    for course in courses:
        code = course.get("code", "").strip().upper()
        if not code:
            logger.warning("Skipping course with missing code: %s", course)
            continue

        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO courses
                    (code, title, credits, description, semester, professor)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    code,
                    course.get("title", ""),
                    course.get("credits", 3),
                    course.get("description", ""),
                    course.get("semester", ""),
                    course.get("professor", ""),
                ),
            )
            if conn.execute(
                "SELECT changes()"
            ).fetchone()[0]:
                courses_inserted += 1

        except sqlite3.IntegrityError as exc:
            logger.warning("Could not insert course %s: %s", code, exc)
            continue

        # Insert prerequisites with type support
        for prereq_item in course.get("prerequisites", []):
            if isinstance(prereq_item, dict):
                prereq_code = prereq_item.get("code", "").strip().upper()
                prereq_type = prereq_item.get("type", "required")
                notes = prereq_item.get("notes", "")
            else:
                prereq_code = str(prereq_item).strip().upper()
                prereq_type = "required"
                notes = ""

            if not prereq_code:
                continue

            if prereq_code not in all_codes:
                msg = f"{code}: prerequisite '{prereq_code}' not found in course list"
                warnings.append(msg)
                logger.warning(msg)
                continue

            try:
                conn.execute(
                    """INSERT OR IGNORE INTO prerequisites
                       (course_code, prereq_code, prereq_type, notes)
                       VALUES (?, ?, ?, ?)""",
                    (code, prereq_code, prereq_type, notes),
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    prereqs_inserted += 1
            except sqlite3.IntegrityError as exc:
                logger.warning(
                    "Could not insert prerequisite %s → %s: %s", code, prereq_code, exc
                )

    conn.commit()
    return courses_inserted, prereqs_inserted, warnings


def seed_degree_requirements(conn: sqlite3.Connection, requirements: list[dict]) -> int:
    """Insert or ignore degree requirement records.

    Parameters
    ----------
    conn : sqlite3.Connection
        Open database connection.
    requirements : list[dict]
        List of degree requirement dicts from the JSON file.

    Returns
    -------
    int
        Number of records inserted.
    """
    inserted = 0
    for req in requirements:
        program = req.get("program", "").strip()
        req_type = req.get("requirement_type", "").strip()
        course_code = req.get("course_code", "").strip().upper()
        notes = req.get("notes", "")

        if not all([program, req_type, course_code]):
            logger.warning("Skipping incomplete degree requirement: %s", req)
            continue

        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO degree_requirements
                    (program, requirement_type, course_code, notes)
                VALUES (?, ?, ?, ?)
                """,
                (program, req_type, course_code, notes),
            )
            if conn.execute("SELECT changes()").fetchone()[0]:
                inserted += 1
        except sqlite3.IntegrityError as exc:
            logger.warning("Could not insert degree requirement %s/%s: %s", program, course_code, exc)

    conn.commit()
    return inserted


def seed_faqs(conn: sqlite3.Connection, faqs: list[dict]) -> int:
    """Insert FAQ records (deduplication based on question text).

    Parameters
    ----------
    conn : sqlite3.Connection
        Open database connection.
    faqs : list[dict]
        List of FAQ dicts from the JSON file.

    Returns
    -------
    int
        Number of records inserted.
    """
    inserted = 0
    for faq in faqs:
        question = faq.get("question", "").strip()
        answer = faq.get("answer", "").strip()
        category = faq.get("category", "General").strip()

        if not question or not answer:
            logger.warning("Skipping FAQ with missing question or answer: %s", faq)
            continue

        # Check for duplicate question
        existing = conn.execute(
            "SELECT id FROM faqs WHERE question = ?", (question,)
        ).fetchone()

        if existing:
            continue  # idempotent — skip if already present

        conn.execute(
            "INSERT INTO faqs (question, answer, category) VALUES (?, ?, ?)",
            (question, answer, category),
        )
        inserted += 1

    conn.commit()
    return inserted


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Seed the CityU SQLite database from cityu_courses.json.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        default=DEFAULT_DATA_FILE,
        help="Path to the cityu_courses.json data file.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to the SQLite database file (will be created if absent).",
    )
    return parser.parse_args()


def main() -> None:
    """Main seeding pipeline."""
    args = parse_args()

    logger.info("=" * 60)
    logger.info("CityU Database Seeding Script")
    logger.info("Data file : %s", args.data_file)
    logger.info("DB path   : %s", args.db_path)
    logger.info("=" * 60)

    # Load JSON data
    if not args.data_file.exists():
        logger.error(
            "Data file not found: %s\n"
            "Please create data/cityu_courses.json with your CityU course data.",
            args.data_file,
        )
        sys.exit(1)

    try:
        with open(args.data_file, encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON in %s: %s", args.data_file, exc)
        sys.exit(1)

    # Initialise DB
    try:
        conn = init_database(args.db_path)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        sys.exit(1)

    try:
        # Seed tables
        courses_inserted, prereqs_inserted, prereq_warnings = seed_courses(
            conn, data.get("courses", [])
        )
        degree_reqs_inserted = seed_degree_requirements(
            conn, data.get("degree_requirements", [])
        )
        faqs_inserted = seed_faqs(conn, data.get("faqs", []))

        logger.info("=" * 60)
        logger.info("Seeding complete!")
        logger.info("  Courses inserted          : %d", courses_inserted)
        logger.info("  Prerequisites inserted     : %d", prereqs_inserted)
        logger.info("  Degree requirements inserted: %d", degree_reqs_inserted)
        logger.info("  FAQs inserted              : %d", faqs_inserted)
        if prereq_warnings:
            logger.warning("  Missing prerequisite references: %d", len(prereq_warnings))
            for w in prereq_warnings[:5]:
                logger.warning("    - %s", w)
            if len(prereq_warnings) > 5:
                logger.warning("    ... and %d more", len(prereq_warnings) - 5)
        logger.info("=" * 60)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
