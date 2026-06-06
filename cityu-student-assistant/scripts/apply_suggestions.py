#!/usr/bin/env python
"""
Review and apply suggested course updates to the database.

Workflow:
1. Run this script to see pending suggestions
2. Edit suggested_updates.log to mark APPROVED: yes/no
3. Script applies approved updates to cityu.db
"""

import sqlite3
import re
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "db" / "cityu.db"
LOG_FILE = PROJECT_ROOT / "suggested_updates.log"


def parse_suggestions(log_content: str) -> list[dict]:
    """Parse suggestions from log file format."""
    suggestions = []
    # Look for sections with [timestamp] headers
    blocks = re.split(r'\n\[', log_content)

    for block in blocks:
        if not block.strip():
            continue

        # Check if approved
        approved = "APPROVED: yes" in block.lower()

        # Extract course code and prerequisites
        match = re.search(r'([A-Z]+\d+).*?prerequisites?.*?([A-Z]\d+(?:\s*,\s*[A-Z]\d+)*)', block, re.IGNORECASE)
        if match:
            course_code = match.group(1)
            prereqs = [p.strip() for p in match.group(2).split(',')]

            suggestions.append({
                'course_code': course_code,
                'prereqs': prereqs,
                'approved': approved,
                'reasoning': block[:200]  # first 200 chars as summary
            })

    return suggestions


def apply_update(course_code: str, prereqs: list[str]) -> bool:
    """Add prerequisites to database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Check if course exists
        cursor.execute("SELECT code FROM courses WHERE code = ?", (course_code,))
        if not cursor.fetchone():
            print(f"  ✗ Course {course_code} not found in database")
            return False

        # Clear existing prerequisites
        cursor.execute("DELETE FROM prerequisites WHERE course_code = ?", (course_code,))

        # Add new prerequisites
        for prereq in prereqs:
            cursor.execute(
                "INSERT INTO prerequisites (course_code, prereq_code) VALUES (?, ?)",
                (course_code, prereq.strip())
            )

        conn.commit()
        conn.close()
        print(f"  ✓ Updated {course_code} with prerequisites: {', '.join(prereqs)}")
        return True
    except Exception as e:
        print(f"  ✗ Error updating {course_code}: {e}")
        return False


def main():
    if not LOG_FILE.exists():
        print("No suggestions log found.")
        return

    with open(LOG_FILE, 'r') as f:
        content = f.read()

    suggestions = parse_suggestions(content)

    if not suggestions:
        print("No suggestions to review.")
        return

    print("\n" + "="*80)
    print("PENDING COURSE UPDATE SUGGESTIONS")
    print("="*80)

    approved_count = 0
    for i, sugg in enumerate(suggestions, 1):
        status = "✓ APPROVED" if sugg['approved'] else "○ PENDING"
        print(f"\n[{i}] {status}")
        print(f"    Course: {sugg['course_code']}")
        print(f"    Prerequisites: {', '.join(sugg['prereqs'])}")
        print(f"    Summary: {sugg['reasoning'][:100]}...")

    # Apply approved updates
    print("\n" + "="*80)
    print("APPLYING APPROVED UPDATES")
    print("="*80)

    for sugg in suggestions:
        if sugg['approved']:
            if apply_update(sugg['course_code'], sugg['prereqs']):
                approved_count += 1

    print(f"\n✓ Applied {approved_count} updates to database")
    print("\nTO APPROVE SUGGESTIONS:")
    print(f"1. Edit: {LOG_FILE}")
    print("2. Change 'APPROVED: no' to 'APPROVED: yes'")
    print("3. Run this script again")


if __name__ == "__main__":
    main()
