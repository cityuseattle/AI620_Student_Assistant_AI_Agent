"""
run_all.py — Orchestrates the full CityU RAG data pipeline.

Steps:
1. Run Scraper 1 (extract correct course codes from SmartCatalogIQ)
2. Run Scraper 2 (download ALL syllabus PDFs + extract text)
3. Print summary

Usage:
    python run_all.py
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

SCRIPTS = [
    "scripts/scrape_course_list.py",   # Scraper 1
    "scripts/scrape_cityu_courses_details.py",       # Scraper 2
]

def run_script(script_path):
    print(f"\n=== Running {script_path} ===")
    result = subprocess.run([sys.executable, script_path])
    if result.returncode != 0:
        print(f"ERROR: Script failed → {script_path}")
        sys.exit(1)
    print(f"✓ Completed: {script_path}")


def main():
    print("\n======================================")
    print("  CityU RAG Pipeline — Full Run Start")
    print("======================================\n")

    for script in SCRIPTS:
        run_script(str(PROJECT_ROOT / script))

    print("\n======================================")
    print("  CityU RAG Pipeline — All Done!")
    print("======================================\n")
    print("Your data is ready in:")
    print("  • data/cityu_courses.json")
    print("  • data/raw/*.txt (full syllabus text)")
    print("\nYou can now ingest into ChromaDB.\n")


if __name__ == "__main__":
    main()
