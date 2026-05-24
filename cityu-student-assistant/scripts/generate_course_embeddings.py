"""Generate embedabale markdown files from course data.

Converts courses.json into individual .md files organized by program.
Each file contains rich course metadata for RAG embedding.

Output structure:
  data/courses_md/
    ├── MSAI/
    │   ├── AI600_Foundations_of_AI.md
    │   ├── AI610_Machine_Learning_Fundamentals.md
    │   └── ...
    ├── MSIS/
    │   ├── IS500_Foundations_of_IS.md
    │   └── ...
    └── General/
        └── SHARED_COURSES.md

Usage:
    python scripts/generate_course_embeddings.py [--data-file PATH] [--output-dir PATH]
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from textwrap import dedent

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_FILE = PROJECT_ROOT / "data" / "cityu_courses.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "courses_md"


def format_course_as_markdown(
    course: dict, degree_requirements: list[dict] | None = None
) -> str:
    """Convert course dict to embedabale markdown.

    Parameters
    ----------
    course : dict
        Course record from JSON.
    degree_requirements : list[dict], optional
        Degree requirements for context.

    Returns
    -------
    str
        Formatted markdown content.
    """
    code = course.get("code", "").upper()
    title = course.get("title", "")
    credits = course.get("credits", 3)
    description = course.get("description", "")
    semester = course.get("semester", "")
    professor = course.get("professor", "")
    prerequisites = course.get("prerequisites", [])

    # Filter degree requirements for this course
    requirements = (
        [r for r in degree_requirements if r.get("course_code") == code]
        if degree_requirements
        else []
    )

    md = f"""# {code}: {title}

## Course Information
- **Course Code**: {code}
- **Credits**: {credits}
- **Semester**: {semester or "Variable"}
- **Professor**: {professor or "TBA"}

## Description
{description or "No description available."}

"""

    # Prerequisites section
    if prerequisites:
        md += "## Prerequisites\n"
        for prereq in prerequisites:
            if isinstance(prereq, dict):
                p_code = prereq.get("code", "")
                p_type = prereq.get("type", "required").lower()
                p_notes = prereq.get("notes", "")
                if p_code:
                    md += f"- **{p_code}** ({p_type})"
                    if p_notes:
                        md += f": {p_notes}"
                    md += "\n"
            else:
                md += f"- {prereq}\n"
        md += "\n"

    # Degree requirements section
    if requirements:
        md += "## Program Requirements\n"
        for req in requirements:
            program = req.get("program", "")
            req_type = req.get("requirement_type", "")
            notes = req.get("notes", "")
            md += f"- **{program}**: {req_type}"
            if notes:
                md += f" — {notes}"
            md += "\n"
        md += "\n"

    md += f"""## Tags
