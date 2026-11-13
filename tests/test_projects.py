"""Aegis Intelligence - Multi-Project Intelligence Tests"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import Config
from storage.database import init_db
from intelligence.project_analyzer import ProjectAnalyzer
from integrations.filesystem import FilesystemIntegration

class TestProjectIntelligence(unittest.TestCase):
    def setUp(self):
        init_db()
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.proj_path = self.tmp_dir.name

        # Create sample project files
        with open(os.path.join(self.proj_path, "package.json"), "w") as f:
            f.write('{"name": "test-pkg", "dependencies": {"react": "^18.0.0", "typescript": "^5.0.0"}}')
        with open(os.path.join(self.proj_path, "README.md"), "w") as f:
            f.write("# Test Project Documentation")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_project_registration_and_retrieval(self):
        """Register project, verify persisted fields, stack detection, and retrieval."""
        registered = ProjectAnalyzer.register_project(
            name="Sample App",
            path=self.proj_path,
            description="A test project"
        )
        pid = registered["id"]
        self.assertTrue(pid.startswith("proj_"))
        self.assertEqual(registered["name"], "Sample App")
        self.assertEqual(registered["description"], "A test project")
        self.assertIn("TypeScript", registered["languages"])
        self.assertIn("React", registered["tech_stack"])

        # Fetch by ID
        fetched = ProjectAnalyzer.get_project(pid)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched["id"], pid)

    def test_set_active_project(self):
        """Setting active project sets is_active flag."""
        p1 = ProjectAnalyzer.register_project("P1", self.proj_path)
        ProjectAnalyzer.set_active_project(p1["id"])
        active = ProjectAnalyzer.get_active_project()
        self.assertEqual(active["id"], p1["id"])

    def test_project_update(self):
        """Updating metadata modifies name and description."""
        p = ProjectAnalyzer.register_project("Old Name", self.proj_path)
        updated = ProjectAnalyzer.update_project(p["id"], name="New Name", description="Updated desc")
        self.assertEqual(updated["name"], "New Name")
        self.assertEqual(updated["description"], "Updated desc")

    def test_unregister_preserves_files(self):
        """Unregistering removes database record without deleting files from disk."""
        p = ProjectAnalyzer.register_project("Preserve Test", self.proj_path)
        pid = p["id"]

        # Ensure README exists
        readme_path = os.path.join(self.proj_path, "README.md")
        self.assertTrue(os.path.exists(readme_path))

        # Unregister
        removed = ProjectAnalyzer.remove_project(pid)
        self.assertTrue(removed)

        # Confirm database record is gone
        self.assertIsNone(ProjectAnalyzer.get_project(pid))

        # Physical file MUST still exist intact
        self.assertTrue(os.path.exists(readme_path))

    def test_compare_projects(self):
        """Comparing projects returns structured side-by-side metrics."""
        p = ProjectAnalyzer.register_project("Comp App", self.proj_path)
        comparison = ProjectAnalyzer.compare_projects([p["id"]])
        self.assertEqual(len(comparison), 1)
        self.assertEqual(comparison[0]["id"], p["id"])
        self.assertIn("task_summary", comparison[0])

if __name__ == "__main__":
    unittest.main()
