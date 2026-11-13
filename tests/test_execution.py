"""Aegis Intelligence - Execution & Antigravity Integration Tests"""

import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.isolated_test_case import IsolatedTestCase
from integrations.terminal import safe_run_command, TerminalExecutionResult
from core.agy_executor import AgyExecutor
from core.execution_manager import ExecutionManager
from integrations.model_manager import ModelManager
from integrations.usage_monitor import UsageMonitor

class TestExecutionEngine(IsolatedTestCase):
    def setUp(self):
        super().setUp()
        from storage.database import db_session
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).isoformat()
        with db_session() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO projects (id, name, path, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                ("proj_sample", "Sample Exec Project", "/tmp/sample_exec_proj", now, now)
            )

    def test_safe_argument_array_prevents_injection(self):
        """Shell injection operators (;, &&, |) must NOT execute as shell commands."""
        res = safe_run_command(["echo", "hello; touch /tmp/injection_failed_test"], timeout=5)
        self.assertEqual(res.exit_code, 0)
        self.assertIn("hello; touch /tmp/injection_failed_test", res.stdout)
        self.assertFalse(os.path.exists("/tmp/injection_failed_test"))

    def test_timeout_handling(self):
        """Processes exceeding timeout are cleanly terminated with timed_out flag."""
        res = safe_run_command(["sleep", "2"], timeout=1)
        self.assertTrue(res.timed_out)
        self.assertEqual(res.exit_code, -1)
        self.assertIn("timed out", res.stderr)

    @patch("core.agy_executor.safe_run_command")
    def test_agy_executor_json_parsing(self, mock_run):
        """AgyExecutor parses structured JSON from CLI output and extracts tokens."""
        mock_run.return_value = TerminalExecutionResult(
            exit_code=0,
            stdout='{"conversation_id": "test-conv-123", "status": "SUCCESS", "response": "Completed task successfully", "duration_seconds": 2.5, "usage": {"input_tokens": 100, "output_tokens": 50, "total_tokens": 150}}',
            stderr="",
            duration_seconds=2.5,
            timed_out=False
        )

        result = AgyExecutor.execute(prompt="Write unit test", project_path="/data/data/com.termux/files/home/aegis-intelligence")
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.status, "SUCCESS")
        self.assertEqual(result.conversation_id, "test-conv-123")
        self.assertEqual(result.usage.get("total_tokens"), 150)

    @patch("core.execution_manager.AgyExecutor.execute")
    def test_execution_job_tracking(self, mock_exec):
        """ExecutionManager persists job progress and token metrics to SQLite."""
        from core.agy_executor import AgyExecutionResult
        mock_exec.return_value = AgyExecutionResult(
            exit_code=0,
            status="SUCCESS",
            response="Feature implemented",
            duration_seconds=3.1,
            conversation_id="conv-abc",
            usage={"input_tokens": 200, "output_tokens": 80, "total_tokens": 280}
        )

        job = ExecutionManager.execute_job(
            project_path="/data/data/com.termux/files/home/aegis-intelligence",
            prompt="Implement login",
            project_id="proj_sample",
            async_run=False
        )

        self.assertIsNotNone(job)
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["stdout"], "Feature implemented")
        self.assertEqual(job["token_usage"]["total_tokens"], 280)

        # Retrieve by ID
        fetched = ExecutionManager.get_job(job["id"])
        self.assertEqual(fetched["id"], job["id"])

    @patch("integrations.model_manager.safe_run_command")
    def test_model_catalog_and_families(self, mock_models_run):
        """ModelManager catalogs verified models and detects families."""
        mock_models_run.return_value = TerminalExecutionResult(
            exit_code=0,
            stdout=(
                "gemini-3.8-flash-high     Gemini 3.8 Flash (High)\n"
                "gemini-3.8-flash-medium   Gemini 3.8 Flash (Medium)\n"
                "claude-sonnet-4-6         Claude Sonnet 4.6 (Thinking)\n"
                "gpt-oss-120b-medium       GPT-OSS 120B (Medium)\n"
            ),
            stderr="",
            duration_seconds=0.1
        )
        models = ModelManager.list_models()
        self.assertTrue(len(models) > 0)
        ids = [m["id"] for m in models]
        self.assertIn("gemini-3.8-flash-high", ids)
        for m in models:
            if "gemini" in m["id"]:
                self.assertEqual(m["family"], "Gemini")
            elif "claude" in m["id"]:
                self.assertEqual(m["family"], "Claude")

    def test_usage_unsupported_quota_handling(self):
        """Account quota status must be explicitly marked 'unsupported'."""
        usage = UsageMonitor.get_usage_summary()
        self.assertEqual(usage["account_quota"]["status"], "unsupported")
        self.assertEqual(usage["account_quota"]["remaining_quota"], "unavailable")
        self.assertEqual(usage["local_session_usage"]["status"], "supported")

if __name__ == "__main__":
    unittest.main()
