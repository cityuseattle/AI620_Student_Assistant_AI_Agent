"""
CityU SmartCatalog scraper using Playwright (no Selenium, no ChromeDriver).

This version:
- Loads the Course Descriptions page
- Clicks "Load More" until all courses are loaded
- Extracts ALL course tables
- Writes JSON compatible with seed_database.py
"""

import argparse
import json
import logging
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "cityu_courses.json"

COURSE_URL = (
    "https://cityu.smartcatalogiq.com/2025-2026/2025-2026-catalog/course-descriptions/"
)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scrape_cityu")


def load_all_courses(page):
    """
    Click "Load More" until it disappears.
    """
    logger.info("Clicking 'Load More' to load all courses...")
    while True:
        btn = page.locator("text=Load More")
        try:
            if btn.count() == 0 or not btn.first.is_visible():
                break
            logger.info("Clicking 'Load More'...")
            btn.first.click()
            page.wait_for_timeout(1000)  # small delay for new tables to load
        except Exception:
            break
    logger.info("Finished loading all courses.")


def scrape_courses(url: str):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        logger.info("Loading page...")
        page.goto(url, timeout=60000)

        # Ensure first tables are present
        page.wait_for_selector("table", timeout=60000)

        # Load all remaining courses
        load_all_courses(page)

        logger.info("Extracting tables...")
        tables = page.query_selector_all("table")

        courses = []
        seen = set()

        for table in tables:
            rows = table.query_selector_all("tr")
            if not rows:
                continue

            # Check header
            headers = [h.inner_text().strip().upper() for h in rows[0].query_selector_all("th")]
            if "COURSE #" not in headers:
                continue

            # Parse rows
            for row in rows[1:]:
                cells = row.query_selector_all("td")
                if len(cells) < 2:
                    continue

                raw_code = cells[0].inner_text().strip()
                title = cells[1].inner_text().strip()

                if not raw_code or not title:
                    continue

                code = raw_code.replace(" ", "").upper()

                if code in seen:
                    continue
                seen.add(code)

                courses.append({
                    "code": code,
                    "title": title,
                    "credits": 3,
                    "description": "",
                    "semester": "",
                    "professor": "",
                    "prerequisites": [],
                })

        browser.close()
        return courses


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=COURSE_URL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    logger.info("Scraping CityU catalog...")
    courses = scrape_courses(args.url)

    logger.info("Extracted %d courses", len(courses))

    data = {
        "courses": courses,
        "degree_requirements": [],
        "faqs": [],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

    logger.info("Wrote %d courses to %s", len(courses), args.output)


if __name__ == "__main__":
    main()