course, {code.lower()}, credits:{credits}"""

    return md


def group_courses_by_program(
    courses: list[dict], degree_requirements: list[dict]
) -> dict[str, list[dict]]:
    """Group courses by the programs they belong to.

    Parameters
    ----------
    courses : list[dict]
        All courses.
    degree_requirements : list[dict]
        Degree requirements mapping courses to programs.

    Returns
    -------
    dict[str, list[dict]]
        Mapping program → courses in that program.
    """
    groups = {}

    for req in degree_requirements:
        program = req.get("program", "General")
        course_code = req.get("course_code", "")

        if program not in groups:
            groups[program] = set()
        groups[program].add(course_code)

    # Convert to course objects
    code_to_course = {c.get("code"): c for c in courses}
    result = {}

    for program, codes in groups.items():
        result[program] = [code_to_course[c] for c in codes if c in code_to_course]

    # Add any courses not in requirements to "General"
    required_codes = {c.get("code") for c in courses for req in degree_requirements}
    unassigned = [c for c in courses if c.get("code") not in required_codes]
    if unassigned:
        result["General"] = unassigned

    return result


def generate_course_files(
    data: dict, output_dir: Path, group_by_program: bool = True
) -> tuple[int, list]:
    """Generate markdown files from course data.

    Parameters
    ----------
    data : dict
        Loaded JSON data with "courses", "degree_requirements".
    output_dir : Path
        Output directory for generated files.
    group_by_program : bool
        If True, organize files by program subdirectories.

    Returns
    -------
    tuple[int, list]
        (files_written, warnings)
    """
    courses = data.get("courses", [])
    degree_requirements = data.get("degree_requirements", [])

    output_dir.mkdir(parents=True, exist_ok=True)
    files_written = 0
    warnings = []

    if group_by_program and degree_requirements:
        groups = group_courses_by_program(courses, degree_requirements)

        for program, program_courses in groups.items():
            program_dir = output_dir / program
            program_dir.mkdir(parents=True, exist_ok=True)

            for course in program_courses:
                code = course.get("code", "").upper()
                title = course.get("title", "").replace("/", "_")
                filename = f"{code}_{title}.md"

                try:
                    md_content = format_course_as_markdown(course, degree_requirements)
                    filepath = program_dir / filename
                    filepath.write_text(md_content, encoding="utf-8")
                    files_written += 1
                    logger.info("Wrote: %s", filepath.relative_to(PROJECT_ROOT))
                except Exception as exc:
                    msg = f"Failed to write {filename}: {exc}"
                    warnings.append(msg)
                    logger.warning(msg)
    else:
        # Flat structure, all courses in one directory
        for course in courses:
            code = course.get("code", "").upper()
            title = course.get("title", "").replace("/", "_")
            filename = f"{code}_{title}.md"

            try:
                md_content = format_course_as_markdown(course, degree_requirements)
                filepath = output_dir / filename
                filepath.write_text(md_content, encoding="utf-8")
                files_written += 1
                logger.info("Wrote: %s", filepath.relative_to(PROJECT_ROOT))
            except Exception as exc:
                msg = f"Failed to write {filename}: {exc}"
                warnings.append(msg)
                logger.warning(msg)

    return files_written, warnings


def generate_program_summary(
    data: dict, output_dir: Path
) -> None:
    """Create summary document per program listing all courses.

    Parameters
    ----------
    data : dict
        Loaded JSON data.
    output_dir : Path
        Output directory.
    """
    courses = data.get("courses", [])
    degree_requirements = data.get("degree_requirements", [])

    groups = group_courses_by_program(courses, degree_requirements)
    code_to_course = {c.get("code"): c for c in courses}

    for program, course_codes in groups.items():
        program_dir = output_dir / program
        summary_path = program_dir / "_PROGRAM_SUMMARY.md"

        md = f"# {program} Program Overview\n\n"
        md += f"## Courses in {program}\n\n"

        # Group by course type
        core_courses = []
        electives = []
        capstone = []

        for req in degree_requirements:
            if req.get("program") != program:
                continue

            code = req.get("course_code", "")
            req_type = req.get("requirement_type", "")
            course = code_to_course.get(code)

            if not course:
                continue

            entry = f"- **{code}**: {course.get('title', '')} ({course.get('credits', 3)} credits)"

            if req_type == "Core":
                core_courses.append(entry)
            elif req_type == "Capstone":
                capstone.append(entry)
            else:
                electives.append(entry)

        if core_courses:
            md += "### Core Courses\n" + "\n".join(core_courses) + "\n\n"
        if electives:
            md += "### Electives\n" + "\n".join(electives) + "\n\n"
        if capstone:
            md += "### Capstone\n" + "\n".join(capstone) + "\n\n"

        try:
            summary_path.write_text(md, encoding="utf-8")
            logger.info("Wrote program summary: %s", summary_path.relative_to(PROJECT_ROOT))
        except Exception as exc:
            logger.warning("Failed to write program summary: %s", exc)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Generate embedabale markdown files from course JSON data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--data-file",
        type=Path,
        default=DEFAULT_DATA_FILE,
        help="Path to cityu_courses.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory for generated markdown files",
    )
    parser.add_argument(
        "--flat",
        action="store_true",
        help="Generate flat structure (no program subdirs)",
    )
    parser.add_argument(
        "--skip-summary",
        action="store_true",
        help="Skip program summary generation",
    )
    return parser.parse_args()


def main() -> None:
    """Main generation pipeline."""
    args = parse_args()

    logger.info("=" * 70)
    logger.info("Course Markdown Generation for RAG Embedding")
    logger.info("Data file : %s", args.data_file)
    logger.info("Output dir: %s", args.output_dir)
    logger.info("=" * 70)

    # Load JSON
    if not args.data_file.exists():
        logger.error("Data file not found: %s", args.data_file)
        sys.exit(1)

    try:
        with open(args.data_file, encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        logger.error("Invalid JSON: %s", exc)
        sys.exit(1)

    # Generate files
    try:
        files_written, warnings = generate_course_files(
            data, args.output_dir, group_by_program=not args.flat
        )

        if not args.skip_summary and not args.flat:
            generate_program_summary(data, args.output_dir)

        logger.info("=" * 70)
        logger.info("Generation complete!")
        logger.info("  Files written: %d", files_written)
        if warnings:
            logger.warning("  Warnings: %d", len(warnings))
            for w in warnings[:5]:
                logger.warning("    - %s", w)
        logger.info("=" * 70)
        logger.info("\nNext step: Run ingest_documents.py to embed these files:")
        logger.info("  python scripts/ingest_documents.py --raw-dir %s", args.output_dir)

    except Exception as exc:
        logger.error("Generation failed: %s", exc, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
