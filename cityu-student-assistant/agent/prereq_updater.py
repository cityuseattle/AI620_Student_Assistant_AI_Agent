"""
agent/prereq_updater.py — Self-updating prerequisite engine.

When the structured database has no prerequisites for a course, the agent can
infer likely prerequisites with its LLM reasoning and propose adding them.

Two operating modes (controlled by ``PREREQ_UPDATE_MODE`` env var or set at
runtime via :func:`set_mode`):

* ``approval`` (default, safe) — the proposal is recorded as **pending** in the
  change log. The database is NOT modified until a human approves it.
* ``auto`` — the proposal is written to ``cityu.db`` immediately and recorded as
  **applied** so it can be reviewed (and reverted) later.

All proposals — pending, applied, approved, rejected — are appended as JSON
lines to ``prereq_updates.jsonl`` at the project root for auditability.
"""

from __future__ import annotations

import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from db import queries

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = PROJECT_ROOT / "prereq_updates.jsonl"
MODE_FILE = PROJECT_ROOT / ".prereq_mode"

VALID_MODES = {"approval", "auto"}
_DEFAULT_MODE = "approval"

# Status values used in the change log.
STATUS_PENDING = "pending"
STATUS_APPLIED = "applied"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

_lock = Lock()


# ---------------------------------------------------------------------------
# Mode management (persisted to a small file so it survives restarts)
# ---------------------------------------------------------------------------


def get_mode() -> str:
    """Return the current update mode ('approval' or 'auto')."""
    if MODE_FILE.exists():
        value = MODE_FILE.read_text(encoding="utf-8").strip().lower()
        if value in VALID_MODES:
            return value
    env_value = os.getenv("PREREQ_UPDATE_MODE", _DEFAULT_MODE).strip().lower()
    return env_value if env_value in VALID_MODES else _DEFAULT_MODE


def set_mode(mode: str) -> str:
    """Persist a new update mode. Returns the normalised mode."""
    mode = mode.strip().lower()
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode '{mode}'. Use one of: {sorted(VALID_MODES)}")
    MODE_FILE.write_text(mode, encoding="utf-8")
    logger.info("Prerequisite update mode set to: %s", mode)
    return mode


# ---------------------------------------------------------------------------
# Log persistence (JSON Lines)
# ---------------------------------------------------------------------------


def _append_log(entry: dict) -> None:
    with _lock:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_all() -> list[dict]:
    if not LOG_FILE.exists():
        return []
    entries: list[dict] = []
    with _lock:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    logger.warning("Skipping malformed log line: %s", line[:80])
    return entries


def _rewrite_all(entries: list[dict]) -> None:
    with _lock:
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _latest_status_map() -> dict[str, dict]:
    """Collapse the append-only log into the latest entry per change id."""
    latest: dict[str, dict] = {}
    for entry in _read_all():
        cid = entry.get("id")
        if cid:
            latest[cid] = entry
    return latest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalise_prereqs(prereqs) -> list[str]:
    """Accept a list or a comma/space separated string; return clean codes."""
    if isinstance(prereqs, str):
        parts = re.split(r"[,\s]+", prereqs)
    else:
        parts = list(prereqs)
    cleaned: list[str] = []
    seen: set[str] = set()
    for p in parts:
        code = str(p).strip().upper()
        if code and code not in seen:
            seen.add(code)
            cleaned.append(code)
    return cleaned


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


