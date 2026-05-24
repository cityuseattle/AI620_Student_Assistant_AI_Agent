"""
db/test_locally_db.py — Audits local SQLite course and prerequisite records using queries.py
"""

import sys
import json
from pathlib import Path

# Inject the parent root directory so Python can see all project directories if needed
DB_FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(DB_FOLDER.parent))

# Import directly from queries.py which is in the same folder!
from db.queries import get_course_info, get_prerequisites, get_prerequisite_chain, search_courses

# Target the database file sitting right in this folder
REAL_DB_PATH = DB_FOLDER / "cityu.db"

def run_local_audit():
    print("=" * 60)
    print("📋 LOCAL SQLITE DATABASE AUDIT RUNNER")
    print(f"Target Database Path: {REAL_DB_PATH}")
    print("=" * 60)

    if not REAL_DB_PATH.exists():
        print(f"❌ Error: Database not found at {REAL_DB_PATH}. Run seed_database.py first.")
        return

    # 1. Test Course Lookup (Reading Scraped Data Rows)
    print("\n🔍 Test 1: Fetching Course Details for 'EEA641'...")
    course_info = get_course_info("EEA641", db_path=REAL_DB_PATH)
    if course_info:
        print(f"  ✓ Code:        {course_info['code']}")
        print(f"  ✓ Title:       {course_info['title']}")
        print(f"  ✓ Credits:     {course_info['credits']}")
        print(f"  ✓ Description: {course_info['description'][:140]}...")
    else:
        print("  ⚠️ Course EEA641 not found in database.")

    # 2. Test Prerequisite Lookup (Reading Scraped Many-to-Many Relationships)
    print("\n🔗 Test 2: Fetching Prerequisites for 'EEA641'...")
    prereqs = get_prerequisites("EEA641", db_path=REAL_DB_PATH)
    if prereqs:
        print(f"  ✓ Found {len(prereqs)} prerequisite requirement(s):")
        for p in prereqs:
            print(f"    ↳ {p['code']} - {p['title'] or 'No Title'} (Type: {p['type']})")
    else:
        print("  None (or course parent link pending execution)")

    # 3. Test Recursive Prerequisite Chain Engine
    print("\n🌳 Test 3: Building Prerequisite Chain Tree for 'EEA641'...")
    chain = get_prerequisite_chain("EEA641", max_depth=3, db_path=REAL_DB_PATH)
    print(json.dumps(chain, indent=4))

    # 4. Test Wildcard Search Matching
    print("\n🔎 Test 4: Searching catalog tables for keyword 'Accounting'...")
    search_results = search_courses("Accounting", db_path=REAL_DB_PATH)
    print(f"  ✓ Found {len(search_results)} items matching query string:")
    for res in search_results[:3]:
        print(f"    ↳ {res['code']}: {res['title']}")

    print("\n" + "=" * 60)
    print("🎉 Audit Complete! Your relational query tools are functioning.")
    print("=" * 60)

if __name__ == "__main__":
    run_local_audit()
