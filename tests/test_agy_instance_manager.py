"""Aegis Intelligence - Antigravity Instance Manager & Control Plane Tests

Verification suite covering:
1. Live instance discovery via /proc scanning and historical SQLite reconciliation.
2. Starting an Antigravity background instance with process group isolation.
3. Querying instance status by PID and by instance_id.
4. Retrieving instance output logs and tail line slicing.
5. Safe instance termination with security verification against non-Agy PIDs.
6. Submitting autonomous development tasks with conversation continuation.
7. Polling task status and structured response extraction.
8. Dispatcher routing across all agy_instance_* and agy_task_* actions.
"""

import os
import sys
import time
import json
import stat
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.isolated_test_case import IsolatedTestCase
from config import Config
from storage.database import db_session
from intelligence.project_analyzer import ProjectAnalyzer
from core.agy_instance_manager import AgyInstanceManager, is_pid_alive
from core.tool_router import ToolRouter


class TestAgyInstanceManager(IsolatedTestCase):
    """Test suite for AgyInstanceManager and Antigravity instance control plane."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # 1. Create sample project
        cls.project_dir = Path(cls._temp_dir) / "sample_project"
        cls.project_dir.mkdir(parents=True, exist_ok=True)
        cls.project = ProjectAnalyzer.register_project(
            name="Sample Agy Project",
            path=str(cls.project_dir),
            description="Project for Agy instance orchestration tests"
        )
        cls.project_id = cls.project["id"]

        # 2. Create mock agy executable script
        cls.bin_dir = Path(cls._temp_dir) / "bin"
        cls.bin_dir.mkdir(parents=True, exist_ok=True)
        cls.mock_agy_script = cls.bin_dir / "mock_agy"

        # Mock script emulates agy CLI behaviors
        script_content = f"""#!{sys.executable}
import sys, time, json

args = sys.argv[1:]

# Check if sleeping is requested
if "sleep" in " ".join(args):
    time.sleep(10)
    sys.exit(0)

conv_id = "conv_test_12345"
for i, a in enumerate(args):
    if a == "--conversation" and i + 1 < len(args):
        conv_id = args[i + 1]

prompt_val = "ok"
for i, a in enumerate(args):
    if a == "-p" and i + 1 < len(args):
        prompt_val = args[i + 1]

output = {{
    "conversation_id": conv_id,
    "status": "SUCCESS",
    "response": f"Executed prompt: {{prompt_val}}",
    "duration_seconds": 0.05,
    "num_turns": 1,
    "usage": {{
        "input_tokens": 120,
        "output_tokens": 45,
        "total_tokens": 165
    }}
}}

