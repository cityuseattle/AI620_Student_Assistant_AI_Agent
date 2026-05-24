import json
import re
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("prepare_json_for_seeding")

INPUT_JSON = PROJECT_ROOT / "data" / "cityu_courses.json"
OUTPUT_JSON = PROJECT_ROOT / "data" / "cityu_courses_ready.json"
RAW_TXT_DIR = PROJECT_ROOT / "data" / "raw"

def parse_txt_file(file_path: Path) -> dict:
    """Extracts clean database structural entities from a scraped course text file."""
    content = file_path.read_text(encoding="utf-8")
    
    # Extract credits as an integer, defaulting to 3 if not found or parsing fails
    credits_match = re.search(r"Credits:\s*(\d+)", content)
    credits_val = 3
    if credits_match:
        try:
            credits_val = int(credits_match.group(1))
        except ValueError:
            pass
            
    # Extract prerequisites line
    prereqs_match = re.search(r"Prerequisites:\s*([^\n]+)", content)
    prereqs_list = []
    notes = ""
    
    if prereqs_match:
        p_text = prereqs_match.group(1).strip()
        if p_text and p_text.lower() != "none":
            notes = p_text
            # Identify typical alphanumeric sequences like 'ECC 509' or 'AC 215'
            found_codes = re.findall(r"([A-Z]{2,5}\s*\d{3})", p_text)
            # Normalize them to match the exact spacing/case needed (no spaces, all caps)
            prereqs_list = [c.replace(" ", "").upper() for c in found_codes]

    # Extract description text layer cleanly
    desc_block = ""
    desc_search = re.search(r"Description:\n(.*?)(?=\n\n|\nOutcomes:|$)", content, re.DOTALL)
    if desc_search:
        desc_block = desc_search.group(1).strip()

    return {
        "credits": credits_val,
        "description": desc_block or "Course documentation details pending.",
        "prerequisites_extracted": prereqs_list,
        "notes": notes
    }

def main():
    if not INPUT_JSON.exists():
        logger.error("Input base data file missing: %s", INPUT_JSON)
        sys.exit(1)

    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        src_data = json.load(f)

    raw_courses = src_data.get("courses", [])
    processed_courses = []
    
    # Keep track of all valid course codes we are inserting to satisfy SQLite Foreign Key constraints
    valid_codes = set()
    for c in raw_courses:
        code = c.get("normalized_code") or c.get("code", "").replace(" ", "").upper()
        if code:
            valid_codes.add(code)

    logger.info("Syncing metadata constraints across %d tracking items...", len(raw_courses))

    for course in raw_courses:
        # Resolve clean code naming schema uniformly
        clean_code = course.get("normalized_code") or course.get("code", "").replace(" ", "").upper()
        if not clean_code:
            continue
            
        txt_path = RAW_TXT_DIR / f"{clean_code}.txt"
        
        # Structure fields exactly as expected by seed_database.py
        compiled_course = {
            "code": clean_code,
            "title": course.get("title", f"{clean_code} Course").strip(" *"),
            "credits": 3,
            "description": "Details pending administrative catalog processing.",
            "semester": "Fall, Winter, Spring",
            "professor": "Faculty Staff",
            "prerequisites": []
        }
        
        if txt_path.exists():
            parsed_metrics = parse_txt_file(txt_path)
            
            # Reconstruct the prerequisites array to fit seed_database.py requirements
            formatted_prereqs = []
            for p_code in parsed_metrics["prerequisites_extracted"]:
                # ONLY add the prerequisite if it actually exists in our course master list
                # This protects SQLite from foreign key reference errors
                if p_code in valid_codes:
                    formatted_prereqs.append({
                        "code": p_code,
                        "type": "required",
                        "notes": parsed_metrics["notes"]
                    })
                else:
                    logger.warning(
                        "Skipping prerequisite %s for %s (not in main course list)", 
                        p_code, clean_code
                    )

            compiled_course.update({
                "credits": parsed_metrics["credits"],
                "description": parsed_metrics["description"],
                "prerequisites": formatted_prereqs
            })
        else:
            logger.warning("No localized text sheet found for item: %s", clean_code)
            
        processed_courses.append(compiled_course)

    # Maintain existing arrays for degree requirements and FAQs
    output_payload = {
        "courses": processed_courses,
        "degree_requirements": src_data.get("degree_requirements", []),
        "faqs": src_data.get("faqs", [])
    }

    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)
        
    logger.info("Successfully exported fully structured seeding map layout to: %s", OUTPUT_JSON)

if __name__ == "__main__":
    main()
