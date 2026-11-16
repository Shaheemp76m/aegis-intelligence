"""Aegis Intelligence - Asynchronous Background Job Tests

Comprehensive verification suite covering:
1. Short command execution.
2. Simulated long-running background command.
3. Successful build execution and log capture.
4. Failed build execution and exit code recording.
5. Job cancellation via process group termination.
6. Configured execution timeout enforcement.
7. Backend restart recovery for orphaned/crashed jobs.
8. Asynchronous Telegram completion notification dispatch.
9. Duplicate job prevention and concurrency guards.
10. Path validation and forbidden command protection.
"""

import os
import sys
import time
import json
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from tests.isolated_test_case import IsolatedTestCase
from config import Config
from storage.database import db_session
from intelligence.project_analyzer import ProjectAnalyzer
from core.execution_manager import ExecutionManager, is_process_running
from security.path_validator import PathValidationError


class TestAsyncJobs(IsolatedTestCase):
    """Test suite for asynchronous background job execution and lifecycle management."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # Create a sample project directory within the isolated temporary directory
        cls.project_dir = Path(cls._temp_dir) / "test_repo"
        cls.project_dir.mkdir(parents=True, exist_ok=True)

        # Register the project
        cls.project = ProjectAnalyzer.register_project(
            name="Test Async Repo",
            path=str(cls.project_dir),
            description="Isolated repository for async job testing"
        )
        cls.project_id = cls.project["id"]

    def setUp(self):
        super().setUp()
        # Ensure jobs directory exists
        Config.JOBS_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        # Cancel any leftover processes
        with ExecutionManager._lock:
            for jid, proc in list(ExecutionManager._active_processes.items()):
                try:
                    proc.kill()
                except Exception:
                    pass
            ExecutionManager._active_processes.clear()
            ExecutionManager._active_pgids.clear()
            ExecutionManager._monitor_threads.clear()
        super().tearDown()

    def test_01_short_command_execution(self):
        """Test short background command execution and exit code recording."""
        cmd = [sys.executable, "-c", "print('hello from background job')"]
        res = ExecutionManager.start_job(
            command=cmd,
            project_id=self.project_id
        )

        self.assertIn("job_id", res)
        self.assertEqual(res["status"], "running")
        job_id = res["job_id"]

        # Wait for the monitor thread to finish execution
        time.sleep(1.0)

        job = ExecutionManager.get_job(job_id)
        self.assertIsNotNone(job)
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["exit_code"], 0)
        self.assertIn("hello from background job", job["stdout"])
        self.assertGreater(job["duration"], 0.0)
        self.assertIsNotNone(job["finished_at"])

    def test_02_simulated_long_running_command(self):
        """Test that long-running commands return immediately without blocking."""
        cmd = [sys.executable, "-c", "import time; time.sleep(0.6); print('long work done')"]
        start_t = time.perf_counter()
        res = ExecutionManager.start_job(
            command=cmd,
            project_id=self.project_id
        )
        dispatch_duration = time.perf_counter() - start_t

        # Must return in under 200ms
        self.assertLess(dispatch_duration, 0.25)
        self.assertEqual(res["status"], "running")
        job_id = res["job_id"]

        # Check job status while running
        job_running = ExecutionManager.get_job(job_id)
        self.assertIn(job_running["status"], ("running", "completed"))

        # Wait for process completion (up to 3 seconds)
        job_done = None
        for _ in range(30):
            time.sleep(0.1)
            job_done = ExecutionManager.get_job(job_id)
            if job_done["status"] != "running":
                break

        self.assertIsNotNone(job_done)
        self.assertEqual(job_done["status"], "completed")
        self.assertEqual(job_done["exit_code"], 0)
        self.assertIn("long work done", job_done["stdout"])

    def test_03_successful_build(self):
        """Test successful build command execution and log retrieval."""
        build_script = self.project_dir / "build.py"
        build_script.write_text("print('Vite v5.0.0 building for production...'); print('✓ 45 modules transformed.'); print('✓ built in 120ms.')")

        cmd = [sys.executable, "build.py"]
        res = ExecutionManager.start_job(
            command=cmd,
            project_id=self.project_id,
            action="build"
        )
        job_id = res["job_id"]
        time.sleep(1.0)

        job = ExecutionManager.get_job(job_id)
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["exit_code"], 0)
        self.assertEqual(job["action"], "build")

        # Test log retrieval
        logs = ExecutionManager.get_job_logs(job_id, lines=10)
        self.assertEqual(logs["job_id"], job_id)
        self.assertIn("Vite v5.0.0 building", logs["logs"])
        self.assertIn("built in 120ms", logs["logs"])

    def test_04_failed_build(self):
        """Test failed build execution and error capture."""
        cmd = [sys.executable, "-c", "import sys; sys.stderr.write('ModuleNotFoundError: missing asset\\n'); sys.exit(2)"]
        res = ExecutionManager.start_job(
            command=cmd,
            project_id=self.project_id,
            action="build"
        )
        job_id = res["job_id"]
        for _ in range(30):
            time.sleep(0.1)
            job = ExecutionManager.get_job(job_id)
            if job["status"] != "running":
                break

        self.assertEqual(job["status"], "failed")
        self.assertEqual(job["exit_code"], 2)
        self.assertIn("missing asset", job["stdout"])
        self.assertIn("non-zero return code 2", job["error"])

    def test_05_job_cancellation(self):
        """Test cancelling a running job via process group termination."""
        cmd = [sys.executable, "-c", "import time; time.sleep(15)"]
        res = ExecutionManager.start_job(
            command=cmd,
            project_id=self.project_id
        )
        job_id = res["job_id"]
        time.sleep(0.3)

        # Cancel the job
        cancel_res = ExecutionManager.cancel_job(job_id)
        self.assertTrue(cancel_res["success"])
        self.assertEqual(cancel_res["status"], "cancelled")

        job = ExecutionManager.get_job(job_id)
        self.assertEqual(job["status"], "cancelled")
        self.assertEqual(job["exit_code"], -15)
        self.assertIn("cancelled", job["error"].lower())

    def test_06_command_timeout_enforcement(self):
        """Test that a command exceeding its timeout is killed and marked timed_out."""
        cmd = [sys.executable, "-c", "import time; time.sleep(10)"]
        res = ExecutionManager.start_job(
            command=cmd,
            project_id=self.project_id,
            timeout=1  # 1-second timeout
        )
        job_id = res["job_id"]

        # Wait 2.2s for timeout enforcement and cleanup
        time.sleep(2.2)

        job = ExecutionManager.get_job(job_id)
        self.assertEqual(job["status"], "timed_out")
        self.assertIn("timed out", job["error"].lower())

    def test_07_backend_restart_recovery(self):
        """Test recovery of orphaned/interrupted jobs when the backend restarts."""
        # Insert a job with status='running' and a dead PID
        dead_job_id = "job_dead_restart_test"
        now_iso = "2026-11-14T10:00:00+00:00"
        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO execution_jobs (
                    id, project_id, action, prompt, status, pid, pgid,
                    command, created_at, started_at
                ) VALUES (?, ?, 'command', 'npm run build', 'running', 9999999, 9999999, 'npm run build', ?, ?)
                """,
                (dead_job_id, self.project_id, now_iso, now_iso)
            )

        recovered_count = ExecutionManager.recover_jobs()
        self.assertGreaterEqual(recovered_count, 1)

        job = ExecutionManager.get_job(dead_job_id)
        self.assertEqual(job["status"], "failed")
        self.assertIn("terminated during server restart", job["error"])
        self.assertIsNotNone(job["finished_at"])

    @patch("core.execution_manager.send_telegram_message")
    def test_08_telegram_completion_notification(self, mock_send_tg):
        """Test that finished background jobs dispatch independent Telegram notifications."""
        mock_send_tg.return_value = True
        cmd = [sys.executable, "-c", "print('Build output complete')"]
        res = ExecutionManager.start_job(
            command=cmd,
            project_id=self.project_id,
            telegram_chat_id="5170203589"
        )
        job_id = res["job_id"]
        time.sleep(1.0)

        mock_send_tg.assert_called_once()
        call_args = mock_send_tg.call_args[0]
        self.assertEqual(call_args[0], "5170203589")
        message_body = call_args[1]
        self.assertIn("Background Job COMPLETED", message_body)
        self.assertIn(job_id, message_body)
        self.assertIn("Build output complete", message_body)

    def test_09_duplicate_job_prevention(self):
        """Test that starting an identical command while running returns the existing job."""
        cmd = [sys.executable, "-c", "import time; time.sleep(2.0)"]
        res1 = ExecutionManager.start_job(command=cmd, project_id=self.project_id)
        res2 = ExecutionManager.start_job(command=cmd, project_id=self.project_id)

        self.assertEqual(res1["job_id"], res2["job_id"])
        self.assertTrue(res2.get("already_running", False))

        ExecutionManager.cancel_job(res1["job_id"])

    def test_10_security_path_and_command_validation(self):
        """Test security validation against dangerous commands and out-of-bounds paths."""
        # 1. Prohibited catastrophic command
        with self.assertRaises(PermissionError):
            ExecutionManager.start_job(command="rm -rf /", project_id=self.project_id)

        # 2. Path traversal working directory
        with self.assertRaises(PathValidationError):
            ExecutionManager.start_job(
                command=[sys.executable, "-c", "print('out')"],
                project_id=self.project_id,
                cwd="../../../../../etc"
            )

        # 3. Empty command
        with self.assertRaises(ValueError):
            ExecutionManager.start_job(command="", project_id=self.project_id)


if __name__ == "__main__":
    unittest.main()
