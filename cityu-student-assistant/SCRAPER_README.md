# CityU Course Catalog Web Scraper

Automatically populate the course database from the CityU SmartCatalog portal.

## Quick Start

### Option 1: Use Sample Data (No Setup)

```bash
python scripts/scrape_cityu_courses.py
python scripts/seed_database.py
```

This uses the existing sample courses in `data/cityu_courses.json`.

---

### Option 2: Scrape Live Data from CityU Portal (Recommended)

#### Prerequisites

1. **Python 3.9+**
2. **Selenium & ChromeDriver**

```bash
# Install Selenium
pip install selenium

# Download ChromeDriver (must match your Chrome version)
# From: https://chromedriver.chromium.org/

# Option A: Add to PATH
#   Extract chromedriver and add to system PATH

# Option B: Specify in script
#   Edit scrape_cityu_courses.py line 50:
#   driver = webdriver.Chrome("/path/to/chromedriver", options=options)
```

#### Run the Scraper

```bash
python scripts/scrape_cityu_courses.py
```

The scraper will:
1. Load the CityU catalog at https://cityu.smartcatalogiq.com/2025-2026/2025-2026-catalog
2. Wait for JavaScript to render course listings
3. Extract course data (code, title, credits, prerequisites, etc.)
4. Write to `data/cityu_courses.json`

#### Then Seed the Database

```bash
python scripts/seed_database.py
```

This reads the JSON file and populates `db/cityu.db` with:
- Courses & prerequisites
- Degree requirements
- FAQs

---

## What Gets Extracted

Each course includes:
- **Code** (e.g., "AI620")
- **Title** (e.g., "Machine Learning for AI")
- **Credits** (3, 4, etc.)
- **Description** (full course description)
- **Prerequisites** (list of required courses)
- **Semester** (when offered)
- **Professor** (instructor name if available)

---

## Troubleshooting

### ChromeDriver Version Mismatch

If you get a "version mismatch" error:
1. Check your Chrome version: `chrome://version/`
2. Download matching ChromeDriver from https://chromedriver.chromium.org/
3. Replace the existing chromedriver

### Scraper Returns 0 Courses

**Possible causes:**
1. ChromeDriver not found → install it
2. Page structure changed → SmartCatalog updates may require code adjustments
3. Network issue → check internet connection

**Fallback:**
The scraper will automatically use sample data if live scraping fails.

---

## File Structure

```
cityu-student-assistant/
├── scripts/
│   ├── scrape_cityu_courses.py    ← Web scraper
│   └── seed_database.py           ← Database seeding
├── data/
│   └── cityu_courses.json         ← Scraped/sample data
└── db/
    ├── schema.sql                  ← Database schema
    └── cityu.db                    ← SQLite database (auto-created)
```

---

## Next Steps

After scraping and seeding:

1. **Start the API**:
   ```bash
   python -m uvicorn api.main:app --reload
   ```

2. **Query the agent**:
   ```bash
   curl -X POST http://localhost:8000/chat \
     -H "Content-Type: application/json" \
     -d '{"query": "What is AI620?", "session_id": "user1"}'
   ```

---

## Notes

- **First run:** The scraper may take 30-60 seconds as it waits for page rendering
- **Caching:** Course data is cached in ChromaDB for fast RAG queries
- **Persistence:** Database persists across server restarts; ChromaDB is in-process (memory + disk)
- **Updates:** Re-run scraper and seed_database to refresh course data
