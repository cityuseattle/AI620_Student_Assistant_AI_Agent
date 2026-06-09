"""
run_all.py — Orchestrates the full CityU Student Assistant AI Agent data pipeline.

Smart Features:
1. Detects existing data assets and skips scraping automatically.
2. Formats scraped files into a clean database layout schema.
3. Seeds the relational SQLite database core cleanly.
4. Builds the structural document semantic layer inside ChromaDB.

Usage:
    python run_all.py
"""

import subprocess
import sys
from pathlib import Path

# Ensure UTF-8 output so emoji/status characters don't crash on Windows cp1252 consoles.
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):
    pass

PROJECT_ROOT = Path(__file__).resolve().parent

# Universal System File Map Tracking
COURSES_JSON = PROJECT_ROOT / "data" / "cityu_courses.json"
RAW_TXT_DIR = PROJECT_ROOT / "data" / "raw"

def run_script(script_relative_path: str, args: list = None):
    """Executes a Python script subprocess cleanly inside the current venv context."""
    script_path = PROJECT_ROOT / script_relative_path
    print(f"\n⚙️  [Running Pipeline Stage] -> {script_relative_path}")
    
    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)
        
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"❌ ERROR: Stage failed processing -> {script_relative_path}")
        sys.exit(1)
    print(f"✅ Stage Completed: {script_relative_path}")


def main():
    print("\n============================================================")
    print("  CityU AI Student Assistant — Smart Pipeline Orchestrator  ")
    print("============================================================\n")

    # --- STAGE 1: DYNAMIC WORKLOAD SCANNERS ---
    scraped_files_count = len(list(RAW_TXT_DIR.glob("*.txt"))) if RAW_TXT_DIR.exists() else 0
    
    # Check if data files already exist on disk
    if COURSES_JSON.exists() and scraped_files_count > 50:
        print(f"⏩ Found existing data assets ({scraped_files_count} text profiles detected).")
        print("   Skipping live scraping loops to preserve network bandwidth and execution time.")
    else:
        print("📥 Raw text data assets missing or incomplete. Launching catalog crawlers...")
        #run_script("scripts/scrape_course_list.py") - To be removed if running locally first time 
        #run_script("scripts/scrape_cityu_courses_details.py")- To be removed if running locally first time 

    # --- STAGE 2: PRE-PROCESSING BRIDGE LAYER ---
    print("\n🧹 Launching pre-processing formatting bridge...")
    run_script("scripts/prepare_json_for_seeding.py")

    # --- STAGE 3: RELATIONAL DATA LAYER SEEDING (SQLite) ---
    print("\n🗄️ Seeding structural SQLite data core...")
    # Targets the compiled, constraint-safe JSON output explicitly
    run_script("scripts/seed_database.py", args=["--data-file", "data/cityu_courses_ready.json"])

    # --- STAGE 4: SEMANTIC VECTOR INGESTION (ChromaDB) ---
    print("\n🧠 Constructing semantic knowledge embeddings in ChromaDB...")
    run_script("scripts/ingest_documents.py")

    print("\n============================================================")
    print("  🎉 CityU RAG Pipeline Integration Complete! All Done!    ")
    print("============================================================\n")
    print("Your databases are synchronized, optimized, and ready for queries:")
    print("  • Structured Records Matrix  ->  db/cityu.db (SQLite)")
    print("  • Unstructured Document Space ->  chroma_db/  (Chroma Vector Store)")
    print("\nYou can now safely execute your application backend services:")
    print("  👉 uvicorn api.main:app --reload")
    print("  👉 streamlit run frontend/app.py\n")

    # after running successfuly test by running 
    # 
    run_script("db/test_locally_db.py")

if __name__ == "__main__":
    main()
