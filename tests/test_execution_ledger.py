"""Aegis Intelligence - Execution Ledger & Loop Safeguards Test Suite

Verifies:
1. Repeated identical read-only action returns cached result without re-execution.
2. Same action with different parameters executes normally.
3. Concurrent duplicate requests handled safely without race conditions.
4. Failed action followed by legitimate retry is allowed.
5. State-changing actions are not incorrectly blocked.
6. Repeated identical action hitting threshold triggers stagnation stop cleanly.
7. Configurable execution limits (total actions, consecutive failures, timeout) enforced.
8. Session continuation across separate Telegram messages.
"""

import time
import json
import threading
from unittest.mock import patch

from tests.isolated_test_case import IsolatedTestCase
from storage.database import db_session
from core.tool_router import ToolRouter
from core.execution_ledger import ExecutionLedger
from intelligence.project_analyzer import ProjectAnalyzer
from intelligence.task_manager import TaskManager
from intelligence.session_manager import SessionManager

class TestExecutionLedger(IsolatedTestCase):
    """Test suite for execution ledger, deduplication, stagnation, and execution limits."""

    def setUp(self):
        super().setUp()
        # Clean ledger and session tables before each test
        with db_session() as conn:
            conn.execute("DELETE FROM execution_ledger")
            conn.execute("DELETE FROM conversation_sessions")
            conn.execute("DELETE FROM processed_telegram_messages")
            conn.execute("DELETE FROM tasks")
            conn.execute("DELETE FROM projects")

        # Register a base test project
        self.proj_dir = self._temp_data_dir / "test_project_alpha"
        self.proj_dir.mkdir(parents=True, exist_ok=True)
        (self.proj_dir / "app.py").write_text("print('hello')", encoding="utf-8")
        self.project = ProjectAnalyzer.register_project(
            name="Alpha Project",
            path=str(self.proj_dir),
            description="Alpha test project"
        )
        self.project_id = self.project["id"]

        # Register a second test project for parameter variation testing
        self.proj_dir2 = self._temp_data_dir / "test_project_beta"
        self.proj_dir2.mkdir(parents=True, exist_ok=True)
        (self.proj_dir2 / "main.py").write_text("print('beta')", encoding="utf-8")
        self.project2 = ProjectAnalyzer.register_project(
            name="Beta Project",
            path=str(self.proj_dir2),
            description="Beta test project"
        )
        self.project_id2 = self.project2["id"]

    def test_01_repeated_identical_action_returns_cached_without_reexecution(self):
        """Scenario 1: Repeated identical read-only action returns stored result without re-execution."""
        exec_id = "exec_scen_1"

        # First call: executes normally
        with patch.object(ProjectAnalyzer, "list_projects", wraps=ProjectAnalyzer.list_projects) as mock_list:
            res1 = ToolRouter.dispatch("project_list", {}, execution_id=exec_id)
            self.assertEqual(mock_list.call_count, 1)
            self.assertIsInstance(res1, list)
            self.assertEqual(len(res1), 2)

            # Second call: identical parameters within same execution_id
            res2 = ToolRouter.dispatch("project_list", {}, execution_id=exec_id)
            # Must NOT call ProjectAnalyzer.list_projects again!
            self.assertEqual(mock_list.call_count, 1)
            # Result returned must match exactly
            self.assertEqual(res2, res1)

        # Check ledger record
        progress = ExecutionLedger.get_execution_progress(exec_id)
        self.assertEqual(progress["total_actions"], 1)
        self.assertEqual(progress["repeated_calls_count"], 1)
        self.assertFalse(progress["is_stagnant"])

    def test_02_same_action_with_different_parameters_executes_normally(self):
        """Scenario 2: Same action with different parameters executes normally."""
        exec_id = "exec_scen_2"

        res1 = ToolRouter.dispatch("project_get", {"project_id": self.project_id}, execution_id=exec_id)
        res2 = ToolRouter.dispatch("project_get", {"project_id": self.project_id2}, execution_id=exec_id)

        self.assertIsNotNone(res1)
        self.assertIsNotNone(res2)
        self.assertEqual(res1["id"], self.project_id)
        self.assertEqual(res2["id"], self.project_id2)

        progress = ExecutionLedger.get_execution_progress(exec_id)
        self.assertEqual(progress["total_actions"], 2)
        self.assertEqual(progress["succeeded_actions"], 2)
        self.assertEqual(progress["repeated_calls_count"], 0)

    def test_03_concurrent_duplicate_requests_handled_safely(self):
        """Scenario 3: Concurrent duplicate requests handled safely without race conditions."""
        exec_id = "exec_scen_3"
        sig = ExecutionLedger.compute_action_signature("project_list", {})

        # Manually acquire in-flight lock to simulate an active running action
        with ExecutionLedger._lock:
            ExecutionLedger._in_flight_locks.add((exec_id, sig))

        try:
            # Second concurrent call arrives while the first is in-flight
            res = ToolRouter.dispatch("project_list", {}, execution_id=exec_id)
            self.assertIsInstance(res, dict)
            self.assertEqual(res.get("status"), "BLOCKED")
            self.assertEqual(res.get("reason"), "CONCURRENT_DUPLICATE")
            self.assertIn("already executing concurrently", res.get("message", ""))
        finally:
            with ExecutionLedger._lock:
                ExecutionLedger._in_flight_locks.discard((exec_id, sig))

    def test_04_failed_action_followed_by_legitimate_retry(self):
        """Scenario 4: Failed action followed by legitimate retry is allowed."""
        exec_id = "exec_scen_4"

        # First call fails due to non-existent project
        with self.assertRaises(ValueError):
            ToolRouter.dispatch("project_get", {"project_id": "proj_non_existent_999"}, execution_id=exec_id)

        # Check ledger recorded failure
        norm = ExecutionLedger.normalize_parameters({"project_id": "proj_non_existent_999"})
        sig = ExecutionLedger.compute_action_signature("project_get", norm)
        rec = ExecutionLedger.get_action_record(exec_id, sig)
        self.assertIsNotNone(rec)
        self.assertEqual(rec["execution_status"], "failed")
        self.assertIn("not found", rec["error_message"])

        # Legitimate retry with valid project ID succeeds
        res = ToolRouter.dispatch("project_get", {"project_id": self.project_id}, execution_id=exec_id)
        self.assertEqual(res["id"], self.project_id)

        progress = ExecutionLedger.get_execution_progress(exec_id)
        self.assertEqual(progress["failed_actions"], 1)
        self.assertEqual(progress["succeeded_actions"], 1)

    def test_05_state_changing_actions_not_blocked_incorrectly(self):
        """Scenario 5: State-changing actions are not blocked incorrectly."""
        exec_id = "exec_scen_5"

        # Create Task 1
        t1 = ToolRouter.dispatch("task_create", {
            "project_id": self.project_id,
            "title": "First Mutating Task"
        }, execution_id=exec_id)
        self.assertIsNotNone(t1.get("id"))

        # Create Task 2 (same tool, different params)
        t2 = ToolRouter.dispatch("task_create", {
            "project_id": self.project_id,
            "title": "Second Mutating Task"
        }, execution_id=exec_id)
        self.assertIsNotNone(t2.get("id"))
        self.assertNotEqual(t1["id"], t2["id"])

        # Update Task 1 status to in_progress
        u1 = ToolRouter.dispatch("task_update", {
            "task_id": t1["id"],
            "status": "in_progress"
        }, execution_id=exec_id)
        self.assertEqual(u1["status"], "in_progress")

        # Update Task 1 status to completed (state-changing, not blocked)
        u2 = ToolRouter.dispatch("task_update", {
            "task_id": t1["id"],
            "status": "completed"
        }, execution_id=exec_id)
        self.assertEqual(u2["status"], "completed")

        progress = ExecutionLedger.get_execution_progress(exec_id)
        self.assertEqual(progress["succeeded_actions"], 4)
        self.assertFalse(progress["is_stagnant"])

    def test_06_repeated_identical_action_hitting_threshold_triggers_stagnation_stop(self):
        """Scenario 6: Repeated identical action hitting threshold triggers stagnation stop cleanly."""
        exec_id = "exec_scen_6"

        # Mock max_repeated_actions to 2 for this test
        with patch("config.Config.LEDGER_MAX_REPEATED_ACTIONS", 2):
            # Attempt 1: Success (initial query)
            res1 = ToolRouter.dispatch("project_list", {}, execution_id=exec_id)
            self.assertIsInstance(res1, list)

            # Attempt 2: Cached return (under limit)
            res2 = ToolRouter.dispatch("project_list", {}, execution_id=exec_id)
            self.assertEqual(res2, res1)

            # Attempt 3: Hits stagnation limit (3 > 2)!
            res3 = ToolRouter.dispatch("project_list", {}, execution_id=exec_id)
            self.assertIsInstance(res3, dict)
            self.assertEqual(res3.get("status"), "STAGNATION_DETECTED")
            self.assertTrue(res3.get("halted"))
            self.assertEqual(res3.get("limit_type"), "max_repeated_actions")
            self.assertIn("Repeated action limit reached", res3.get("message", ""))
            self.assertEqual(res3.get("attempt_count"), 3)
            self.assertEqual(res3.get("cached_data"), res1)

            # Verify progress shows stagnation
            progress = ExecutionLedger.get_execution_progress(exec_id)
            self.assertTrue(progress["is_stagnant"])
            self.assertIn("repeated 3 times", progress["stagnation_reason"])

    def test_07_configurable_execution_limits_enforced(self):
        """Scenario 7: Configurable execution limits (total actions, consecutive failures, timeout) enforced."""
        # 7A: Max Total Actions
        exec_total = "exec_limit_total"
        with patch("config.Config.LEDGER_MAX_TOTAL_ACTIONS", 3):
            # Run 3 distinct actions
            ToolRouter.dispatch("project_list", {}, execution_id=exec_total)
            ToolRouter.dispatch("system_health", {}, execution_id=exec_total)
            ToolRouter.dispatch("project_get", {"project_id": self.project_id}, execution_id=exec_total)

            # 4th action exceeds total limit
            res_exceeded = ToolRouter.dispatch("project_get", {"project_id": self.project_id2}, execution_id=exec_total)
            self.assertIsInstance(res_exceeded, dict)
            self.assertEqual(res_exceeded.get("status"), "LIMIT_EXCEEDED")
            self.assertEqual(res_exceeded.get("limit_type"), "max_total_actions")
            self.assertTrue(res_exceeded.get("halted"))
            self.assertIn("exceeded maximum total actions limit", res_exceeded.get("message", ""))

        # 7B: Max Consecutive Failures
        exec_fail = "exec_limit_fail"
        with patch("config.Config.LEDGER_MAX_CONSECUTIVE_FAILURES", 2):
            # Failure 1
            try:
                ToolRouter.dispatch("task_get", {"task_id": "tsk_missing_1"}, execution_id=exec_fail)
            except Exception:
                pass
            # Failure 2
            try:
                ToolRouter.dispatch("task_get", {"task_id": "tsk_missing_2"}, execution_id=exec_fail)
            except Exception:
                pass

            # 3rd action should be halted due to consecutive failures
            res_fail_limit = ToolRouter.dispatch("project_list", {}, execution_id=exec_fail)
            self.assertIsInstance(res_fail_limit, dict)
            self.assertEqual(res_fail_limit.get("status"), "LIMIT_EXCEEDED")
            self.assertEqual(res_fail_limit.get("limit_type"), "max_consecutive_failures")
            self.assertTrue(res_fail_limit.get("halted"))

        # 7C: Execution Timeout
        exec_timeout = "exec_limit_timeout"
        with patch("config.Config.LEDGER_EXECUTION_TIMEOUT", 1):
            # Action 1 starts clock
            ToolRouter.dispatch("system_health", {}, execution_id=exec_timeout)
            time.sleep(1.2)  # Wait beyond 1s timeout
            res_timed_out = ToolRouter.dispatch("project_list", {}, execution_id=exec_timeout)
            self.assertIsInstance(res_timed_out, dict)
            self.assertEqual(res_timed_out.get("status"), "LIMIT_EXCEEDED")
            self.assertEqual(res_timed_out.get("limit_type"), "execution_timeout")
            self.assertTrue(res_timed_out.get("halted"))

    def test_08_session_continuation_across_separate_telegram_messages(self):
        """Scenario 8: Session continuation across separate Telegram messages."""
        chat_id = "tg_chat_888"
        user_id = "tg_user_888"

        # Turn 1: User sends message 1 ("List my projects")
        sess = SessionManager.get_or_create_session(
            telegram_chat_id=chat_id,
            telegram_user_id=user_id,
            user_prompt="List my projects"
        )
        session_id = sess["session_id"]
        exec_msg_1 = f"{session_id}_msg_101"

        # Agent runs tool in turn 1
        res1 = ToolRouter.dispatch(
            "project_list",
            {},
            execution_id=exec_msg_1,
            session_id=session_id
        )
        self.assertIsInstance(res1, list)
        self.assertEqual(len(res1), 2)

        # Complete Turn 1
        SessionManager.add_turn(
            session_id=session_id,
            user_text="List my projects",
            agent_output="You have 2 projects: Alpha Project and Beta Project."
        )

        # Turn 2: User sends message 2 in the same session ("List my projects again")
        exec_msg_2 = f"{session_id}_msg_102"

        # In Turn 2, calling project_list must execute for Turn 2 (not mistakenly blocked by Turn 1's execution cache)
        with patch.object(ProjectAnalyzer, "list_projects", wraps=ProjectAnalyzer.list_projects) as mock_list:
            res2 = ToolRouter.dispatch(
                "project_list",
                {},
                execution_id=exec_msg_2,
                session_id=session_id
            )
            self.assertEqual(mock_list.call_count, 1)
            self.assertEqual(len(res2), 2)

        # Session history must show continuous context across both turns
        active_sess = SessionManager.get_active_session(chat_id, user_id)
        self.assertEqual(active_sess["id"], session_id)
        self.assertEqual(len(active_sess["context"]), 1)
        self.assertEqual(active_sess["context"][0]["user"], "List my projects")
        self.assertIn("Alpha Project and Beta Project", active_sess["context"][0]["agent"])
