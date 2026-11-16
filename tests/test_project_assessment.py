"""Aegis Intelligence - Project Assessment Composite Action Tests

Verifies the composite read-only dispatcher action "project_assessment":
- Full multi-section technical assessment
- Selective section execution
- Non-git repository graceful handling (status: unavailable)
- Populated vs empty section result handling
- Section error isolation (failure in one section does not fail the whole assessment)
- Read-only guarantees (no mutations to database or filesystem)
- Alias normalization and parameter validation
"""

import os
import subprocess
import unittest
from datetime import datetime, timezone, timedelta
from tests.isolated_test_case import IsolatedTestCase
from core.tool_router import ToolRouter
from intelligence.project_analyzer import ProjectAnalyzer
from intelligence.task_manager import TaskManager
from intelligence.bug_tracker import BugTracker
from intelligence.project_memory import ProjectMemory
from storage.database import db_session

class TestProjectAssessment(IsolatedTestCase):
    """Exhaustive tests for composite read-only action 'project_assessment'."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # 1. Create a Git-backed sample project
        cls.git_proj_dir = os.path.join(cls._temp_dir, "git_sample_proj")
        os.makedirs(cls.git_proj_dir, exist_ok=True)
        subprocess.run(["git", "init"], cwd=cls.git_proj_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "AegisTester"], cwd=cls.git_proj_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "tester@aegis.local"], cwd=cls.git_proj_dir, check=True, capture_output=True)

        # Seed files
        with open(os.path.join(cls.git_proj_dir, "package.json"), "w") as f:
            f.write('{"name": "sample-app", "dependencies": {"react": "^18.0.0", "typescript": "^5.0.0"}}\n')
        with open(os.path.join(cls.git_proj_dir, "README.md"), "w") as f:
            f.write("# Sample App\nInitial git documentation.\n")

        subprocess.run(["git", "add", "."], cwd=cls.git_proj_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit for assessment testing"], cwd=cls.git_proj_dir, check=True, capture_output=True)

        cls.proj = ProjectAnalyzer.register_project(
            name="Assessment Git App",
            path=cls.git_proj_dir,
            description="Git-backed test app for composite assessment"
        )
        cls.project_id = cls.proj["id"]
        ProjectAnalyzer.set_active_project(cls.project_id)

        # Seed tasks: 1 pending, 1 in_progress, 1 blocked, 1 overdue
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        TaskManager.create_task(cls.project_id, title="Pending task", status="pending", priority="high")
        TaskManager.create_task(cls.project_id, title="In progress task", status="in_progress", priority="medium")
        TaskManager.create_task(cls.project_id, title="Blocked task", status="blocked", priority="critical")
        TaskManager.create_task(cls.project_id, title="Overdue task", status="pending", due_date=yesterday)

        # Seed bugs: 1 unverified, 1 diagnosed, 1 resolved (should not be in unresolved list)
        BugTracker.create_bug(cls.project_id, title="Unverified bug", severity="high", verification_status="unverified")
        BugTracker.create_bug(cls.project_id, title="Diagnosed bug", severity="critical", verification_status="diagnosed")
        BugTracker.create_bug(cls.project_id, title="Resolved bug", severity="medium", verification_status="resolved")

        # Seed memory items: 2 items
        ProjectMemory.record_memory(cls.project_id, title="DB Choice", content="SQLite with WAL mode", category="architecture")
        ProjectMemory.record_memory(cls.project_id, title="Framework Spec", content="React 18 with Vite", category="decision")

        # 2. Create a non-git project
        cls.nongit_proj_dir = os.path.join(cls._temp_dir, "nongit_sample_proj")
        os.makedirs(cls.nongit_proj_dir, exist_ok=True)
        with open(os.path.join(cls.nongit_proj_dir, "main.py"), "w") as f:
            f.write("# Non-git Python script\nprint('hello')\n")

        cls.nongit_proj = ProjectAnalyzer.register_project(
            name="Assessment Non-Git App",
            path=cls.nongit_proj_dir,
            description="Non-git directory for assessment testing"
        )
        cls.nongit_project_id = cls.nongit_proj["id"]

    def test_full_assessment_default_sections(self):
        """Verifies that project_assessment collects all 7 sections with structured data."""
        res = ToolRouter.dispatch("project_assessment", {"project_id": self.project_id})

        # Root metadata
        self.assertEqual(res["project_id"], self.project_id)
        self.assertEqual(res["project_name"], "Assessment Git App")
        self.assertEqual(res["project_path"], self.git_proj_dir)
        self.assertIn("assessed_at", res)
        self.assertEqual(res["section_errors"], {})

        # Verify all 7 sections present
        expected_sections = ["project", "git", "tasks", "bugs", "memory", "filesystem", "health"]
        for sec in expected_sections:
            self.assertIn(sec, res)
            self.assertEqual(res[sec]["status"], "ok")

        # 1. Project section verification
        p_sec = res["project"]
        self.assertEqual(p_sec["name"], "Assessment Git App")
        self.assertIn("TypeScript", p_sec["languages"])
        self.assertIn("React", p_sec["tech_stack"])
        self.assertEqual(p_sec["counts"]["tasks"], 4)
        self.assertEqual(p_sec["counts"]["bugs"], 3)
        self.assertEqual(p_sec["counts"]["memory_items"], 2)

        # 2. Git section verification
        g_sec = res["git"]
        self.assertTrue(g_sec["is_git"])
        self.assertEqual(g_sec["status"], "ok")
        self.assertGreaterEqual(len(g_sec["recent_commits"]), 1)
        self.assertEqual(g_sec["recent_commits"][0]["message"], "Initial commit for assessment testing")

        # 3. Tasks section verification
        t_sec = res["tasks"]
        self.assertEqual(t_sec["counts"]["total"], 4)
        self.assertGreaterEqual(t_sec["counts"]["pending"], 1)
        self.assertEqual(t_sec["counts"]["in_progress"], 1)
        self.assertEqual(t_sec["counts"]["blocked"], 1)
        self.assertGreaterEqual(t_sec["counts"]["overdue"], 1)
        self.assertTrue(any(t["title"] == "Blocked task" for t in t_sec["blocked"]))
        self.assertTrue(any(t["title"] == "Overdue task" for t in t_sec["overdue"]))

        # 4. Bugs section verification
        b_sec = res["bugs"]
        self.assertEqual(b_sec["total_bugs"], 3)
        # Resolved bug must NOT be in unresolved list
        self.assertEqual(b_sec["unresolved_count"], 2)
        unresolved_titles = [b["title"] for b in b_sec["unresolved"]]
        self.assertIn("Unverified bug", unresolved_titles)
        self.assertIn("Diagnosed bug", unresolved_titles)
        self.assertNotIn("Resolved bug", unresolved_titles)

        # 5. Memory section verification
        m_sec = res["memory"]
        self.assertEqual(m_sec["total_returned"], 2)
        self.assertIn("architecture", m_sec["category_breakdown"])
        self.assertIn("decision", m_sec["category_breakdown"])

        # 6. Filesystem section verification
        f_sec = res["filesystem"]
        self.assertGreaterEqual(f_sec["recently_modified_count"], 1)
        self.assertTrue(any(f["path"] == "README.md" for f in f_sec["recently_modified"]))

        # 7. Health section verification
        h_sec = res["health"]
        self.assertIsInstance(h_sec["verified_facts"], list)
        self.assertIsInstance(h_sec["inferred_conclusions"], list)
        self.assertIsInstance(h_sec["recommended_actions"], list)

    def test_selective_sections(self):
        """Verifies that requesting specific sections only computes those sections."""
        res = ToolRouter.dispatch("project_assessment", {
            "project_id": self.project_id,
            "sections": ["git", "tasks"]
        })
        self.assertIn("git", res)
        self.assertIn("tasks", res)
        self.assertNotIn("bugs", res)
        self.assertNotIn("memory", res)
        self.assertNotIn("filesystem", res)
        self.assertNotIn("health", res)
        self.assertEqual(res["sections_assessed"], ["git", "tasks"])

    def test_nongit_repository_handling(self):
        """Verifies that a non-git project marks git as unavailable without failing."""
        res = ToolRouter.dispatch("project_assessment", {"project_id": self.nongit_project_id})
        self.assertEqual(res["project_id"], self.nongit_project_id)

        # Git section must be marked unavailable
        g_sec = res["git"]
        self.assertEqual(g_sec["status"], "unavailable")
        self.assertFalse(g_sec["is_git"])
        self.assertEqual(g_sec["reason"], "Not a Git repository")
        self.assertEqual(g_sec["recent_commits"], [])

        # Non-git sections must succeed
        self.assertEqual(res["project"]["status"], "ok")
        self.assertEqual(res["filesystem"]["status"], "ok")
        self.assertEqual(res["tasks"]["status"], "ok")
        self.assertEqual(res["bugs"]["status"], "ok")
        self.assertEqual(res["section_errors"], {})

    def test_error_isolation_between_sections(self):
        """Verifies that an error in one section does not fail the entire assessment."""
        # Monkeypatch ProjectMemory.search_memory to simulate an internal retrieval error
        orig_search_memory = ProjectMemory.search_memory
        try:
            def broken_search(project_id, **kwargs):
                raise RuntimeError("Simulated vector index retrieval failure")
            ProjectMemory.search_memory = broken_search

            res = ToolRouter.dispatch("project_assessment", {"project_id": self.project_id})

            # Memory section captured the isolated error
            self.assertEqual(res["memory"]["status"], "error")
            self.assertIn("Simulated vector index retrieval failure", res["memory"]["error"])
            self.assertIn("memory", res["section_errors"])

            # All other 6 sections succeeded cleanly
            self.assertEqual(res["project"]["status"], "ok")
            self.assertEqual(res["git"]["status"], "ok")
            self.assertEqual(res["tasks"]["status"], "ok")
            self.assertEqual(res["bugs"]["status"], "ok")
            self.assertEqual(res["filesystem"]["status"], "ok")
            self.assertEqual(res["health"]["status"], "ok")
        finally:
            ProjectMemory.search_memory = orig_search_memory

    def test_strictly_read_only_guarantee(self):
        """Verifies that running an assessment does not mutate any database tables or files."""
        # Record initial row counts
        with db_session() as conn:
            p_before = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            t_before = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
            b_before = conn.execute("SELECT COUNT(*) FROM bugs").fetchone()[0]
            m_before = conn.execute("SELECT COUNT(*) FROM project_memory").fetchone()[0]
            a_before = conn.execute("SELECT COUNT(*) FROM approvals").fetchone()[0]
            # Record project timestamps
            proj_row = conn.execute("SELECT updated_at, last_inspected_at FROM projects WHERE id = ?", (self.project_id,)).fetchone()
            orig_updated = proj_row["updated_at"]
            orig_inspected = proj_row["last_inspected_at"]

        # Run assessment multiple times
        ToolRouter.dispatch("project_assessment", {"project_id": self.project_id})
        ToolRouter.dispatch("project_assessment", {"project_id": self.project_id, "sections": ["git", "health"]})

        # Verify state is completely unchanged
        with db_session() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0], p_before)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0], t_before)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM bugs").fetchone()[0], b_before)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM project_memory").fetchone()[0], m_before)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM approvals").fetchone()[0], a_before)

            proj_after = conn.execute("SELECT updated_at, last_inspected_at FROM projects WHERE id = ?", (self.project_id,)).fetchone()
            self.assertEqual(proj_after["updated_at"], orig_updated)
            self.assertEqual(proj_after["last_inspected_at"], orig_inspected)

    def test_alias_normalization(self):
        """Verifies that aliases 'assess_project' and 'project_assess' map to project_assessment."""
        res1 = ToolRouter.dispatch("assess_project", {"project_id": self.project_id, "sections": ["project"]})
        self.assertEqual(res1["project_id"], self.project_id)
        self.assertIn("project", res1)

        res2 = ToolRouter.dispatch("project_assess", {"project_id": self.project_id, "sections": ["project"]})
        self.assertEqual(res2["project_id"], self.project_id)
        self.assertIn("project", res2)

    def test_active_project_fallback(self):
        """Verifies that omitting project_id uses the active project."""
        res = ToolRouter.dispatch("project_assessment", {"sections": ["project"]})
        self.assertEqual(res["project_id"], self.project_id)

    def test_invalid_project_id_raises_value_error(self):
        """Verifies that non-existent project_id raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            ToolRouter.dispatch("project_assessment", {"project_id": "proj_nonexistent_99999"})
        self.assertIn("not found", str(ctx.exception))

    def test_invalid_sections_parameter_raises_value_error(self):
        """Verifies that non-list sections parameter raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            ToolRouter.dispatch("project_assessment", {"project_id": self.project_id, "sections": "invalid_string_not_list"})
        self.assertIn("must be a list", str(ctx.exception))
