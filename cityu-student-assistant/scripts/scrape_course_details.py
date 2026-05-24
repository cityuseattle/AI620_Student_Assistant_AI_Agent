"""
FINAL WORKING SCRAPER 2
Reads from cityu_courses.json
Scrapes REAL content from SmartCatalogIQ using Playwright locators
Saves TXT only (cleanest for embeddings)
"""

import json
import re
from pathlib import Path
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
COURSES_JSON = PROJECT_ROOT / "data" / "cityu_courses.json"
RAW_DIR = PROJECT_ROOT / "data" / "raw"


def scrape_page(url):
    """Load page with Playwright and extract REAL content."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        page.goto(url, timeout=60000)

        # WAIT for description to load
        page.wait_for_selector("div.sc-coursedescription", timeout=10000)

        # Title
        title = page.locator("h1").inner_text().strip()

        # Description
        desc = page.locator("div.sc-coursedescription").inner_text().strip()

        # Outcomes
        outcomes = []
        if page.locator("h2:has-text('Outcomes')").count() > 0:
            items = page.locator("h2:has-text('Outcomes') + ul li")
            for i in range(items.count()):
                outcomes.append(items.nth(i).inner_text().strip())

        # Prerequisites
        prereqs = []
        if page.locator("h2:has-text('Prerequisite')").count() > 0:
            p = page.locator("h2:has-text('Prerequisite') + p").inner_text()
            matches = re.findall(r"[A-Z]{2,5}\s*\d{3}", p)
            prereqs = sorted({m.replace(" ", "") for m in matches})

        # Credits
        credits = None
        if page.locator("h2:has-text('Credits')").count() > 0:
            p = page.locator("h2:has-text('Credits') + p").inner_text()
            m = re.search(r"\b(\d+)\b", p)
            if m:
                credits = int(m.group(1))

        browser.close()

        return {
            "title": title,
            "description": desc,
            "outcomes": outcomes,
            "prerequisites": prereqs,
            "credits": credits,
        }


def save_txt(data, outdir, code, url):
    outdir.mkdir(exist_ok=True)
    path = outdir / f"{code}.txt"

    lines = [
        f"Course Code: {code}",
        f"Title: {data['title']}",
        f"URL: {url}",
        f"Credits: {data['credits']}",
        f"Prerequisites: {', '.join(data['prerequisites']) or 'None'}",
        "",
        "Description:",
        data["description"],
        "",
        "Outcomes:",
    ]
    lines.extend(data["outcomes"] or ["None"])

    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    RAW_DIR.mkdir(exist_ok=True)

    data = json.loads(COURSES_JSON.read_text(encoding="utf-8"))
    courses = data["courses"]

    print(f"Loaded {len(courses)} courses")

    for course in courses:
        url = course["detail_url"]
        code = course["normalized_code"]

        print(f"Scraping {code} → {url}")

        scraped = scrape_page(url)
        save_txt(scraped, RAW_DIR, code, url)

    print("Done. Files saved in data/raw/")


if __name__ == "__main__":
    main()
