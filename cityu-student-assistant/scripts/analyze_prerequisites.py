"""Analyze and validate the course prerequisite graph.

Detects issues:
- Circular dependencies
- Orphaned prerequisites
- Missing prerequisite definitions
- Unreachable courses
"""

import argparse
import logging
import sqlite3
from collections import defaultdict, deque
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


class PrerequisiteGraph:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.courses = set()
        self.graph = defaultdict(list)
        self.load()

    def load(self):
        """Load courses and prerequisites from database."""
        conn = sqlite3.connect(str(self.db_path))
        try:
            # Get all courses
            rows = conn.execute("SELECT code FROM courses").fetchall()
            self.courses = {row[0] for row in rows}

            # Get all prerequisites
            rows = conn.execute(
                "SELECT course_code, prereq_code, prereq_type FROM prerequisites"
            ).fetchall()
            for course_code, prereq_code, prereq_type in rows:
                self.graph[course_code].append((prereq_code, prereq_type))
        finally:
            conn.close()

    def find_cycles(self) -> list[list[str]]:
        """Detect cycles using DFS.

        Returns list of cycle paths, e.g. [["A", "B", "C", "A"]].
        """
        cycles = []
        visited = set()
        rec_stack = set()
        path = []

        def dfs(node):
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for prereq, _ in self.graph.get(node, []):
                if prereq not in visited:
                    dfs(prereq)
                elif prereq in rec_stack:
                    cycle_start = path.index(prereq)
                    cycles.append(path[cycle_start:] + [prereq])

            path.pop()
            rec_stack.discard(node)

        for course in self.courses:
            if course not in visited:
                dfs(course)

        return cycles

    def find_orphans(self) -> list[str]:
        """Find prerequisite codes that don't exist as courses."""
        orphans = []
        for course, prereqs in self.graph.items():
            for prereq, _ in prereqs:
                if prereq not in self.courses:
                    orphans.append(f"{course} → {prereq} (missing)")
        return sorted(set(orphans))

    def find_chains_by_length(self) -> dict[str, int]:
        """Calculate longest prerequisite chain for each course."""
        memo = {}

        def chain_length(course):
            if course in memo:
                return memo[course]

            if not self.graph.get(course):
                length = 0
            else:
                length = 1 + max(
                    (chain_length(p) for p, _ in self.graph[course]), default=0
                )

            memo[course] = length
            return length

        return {course: chain_length(course) for course in self.courses}

    def find_unreachable(self) -> list[str]:
        """Find courses with no prerequisites (unreachable without direct enrollment)."""
        no_prereq = [c for c in self.courses if c not in self.graph or not self.graph[c]]
        return sorted(no_prereq)

    def get_dependents(self, course: str) -> set[str]:
        """Find all courses that depend on this course (directly or indirectly)."""
        deps = set()
        queue = deque([course])

        while queue:
            node = queue.popleft()
            for course_code, prereqs in self.graph.items():
                for prereq, _ in prereqs:
                    if prereq == node and course_code not in deps:
                        deps.add(course_code)
                        queue.append(course_code)

        return deps


def main():
    parser = argparse.ArgumentParser(description="Analyze course prerequisite graph")
    parser.add_argument(
        "--db", type=Path, default=Path(__file__).parent.parent / "db" / "cityu.db"
    )
    args = parser.parse_args()

    if not args.db.exists():
        logger.error("Database not found: %s", args.db)
        return

    graph = PrerequisiteGraph(args.db)

    logger.info("=" * 60)
    logger.info("Prerequisite Graph Analysis")
    logger.info("=" * 60)

    # Courses summary
    logger.info(f"Total courses: {len(graph.courses)}")

    # Cycles
    cycles = graph.find_cycles()
    if cycles:
        logger.warning(f"Found {len(cycles)} circular dependency/ies:")
        for cycle in cycles:
            logger.warning(f"  → {' → '.join(cycle)}")
    else:
        logger.info("✓ No circular dependencies")

    # Orphans
    orphans = graph.find_orphans()
    if orphans:
        logger.warning(f"Found {len(orphans)} broken prerequisite reference(s):")
        for orphan in orphans[:10]:
            logger.warning(f"  × {orphan}")
        if len(orphans) > 10:
            logger.warning(f"  ... and {len(orphans) - 10} more")
    else:
        logger.info("✓ All prerequisites exist")

    # Chain length analysis
    chains = graph.find_chains_by_length()
    max_chain = max(chains.values())
    longest = [c for c, l in chains.items() if l == max_chain]
    logger.info(f"Longest prerequisite chain: {max_chain} steps")
    if longest:
        logger.info(f"  Courses: {', '.join(longest[:3])}")

    # Root courses
    roots = graph.find_unreachable()
    logger.info(f"Foundation courses (no prerequisites): {len(roots)}")
    if roots:
        logger.info(f"  {', '.join(roots[:5])}")

    logger.info("=" * 60)


if __name__ == "__main__":
    main()
