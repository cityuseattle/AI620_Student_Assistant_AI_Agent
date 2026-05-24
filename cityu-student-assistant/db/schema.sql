-- =============================================================================
-- CityU Student Assistant — SQLite Schema
-- =============================================================================

PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------------
-- Courses
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS courses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT    NOT NULL UNIQUE,   -- e.g. "AI620"
    title       TEXT    NOT NULL,
    credits     INTEGER NOT NULL DEFAULT 3,
    description TEXT,
    semester    TEXT,                      -- e.g. "Fall 2025", "Spring 2026"
    professor   TEXT
);

-- -----------------------------------------------------------------------------
-- Prerequisites  (many-to-many: a course can have multiple prereqs)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS prerequisites (
    course_code TEXT NOT NULL,
    prereq_code TEXT NOT NULL,
    prereq_type TEXT DEFAULT 'required',  -- 'required', 'corequisite', 'recommended'
    notes       TEXT,                      -- e.g. "or CS101"
    PRIMARY KEY (course_code, prereq_code),
    FOREIGN KEY (course_code) REFERENCES courses(code) ON DELETE CASCADE,
    FOREIGN KEY (prereq_code) REFERENCES courses(code) ON DELETE CASCADE
);

-- -----------------------------------------------------------------------------
-- Degree Requirements
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS degree_requirements (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    program          TEXT NOT NULL,   -- e.g. "MSAI", "MSIS", "MBA"
    requirement_type TEXT NOT NULL,   -- e.g. "Core", "Elective", "Capstone"
    course_code      TEXT NOT NULL,
    notes            TEXT,
    FOREIGN KEY (course_code) REFERENCES courses(code) ON DELETE CASCADE
);

-- -----------------------------------------------------------------------------
-- FAQs
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS faqs (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    question TEXT NOT NULL,
    answer   TEXT NOT NULL,
    category TEXT   -- e.g. "Admissions", "Financial Aid", "Registration"
);

-- -----------------------------------------------------------------------------
-- Indexes for performance
-- -----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_courses_code          ON courses(code);
CREATE INDEX IF NOT EXISTS idx_prereqs_course        ON prerequisites(course_code);
CREATE INDEX IF NOT EXISTS idx_degree_req_program    ON degree_requirements(program);
CREATE INDEX IF NOT EXISTS idx_faqs_category         ON faqs(category);
