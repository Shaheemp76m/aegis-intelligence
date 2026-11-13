"""Aegis Intelligence - Project Memory, Tasks & Bugs Tests"""

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.isolated_test_case import IsolatedTestCase
from intelligence.project_memory import ProjectMemory
from intelligence.task_manager import TaskManager
from intelligence.bug_tracker import BugTracker

class TestMemoryTasksAndBugs(IsolatedTestCase):
    def setUp(self):
        super().setUp()
        self.pid = "proj_test_memory_123"
        from storage.database import db_session
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with db_session() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO projects (id, name, path, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (self.pid, "Memory Test Project", "/tmp/mem_test_proj", now, now)
            )

    def test_memory_crud_and_search(self):
        """Memory records persist across searches with keyword relevance ranking."""
        m1 = ProjectMemory.record_memory(
            project_id=self.pid,
            title="Database Architecture Decision",
            content="We chose SQLite with WAL mode for lightweight performance in Termux.",
            category="architecture",
            confidence="verified"
        )
        self.assertTrue(m1["id"].startswith("mem_"))
        self.assertEqual(m1["category"], "architecture")

        m2 = ProjectMemory.record_memory(
            project_id=self.pid,
            title="Frontend Framework Selection",
            content="We evaluated React and Svelte.",
            category="decision",
            confidence="verified"
        )

        # Keyword search
        search_results = ProjectMemory.search_memory(self.pid, query="SQLite WAL")
        self.assertTrue(len(search_results) >= 1)
        self.assertEqual(search_results[0]["id"], m1["id"])

        # Category search
        cat_results = ProjectMemory.search_memory(self.pid, category="architecture")
        self.assertTrue(any(x["id"] == m1["id"] for x in cat_results))

        # Memory update
        updated = ProjectMemory.update_memory(m1["id"], content="Updated SQLite architecture details.")
        self.assertIn("Updated", updated["content"])

        # Memory deletion
        self.assertTrue(ProjectMemory.delete_memory(m1["id"]))
        self.assertIsNone(ProjectMemory.get_memory(m1["id"]))

    def test_task_lifecycle_and_blockers(self):
        """Task creation, priority filtering, completion, and blocker detection."""
        t1 = TaskManager.create_task(
            project_id=self.pid,
            title="Implement user auth",
            priority="high",
            status="in_progress"
        )
        self.assertTrue(t1["id"].startswith("task_"))
        self.assertEqual(t1["priority"], "high")

        t2 = TaskManager.create_task(
            project_id=self.pid,
            title="Wait for third-party API keys",
            priority="critical",
            status="blocked",
            notes="Awaiting client credentials"
        )

        # Check blocker detection
        blockers = TaskManager.get_blockers(self.pid)
        self.assertTrue(any(b["id"] == t2["id"] for b in blockers))

        # Complete task
        completed = TaskManager.complete_task(t1["id"], notes="Delivered in PR #12")
        self.assertEqual(completed["status"], "completed")
        self.assertIsNotNone(completed["completed_at"])

        # Summary verification
        summary = TaskManager.get_summary(self.pid)
        self.assertGreaterEqual(summary["total"], 2)
        self.assertGreaterEqual(summary["blocked_count"], 1)

    def test_bug_tracker_verification_states(self):
        """Bug tracking distinguishes unverified suspicions from verified fixes."""
        b = BugTracker.create_bug(
            project_id=self.pid,
            title="UI flickering on resize",
            severity="medium",
            verification_status="unverified"
        )
        self.assertEqual(b["verification_status"], "unverified")

        # Diagnose
        diagnosed = BugTracker.update_bug(
            b["id"],
            diagnosis="Debounce missing on window resize event handler.",
            verification_status="diagnosed"
        )
        self.assertEqual(diagnosed["verification_status"], "diagnosed")

        # Resolve & verify
        resolved = BugTracker.resolve_bug(b["id"], resolution="Added 100ms debounce", verified=True)
        self.assertEqual(resolved["verification_status"], "verified_fixed")

if __name__ == "__main__":
    unittest.main()
