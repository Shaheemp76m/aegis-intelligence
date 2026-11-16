"""Aegis Intelligence - Comprehensive Dispatcher Coverage Tests

Verifies all 48 dispatcher actions, alias normalization, parameter validation,
risk gating, and path traversal protection against an isolated test database.
"""

import os
import sys
import subprocess
from tests.isolated_test_case import IsolatedTestCase
from core.tool_router import ToolRouter
from security.approvals import ApprovalRequiredException, decide_approval, create_approval_request
from intelligence.project_analyzer import ProjectAnalyzer
from storage.database import db_session

class TestDispatcherCoverage(IsolatedTestCase):
    """Exhaustive test suite for unified POST /api/v1/tools/dispatch coverage."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a sample project directory inside the isolated temp dir
        cls.proj_dir = os.path.join(cls._temp_dir, "test_repo")
        os.makedirs(cls.proj_dir, exist_ok=True)

        # Initialize git repo in sample project
        subprocess.run(["git", "init"], cwd=cls.proj_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "TestUser"], cwd=cls.proj_dir, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@aegis.local"], cwd=cls.proj_dir, check=True, capture_output=True)

        # Create a test file
        test_file = os.path.join(cls.proj_dir, "README.md")
        with open(test_file, "w") as f:
            f.write("# Sample Project\nInitial commit content.\n")

        subprocess.run(["git", "add", "."], cwd=cls.proj_dir, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=cls.proj_dir, check=True, capture_output=True)

        # Register the sample project
        cls.proj = ProjectAnalyzer.register_project(
            name="Test Dispatcher Project",
            path=cls.proj_dir,
            description="Project created for dispatcher coverage testing"
        )
        cls.project_id = cls.proj["id"]
        ProjectAnalyzer.set_active_project(cls.project_id)

    # ==================== 1. Project Management ====================

    def test_project_list(self):
        res = ToolRouter.dispatch("project_list")
        self.assertIsInstance(res, list)
        self.assertGreaterEqual(len(res), 1)

    def test_project_get(self):
        res = ToolRouter.dispatch("project_get", {"project_id": self.project_id})
        self.assertEqual(res["id"], self.project_id)
        self.assertIn("counts", res)

    def test_project_update(self):
        res = ToolRouter.dispatch("project_update", {
            "project_id": self.project_id,
            "description": "Updated project description"
        })
        self.assertEqual(res["description"], "Updated project description")

    def test_project_inspect(self):
        res = ToolRouter.dispatch("project_inspect", {"project_id": self.project_id})
        self.assertIn("git", res)
        self.assertIn("filesystem", res)

    def test_project_assessment(self):
        res = ToolRouter.dispatch("project_assessment", {"project_id": self.project_id})
        self.assertIn("project", res)
        self.assertIn("git", res)
        self.assertIn("tasks", res)
        self.assertIn("bugs", res)
        self.assertIn("health", res)

    def test_project_context(self):
        res = ToolRouter.dispatch("project_context", {"project_id": self.project_id})
        self.assertIn("context", res)
        self.assertIn("Test Dispatcher Project", res["context"])

    def test_project_set_active(self):
        res = ToolRouter.dispatch("project_set_active", {"project_id": self.project_id})
        self.assertEqual(res["id"], self.project_id)

    def test_project_compare(self):
        res = ToolRouter.dispatch("project_compare", {"project_ids": [self.project_id]})
        self.assertIsInstance(res, list)

    def test_project_delete_gated_and_executed(self):
        # Register a disposable project to test deletion
        disp_dir = os.path.join(self._temp_dir, "disp_repo")
        os.makedirs(disp_dir, exist_ok=True)
        subprocess.run(["git", "init"], cwd=disp_dir, check=True, capture_output=True)
        disp_proj = ProjectAnalyzer.register_project(name="Disposable", path=disp_dir)
        disp_id = disp_proj["id"]

        # 1. Unapproved invocation must raise ApprovalRequiredException
        with self.assertRaises(ApprovalRequiredException) as ctx:
            ToolRouter.dispatch("project_delete", {"project_id": disp_id})
        approval_id = ctx.exception.approval_id
        self.assertTrue(approval_id.startswith("appr_"))

        # 2. Approve via decision
        decide_approval(approval_id, decision="APPROVED", reason="Test authorization")

        # 3. Re-dispatch with approval token
        res = ToolRouter.dispatch("project_delete", {"project_id": disp_id}, approval_id=approval_id)
        self.assertTrue(res.get("unregistered"))
        self.assertEqual(res.get("project_id"), disp_id)

        # 4. Confirm project no longer in database
        self.assertIsNone(ProjectAnalyzer.get_project(disp_id))

    # ==================== 2. Health & Diagnostics ====================

    def test_system_health(self):
        res = ToolRouter.dispatch("system_health")
        self.assertEqual(res["status"], "healthy")
        self.assertEqual(res["database"], "connected")
        self.assertEqual(res["service"], "aegis-intelligence")

    def test_development_health(self):
        res = ToolRouter.dispatch("development_health", {"project_id": self.project_id})
        self.assertIn("verified_facts", res)
        self.assertIn("inferred_conclusions", res)
        self.assertIn("git_state", res)

    def test_report_generate(self):
        res = ToolRouter.dispatch("report_generate", {"report_type": "status", "project_id": self.project_id})
        self.assertIn("report", res)

    # ==================== 3. Tasks ====================

    def test_task_lifecycle(self):
        # Create
        task = ToolRouter.dispatch("task_create", {
            "project_id": self.project_id,
            "title": "Coverage Test Task",
            "priority": "high",
            "description": "Task created by test suite"
        })
        task_id = task["id"]
        self.assertEqual(task["title"], "Coverage Test Task")

        # Get
        fetched = ToolRouter.dispatch("task_get", {"task_id": task_id})
        self.assertEqual(fetched["id"], task_id)

        # Update
        updated = ToolRouter.dispatch("task_update", {"task_id": task_id, "priority": "critical"})
        self.assertEqual(updated["priority"], "critical")

        # Complete
        completed = ToolRouter.dispatch("task_complete", {"task_id": task_id, "notes": "Done"})
        self.assertEqual(completed["status"], "completed")

        # List
        tasks = ToolRouter.dispatch("task_list", {"project_id": self.project_id})
        self.assertTrue(any(t["id"] == task_id for t in tasks))

        # Summary
        summary = ToolRouter.dispatch("task_summary", {"project_id": self.project_id})
        self.assertIn("total", summary)

        # Overdue
        overdue = ToolRouter.dispatch("task_overdue", {"project_id": self.project_id})
        self.assertIsInstance(overdue, list)

        # Delete
        del_res = ToolRouter.dispatch("task_delete", {"task_id": task_id})
        self.assertTrue(del_res["deleted"])

    # ==================== 4. Bugs ====================

    def test_bug_lifecycle(self):
        # Create
        bug = ToolRouter.dispatch("bug_create", {
            "project_id": self.project_id,
            "title": "Coverage Test Bug",
            "severity": "medium",
            "reproduction_steps": "Step 1"
        })
        bug_id = bug["id"]
        self.assertEqual(bug["title"], "Coverage Test Bug")

        # Get
        fetched = ToolRouter.dispatch("bug_get", {"bug_id": bug_id})
        self.assertEqual(fetched["id"], bug_id)

        # Update
        updated = ToolRouter.dispatch("bug_update", {"bug_id": bug_id, "diagnosis": "Root cause identified"})
        self.assertEqual(updated["diagnosis"], "Root cause identified")

        # Resolve
        resolved = ToolRouter.dispatch("bug_resolve", {"bug_id": bug_id, "resolution": "Fixed", "verified": True})
        self.assertEqual(resolved["verification_status"], "verified_fixed")

        # List
        bugs = ToolRouter.dispatch("bug_list", {"project_id": self.project_id})
        self.assertTrue(any(b["id"] == bug_id for b in bugs))

        # Summary
        summary = ToolRouter.dispatch("bug_summary", {"project_id": self.project_id})
        self.assertIn("total", summary)

        # Delete
        del_res = ToolRouter.dispatch("bug_delete", {"bug_id": bug_id})
        self.assertTrue(del_res["deleted"])

    # ==================== 5. Persistent Memory ====================

    def test_memory_lifecycle(self):
        # Record
        mem = ToolRouter.dispatch("memory_record", {
            "project_id": self.project_id,
            "title": "Architecture Fact",
            "content": "Aegis runs SQLite with WAL mode.",
            "category": "architecture"
        })
        mem_id = mem["id"]
        self.assertEqual(mem["title"], "Architecture Fact")

        # Get
        fetched = ToolRouter.dispatch("memory_get", {"memory_id": mem_id})
        self.assertEqual(fetched["id"], mem_id)

        # Update
        updated = ToolRouter.dispatch("memory_update", {"memory_id": mem_id, "content": "Updated SQLite architecture content"})
        self.assertEqual(updated["content"], "Updated SQLite architecture content")

        # Search
        results = ToolRouter.dispatch("memory_search", {"project_id": self.project_id, "query": "SQLite"})
        self.assertTrue(any(m["id"] == mem_id for m in results))

        # Delete
        del_res = ToolRouter.dispatch("memory_delete", {"memory_id": mem_id})
        self.assertTrue(del_res["deleted"])

    # ==================== 6. Git & Filesystem ====================

    def test_git_operations(self):
        status = ToolRouter.dispatch("git_status", {"project_id": self.project_id})
        self.assertTrue(status["is_git"])

        commits = ToolRouter.dispatch("git_commits", {"project_id": self.project_id, "count": 5})
        self.assertGreaterEqual(len(commits), 1)

        diff = ToolRouter.dispatch("git_diff", {"project_id": self.project_id})
        self.assertIn("diff", diff)

        contributors = ToolRouter.dispatch("git_contributors", {"project_id": self.project_id})
        self.assertIsInstance(contributors, list)

    def test_filesystem_operations(self):
        read_res = ToolRouter.dispatch("file_read", {"project_id": self.project_id, "path": "README.md"})
        self.assertIn("Sample Project", read_res["content"])

        tree = ToolRouter.dispatch("filesystem_inspect", {"project_id": self.project_id, "max_depth": 2})
        self.assertIn("tree_sample", tree)
        self.assertGreaterEqual(tree["total_files"], 1)

        recent = ToolRouter.dispatch("filesystem_recent_files", {"project_id": self.project_id, "limit": 5})
        self.assertIsInstance(recent, list)
        self.assertTrue(any(f["path"] == "README.md" for f in recent))

    def test_path_traversal_blocked(self):
        from security.path_validator import PathValidationError
        with self.assertRaises(PathValidationError):
            ToolRouter.dispatch("file_read", {"project_id": self.project_id, "path": "../../etc/hosts"})

    # ==================== 7. Antigravity & Jobs ====================

    def test_antigravity_and_jobs(self):
        models = ToolRouter.dispatch("agy_models_list")
        self.assertIn("models", models)

        usage = ToolRouter.dispatch("agy_usage_summary")
        self.assertIn("local_session_usage", usage)
        self.assertIn("account_quota", usage)

        jobs = ToolRouter.dispatch("job_list", {"project_id": self.project_id})
        self.assertIsInstance(jobs, list)

        # Test job_start, job_get, job_logs, and job_cancel via dispatcher
        start_res = ToolRouter.dispatch(
            "job_start",
            {"project_id": self.project_id, "command": [sys.executable, "-c", "import time; time.sleep(0.5); print('dispatcher job done')"]}
        )
        self.assertEqual(start_res["status"], "running")
        jid = start_res["job_id"]

        job_info = ToolRouter.dispatch("job_get", {"job_id": jid})
        self.assertEqual(job_info["job_id"], jid)

        job_logs = ToolRouter.dispatch("job_logs", {"job_id": jid, "lines": 5})
        self.assertIn("job_id", job_logs)

        cancel_res = ToolRouter.dispatch("job_cancel", {"job_id": jid})
        self.assertIn("status", cancel_res)

    # ==================== 8. Approvals & Audit ====================

    def test_approvals_and_audit(self):
        # Create an approval
        appr = create_approval_request(action="test_action", risk_classification="HIGH", reason="Test approval")
        appr_id = appr["id"]

        # Get
        fetched = ToolRouter.dispatch("approval_get", {"approval_id": appr_id})
        self.assertEqual(fetched["id"], appr_id)

        # List
        apprs = ToolRouter.dispatch("approval_list")
        self.assertTrue(any(a["id"] == appr_id for a in apprs))

        # Decide
        decided = ToolRouter.dispatch("approval_decide", {"approval_id": appr_id, "decision": "APPROVED"})
        self.assertEqual(decided["status"], "APPROVED")

        # Audit logs
        logs = ToolRouter.dispatch("audit_logs_get", {"limit": 10})
        self.assertIsInstance(logs, list)

    # ==================== 9. Alias Normalization ====================

    def test_alias_normalization(self):
        # list_tasks -> task_list
        tasks = ToolRouter.dispatch("list_tasks", {"project_id": self.project_id})
        self.assertIsInstance(tasks, list)

        # inspect_project -> project_inspect
        inspect = ToolRouter.dispatch("inspect_project", {"project_id": self.project_id})
        self.assertIn("git", inspect)

        # get_project -> project_get
        p = ToolRouter.dispatch("get_project", {"project_id": self.project_id})
        self.assertEqual(p["id"], self.project_id)

        # health_check -> system_health
        health = ToolRouter.dispatch("health_check")
        self.assertEqual(health["status"], "healthy")

    # ==================== 10. Unknown Tool Handling ====================

    def test_unknown_tool_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            ToolRouter.dispatch("completely_nonexistent_tool_xyz")
        self.assertIn("Unknown tool name", str(ctx.exception))