print(f"Starting mock agy run for {{prompt_val}}")
print(json.dumps(output))
"""
        cls.mock_agy_script.write_text(script_content)
        cls.mock_agy_script.chmod(cls.mock_agy_script.stat().st_mode | stat.S_IEXEC)

        # 3. Configure mock binary path
        cls._orig_agy_bin = Config.AGY_BIN_PATH
        Config.AGY_BIN_PATH = str(cls.mock_agy_script)

    @classmethod
    def tearDownClass(cls):
        Config.AGY_BIN_PATH = cls._orig_agy_bin
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        Config.JOBS_DIR.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        # Clean up any remaining test processes
        with AgyInstanceManager._lock:
            for iid, proc in list(AgyInstanceManager._active_processes.items()):
                try:
                    proc.kill()
                except Exception:
                    pass
            AgyInstanceManager._active_processes.clear()
            AgyInstanceManager._active_pgids.clear()
            AgyInstanceManager._monitor_threads.clear()
        super().tearDown()

    def test_01_start_instance_and_status(self):
        """Test starting an Antigravity instance and querying its status."""
        res = AgyInstanceManager.start_instance(
            project_id=self.project_id,
            prompt="Initial test prompt",
            timeout=30
        )
        self.assertIn("instance_id", res)
        self.assertIn("pid", res)
        self.assertEqual(res["status"], "running")
        self.assertEqual(res["project_id"], self.project_id)

        inst_id = res["instance_id"]
        pid = res["pid"]

        # Status by instance_id
        st_id = AgyInstanceManager.get_instance_status(inst_id)
        self.assertIsNotNone(st_id)
        self.assertEqual(st_id["instance_id"], inst_id)

        # Status by PID
        st_pid = AgyInstanceManager.get_instance_status(pid)
        self.assertIsNotNone(st_pid)
        self.assertEqual(st_pid["instance_id"], inst_id)

        # Wait for short completion
        time.sleep(1.0)
        st_final = AgyInstanceManager.get_instance_status(inst_id)
        self.assertEqual(st_final["status"], "completed")

    def test_02_get_instance_output(self):
        """Test retrieving instance log output and line slicing."""
        res = AgyInstanceManager.start_instance(
            project_id=self.project_id,
            prompt="Log output verification prompt",
            timeout=30
        )
        inst_id = res["instance_id"]

        # Wait for completion
        time.sleep(1.0)

        output_data = AgyInstanceManager.get_instance_output(inst_id, lines=10, tail=True)
        self.assertEqual(output_data["instance_id"], inst_id)
        self.assertIn("output", output_data)
        self.assertIn("Starting mock agy run", output_data["output"])

    def test_03_stop_instance(self):
        """Test terminating a running instance safely."""
        res = AgyInstanceManager.start_instance(
            project_id=self.project_id,
            prompt="sleep for 10 seconds",
            timeout=30
        )
        inst_id = res["instance_id"]
        pid = res["pid"]

        # Verify process is running
        self.assertTrue(is_pid_alive(pid))

        # Stop instance
        stop_res = AgyInstanceManager.stop_instance(inst_id)
        self.assertEqual(stop_res["status"], "terminated")

        # Verify process terminated
        time.sleep(0.5)
        self.assertFalse(is_pid_alive(pid))

        # Check status recorded in database
        st = AgyInstanceManager.get_instance_status(inst_id)
        self.assertEqual(st["status"], "cancelled")

    def test_04_stop_instance_security_guardrail(self):
        """Test that stop_instance refuses to kill a non-Agy process."""
        import subprocess
        # Spawn an unrelated Python process that sleeps
        dummy_proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(10)"])
        dummy_pid = dummy_proc.pid

        try:
            # Attempt to stop the unrelated PID
            with self.assertRaises(PermissionError) as ctx:
                AgyInstanceManager.stop_instance(dummy_pid)
            self.assertIn("Security check failed", str(ctx.exception))
        finally:
            dummy_proc.kill()
            dummy_proc.wait()

    def test_05_submit_task_and_conversation_continuation(self):
        """Test submitting a task with a conversation_id to continue session."""
        # 1. Submit initial task
        task1 = AgyInstanceManager.submit_task(
            prompt="First turn question",
            project_id=self.project_id,
            conversation_id="conv_abc_999"
        )
        self.assertIn("task_id", task1)
        self.assertEqual(task1["conversation_id"], "conv_abc_999")

        # Wait for completion
        time.sleep(1.0)
        st1 = AgyInstanceManager.get_task_status(task1["task_id"])
        self.assertEqual(st1["status"], "completed")

        # 2. Submit follow-up task with same conversation_id
        task2 = AgyInstanceManager.submit_task(
            prompt="Follow up question",
            project_id=self.project_id,
            conversation_id="conv_abc_999"
        )
        self.assertEqual(task2["conversation_id"], "conv_abc_999")
        time.sleep(1.0)
        st2 = AgyInstanceManager.get_task_status(task2["task_id"])
        self.assertEqual(st2["status"], "completed")

    def test_06_discover_instances(self):
        """Test discovering instances merging live processes and historical records."""
        instances = AgyInstanceManager.discover_instances(include_historical=True, limit=10)
        self.assertIsInstance(instances, list)
        self.assertGreaterEqual(len(instances), 1)

    def test_07_dispatcher_tool_routing(self):
        """Test tool router dispatching across all agy_instance_* actions."""
        # 1. agy_instance_list
        inst_list = ToolRouter.dispatch("agy_instance_list", {"limit": 5})
        self.assertIsInstance(inst_list, list)

        # 2. agy_instance_start
        start_res = ToolRouter.dispatch("agy_instance_start", {
            "project_id": self.project_id,
            "prompt": "Dispatcher routing test"
        })
        self.assertIn("instance_id", start_res)
        inst_id = start_res["instance_id"]

        # 3. agy_instance_status
        st = ToolRouter.dispatch("agy_instance_status", {"instance_id": inst_id})
        self.assertEqual(st["instance_id"], inst_id)

        # Wait for task completion
        time.sleep(1.0)

        # 4. agy_instance_output
        out = ToolRouter.dispatch("agy_instance_output", {"instance_id": inst_id, "lines": 5})
        self.assertIn("output", out)

        # 5. agy_task_submit
        task_res = ToolRouter.dispatch("agy_task_submit", {
            "project_id": self.project_id,
            "prompt": "Submit via dispatch",
            "conversation_id": "conv_disp_001"
        })
        self.assertIn("task_id", task_res)

        time.sleep(1.0)

        # 6. agy_task_status
        task_st = ToolRouter.dispatch("agy_task_status", {"task_id": task_res["task_id"]})
        self.assertEqual(task_st["status"], "completed")


if __name__ == "__main__":
    unittest.main()
