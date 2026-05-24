import json
import re
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

# Automatic path tracking
PROJECT_ROOT = Path(__file__).resolve().parent.parent
COURSES_JSON = PROJECT_ROOT / "data" / "cityu_courses.json"
RAW_DIR = PROJECT_ROOT / "data" / "raw"

def clean_text(text):
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def scrape_courses():
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if not COURSES_JSON.exists():
        print(f"❌ Target catalog map file missing: {COURSES_JSON}")
        sys.exit(1)

    with open(COURSES_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    courses = data.get("courses", [])
    total_courses = len(courses)
    print(f"📋 Loaded {total_courses} target course profiles.")

    with sync_playwright() as p:
        print("🚀 Starting Chromium engine...")
        # Added anti-fingerprint launch flags to bypass random hangs
        browser = p.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        # Performance optimization step: skip loading unnecessary binary assets
        page.route("**/*.{png,jpg,jpeg,gif,svg,css,woff,woff2,ico}", lambda route: route.abort())

        for idx, course in enumerate(courses, 1):
            url = course.get("detail_url")
            code = course.get("normalized_code") or course.get("code", "").replace(" ", "")
            txt_path = RAW_DIR / f"{code}.txt"
            
            if txt_path.exists():
                print(f"⏩ [{idx}/{total_courses}] {code} matches local file disk storage. Skipping.")
                continue

            print(f"📥 [{idx}/{total_courses}] Navigating to {code} structural layer...", flush=True)
            
            try:
                # Use a combined timeout approach to prevent hanging
                page.goto(url, timeout=20000, wait_until="commit")
                time.sleep(2.5) # Safe structural load window execution buffer

                # --- 1. TITLE PARSER ---
                title = "N/A"
                if page.locator("h1").count() > 0:
                    title = clean_text(page.locator("h1").first.inner_text())
                else:
                    title = course.get("title", code)

                # --- 2. RESILIENT MAIN CONTENT HARVESTER ---
                # Targets general layout containers since strict classes fail
                full_body_text = ""
                for selector in ["div#main", "main", "article", "div.main", "body"]:
                    if page.locator(selector).count() > 0:
                        full_body_text = page.locator(selector).first.inner_text()
                        if len(full_body_text) > 150:
                            break

                # --- 3. FIELD DATA ISOLATION (Using flexible text lookahead parsing) ---
                credits_val = "None"
                prereqs_val = "None"
                description = "No direct course description text captured."
                outcomes = []

                if full_body_text:
                    # Clean isolated lines array
                    lines = [line.strip() for line in full_body_text.split('\n') if line.strip()]
                    
                    # Target Description matching blocks 
                    desc_startIndex = None
                    for i, line in enumerate(lines):
                        if title in line or code in line:
                            # The paragraph directly following the title/code match is typically the description
                            desc_startIndex = i + 1
                            break
                    
                    if desc_startIndex is not None and desc_startIndex < len(lines):
                        candidate_desc = []
                        for line in lines[desc_startIndex:]:
                            # Terminate description collection if hitting a known structural separator element
                            if any(header_word in line for header_word in ["Credits", "Prerequisite", "Outcomes", "Syllabus"]):
                                break
                            candidate_desc.append(line)
                        if candidate_desc:
                            description = " ".join(candidate_desc)

                    # Extract metadata blocks via direct line verification
                    for i, line in enumerate(lines):
                        if "Credits" in line and (i + 1) < len(lines):
                            credits_val = lines[i + 1]
                        if "Prerequisite" in line and (i + 1) < len(lines):
                            prereqs_val = lines[i + 1]
                        if "Outcomes" in line:
                            # Collect following lines that look like bullet elements or items
                            for n in range(i + 1, min(i + 8, len(lines))):
                                if any(stop_w in lines[n] for stop_w in ["Credits", "Prerequisite", "Description"]):
                                    break
                                outcomes.append(lines[n])

                # --- 4. DATA WRITER PIPELINE ---
                output_lines = [
                    f"Course Code: {code}",
                    f"Title: {title}",
                    f"URL: {url}",
                    f"Credits: {credits_val}",
                    f"Prerequisites: {prereqs_val}",
                    "",
                    "Description:",
                    description,
                    "",
                    "Outcomes:",
                ]
                output_lines.extend(outcomes or ["None"])

                txt_path.write_text("\n".join(output_lines), encoding="utf-8")
                print(f"✅ [{idx}/{total_courses}] Successfully written payload file data: {code}.txt")

            except Exception as error:
                print(f"❌ Scraping engine bypass warning on index entry {code}: {str(error)[:90]}")
                # Save a structural warning trace instead of terminating thread processing completely
                txt_path.write_text(f"Course Code: {code}\nURL: {url}\nError: Data collection thread timed out or target element altered.", encoding="utf-8")
                continue

        browser.close()
    print(f"\n🎉 Task verification operations complete. Exported files saved in: {RAW_DIR}")

if __name__ == "__main__":
    scrape_courses()