def propose_prerequisites(
    course_code: str,
    prereqs,
    reasoning: str = "",
    source: str = "agent",
) -> dict:
    """Propose prerequisites for a course.

    Behaviour depends on the active mode:
    * approval → recorded as pending; DB untouched.
    * auto     → written to DB immediately; recorded as applied.

    Returns a result dict: ``{"status", "message", "id", "course_code",
    "prereqs", "mode"}``.
    """
    course_code = course_code.strip().upper()
    prereqs = _normalise_prereqs(prereqs)
    mode = get_mode()

    if not course_code:
        return {"status": "error", "message": "No course code provided.", "mode": mode}
    if not prereqs:
        return {
            "status": "error",
            "message": "No prerequisite codes provided.",
            "mode": mode,
            "course_code": course_code,
        }

    # The course being updated must exist.
    if not queries.course_exists(course_code):
        return {
            "status": "error",
            "message": f"Course '{course_code}' does not exist in the database.",
            "mode": mode,
            "course_code": course_code,
        }

    # Only fill prerequisites when none are recorded — never overwrite curated data.
    existing = queries.get_prerequisites(course_code)
    if existing:
        return {
            "status": "skipped",
            "message": (
                f"{course_code} already has {len(existing)} prerequisite(s) on "
                "record; no inference needed."
            ),
            "mode": mode,
            "course_code": course_code,
            "prereqs": [p["code"] for p in existing],
        }

    # Flag prereq codes that are not themselves known courses (kept, but noted).
    unknown = [p for p in prereqs if not queries.course_exists(p)]

    change_id = uuid.uuid4().hex[:12]
    base_entry = {
        "id": change_id,
        "course_code": course_code,
        "prereqs": prereqs,
        "unknown_prereqs": unknown,
        "reasoning": reasoning.strip(),
        "source": source,
        "mode": mode,
        "created_at": _now(),
    }

    if mode == "auto":
        inserted = queries.add_prerequisites(course_code, prereqs, notes="auto-inferred by agent")
        entry = {**base_entry, "status": STATUS_APPLIED, "inserted": inserted, "applied_at": _now()}
        _append_log(entry)
        logger.info("AUTO applied %d prereqs for %s: %s", inserted, course_code, prereqs)
        return {
            "status": STATUS_APPLIED,
            "message": (
                f"Auto-mode: added prerequisites {', '.join(prereqs)} to {course_code} "
                f"in the database (change id {change_id})."
            ),
            "id": change_id,
            "course_code": course_code,
            "prereqs": prereqs,
            "mode": mode,
        }

    # approval mode
    entry = {**base_entry, "status": STATUS_PENDING}
    _append_log(entry)
    logger.info("PENDING prereq proposal for %s: %s", course_code, prereqs)
    return {
        "status": STATUS_PENDING,
        "message": (
            f"Proposed prerequisites for {course_code}: {', '.join(prereqs)}. "
            f"Awaiting approval (change id {change_id}). "
            "Approve it in the Prerequisite Updates panel to write it to the database."
        ),
        "id": change_id,
        "course_code": course_code,
        "prereqs": prereqs,
        "mode": mode,
    }


def list_entries(status: Optional[str] = None, limit: int = 50) -> list[dict]:
    """Return the latest state of each change, optionally filtered by status."""
    entries = list(_latest_status_map().values())
    entries.sort(key=lambda e: e.get("created_at", ""), reverse=True)
    if status:
        entries = [e for e in entries if e.get("status") == status]
    return entries[:limit]


def list_pending(limit: int = 50) -> list[dict]:
    """Return pending proposals awaiting approval."""
    return list_entries(status=STATUS_PENDING, limit=limit)


def has_open_proposal(course_code: str) -> bool:
    """Return True if the course already has a pending/applied/approved change.

    Used to avoid creating duplicate proposals for the same course.
    """
    course_code = course_code.strip().upper()
    for entry in _latest_status_map().values():
        if entry.get("course_code", "").upper() == course_code and entry.get(
            "status"
        ) in (STATUS_PENDING, STATUS_APPLIED, STATUS_APPROVED):
            return True
    return False


def approve(change_id: str) -> dict:
    """Approve a pending change and write it to the database."""
    latest = _latest_status_map()
    entry = latest.get(change_id)
    if not entry:
        return {"status": "error", "message": f"Change '{change_id}' not found."}
    if entry.get("status") != STATUS_PENDING:
        return {
            "status": "error",
            "message": f"Change '{change_id}' is '{entry.get('status')}', not pending.",
        }

    course_code = entry["course_code"]
    prereqs = entry["prereqs"]
    inserted = queries.add_prerequisites(course_code, prereqs, notes="approved agent suggestion")
    record = {
        **entry,
        "status": STATUS_APPROVED,
        "inserted": inserted,
        "approved_at": _now(),
    }
    _append_log(record)
    logger.info("APPROVED change %s: %d prereqs added to %s", change_id, inserted, course_code)
    return {
        "status": STATUS_APPROVED,
        "message": f"Approved. Added {inserted} prerequisite(s) to {course_code}.",
        "id": change_id,
        "course_code": course_code,
        "prereqs": prereqs,
    }


def reject(change_id: str) -> dict:
    """Reject a pending change without modifying the database."""
    latest = _latest_status_map()
    entry = latest.get(change_id)
    if not entry:
        return {"status": "error", "message": f"Change '{change_id}' not found."}
    if entry.get("status") != STATUS_PENDING:
        return {
            "status": "error",
            "message": f"Change '{change_id}' is '{entry.get('status')}', not pending.",
        }
    record = {**entry, "status": STATUS_REJECTED, "rejected_at": _now()}
    _append_log(record)
    logger.info("REJECTED change %s for %s", change_id, entry["course_code"])
    return {
        "status": STATUS_REJECTED,
        "message": f"Rejected proposal for {entry['course_code']}.",
        "id": change_id,
    }
