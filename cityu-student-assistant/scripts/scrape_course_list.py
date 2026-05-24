"""
Scraper 1: Extract full course codes + titles from SmartCatalogIQ.

Output:
data/cityu_courses.json
[
  {
    "code": "PPSY 500",
    "normalized_code": "PPSY500",
    "title": "Foundations of Counseling",
    "subject_url": "...",
    "detail_url": "..."
  },
  ...
]
"""

import json
import logging
import re
from pathlib import Path
from urllib.parse import urljoin
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_JSON = PROJECT_ROOT / "data" / "cityu_courses.json"

BASE_INDEX = "https://cityu.smartcatalogiq.com/2025-2026/2025-2026-catalog/course-descriptions/"

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger("scraper1")


def normalize(code: str) -> str:
    prefix = "".join(ch for ch in code if ch.isalpha())
    number = "".join(ch for ch in code if ch.isdigit())
    return f"{prefix}{number}"


def scrape():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        logger.info("Loading course index…")
        page.goto(BASE_INDEX)
        page.wait_for_timeout(800)

        # Collect subject pages
        subject_links = set()
        anchors = page.locator("a[href*='/course-descriptions/']")
        for i in range(anchors.count()):
            href = anchors.nth(i).get_attribute("href")
            if not href:
                continue
            full = urljoin(BASE_INDEX, href)
            if full.rstrip("/") != BASE_INDEX.rstrip("/"):
                subject_links.add(full)

        logger.info("Found %d subject pages", len(subject_links))

        courses = []
        pattern = re.compile(r"\b([A-Z]{2,5})\s*(\d{3})\b")

        for subject_url in sorted(subject_links):
            logger.info("Scanning subject: %s", subject_url)
            try:
                page.goto(subject_url)
                page.wait_for_timeout(800)
            except:
                continue

            links = page.locator("a")
            for i in range(links.count()):
                text = (links.nth(i).inner_text() or "").strip()
                href = links.nth(i).get_attribute("href")
                if not text or not href:
                    continue

                m = pattern.search(text)
                if not m:
                    continue

                prefix, number = m.group(1), m.group(2)
                code = f"{prefix} {number}"
                normalized = f"{prefix}{number}"

                detail_url = urljoin(subject_url, href)

                courses.append({
                    "code": code,
                    "normalized_code": normalized,
                    "title": text,
                    "subject_url": subject_url,
                    "detail_url": detail_url
                })

        browser.close()

    OUTPUT_JSON.write_text(json.dumps({"courses": courses}, indent=2))
    logger.info("Saved %d courses to %s", len(courses), OUTPUT_JSON)


if __name__ == "__main__":
    scrape()
