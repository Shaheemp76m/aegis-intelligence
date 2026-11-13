"""Aegis Intelligence - Comprehensive Full API Verification Tests

Tests all 30+ HTTP endpoints against a live test server instance:
- Status codes (200, 201, 400, 401, 403, 404)
- Request validation & invalid input handling
- Response envelope schemas (success, request_id, data, error)
- Authentication headers (X-Aegis-Token, Authorization: Bearer, casing)
- Missing-resource behavior (404s for projects, tasks, bugs, memory, jobs, approvals)
- Database persistence and cascading operations
"""

import os
import sys
import json
import time
import shutil
import tempfile
import unittest
import threading
import urllib.request
import urllib.error
from pathlib import Path
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import Config
from tests.isolated_test_case import IsolatedTestCase
from server import AegisRequestHandler

TEST_PORT = 8798
TEST_TOKEN = "aegis_test_token_full_suite_abcdef1234567890"

class TestFullApiSuite(IsolatedTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Config.HOST = "127.0.0.1"
        Config.PORT = TEST_PORT
        Config.API_TOKEN = TEST_TOKEN
        Config.TOKEN_FILE.write_text(TEST_TOKEN, encoding="utf-8")

        cls.server = ThreadingHTTPServer((Config.HOST, TEST_PORT), AegisRequestHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        cls.base_url = f"http://127.0.0.1:{TEST_PORT}"

        # Create temporary sample project directory
        cls.sample_project_dir = Path(cls._temp_dir) / "sample_app"
        cls.sample_project_dir.mkdir(parents=True, exist_ok=True)
        (cls.sample_project_dir / "package.json").write_text(
            json.dumps({"name": "test-app", "dependencies": {"react": "^18.0.0", "typescript": "^5.0.0"}}),
            encoding="utf-8"
        )
        (cls.sample_project_dir / "README.md").write_text("# Test App\nA safe test application.", encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        super().tearDownClass()

    def _req(self, path: str, method: str = "GET", body: dict = None, headers: dict = None):
        """Helper to execute HTTP requests with standard error trapping."""
        url = f"{self.base_url}{path}"
        req_headers = headers.copy() if headers is not None else {"Authorization": f"Bearer {TEST_TOKEN}"}
        req_headers.setdefault("Content-Type", "application/json")

        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(url, data=data, headers=req_headers, method=method)

        try:
            with urllib.request.urlopen(req) as resp:
                status = resp.status
                raw = resp.read().decode("utf-8")
                content = json.loads(raw) if raw else {}
                return status, content
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8")
            content = json.loads(raw) if raw else {}
            return e.code, content

    # 1. Health & OpenAPI
    def test_health_endpoint(self):
        code, body = self._req("/health", headers={})
        self.assertEqual(code, 200)
        self.assertTrue(body["success"])
        self.assertEqual(body["data"]["status"], "healthy")
        self.assertEqual(body["data"]["database"], "connected")
        self.assertIsNone(body["error"])

    def test_openapi_endpoint(self):
        code, body = self._req("/openapi.json", headers={})
        self.assertEqual(code, 200)
        self.assertTrue(body["success"])
        self.assertIn("openapi", body["data"])

    # 2. Authentication Enforcement
    def test_auth_enforcement_headers(self):
        # Missing auth -> 401
        code, body = self._req("/api/v1/projects", headers={})
        self.assertEqual(code, 401)
        self.assertFalse(body["success"])
        self.assertEqual(body["error"]["code"], "UNAUTHORIZED")

        # Invalid token -> 401
        code, body = self._req("/api/v1/projects", headers={"X-Aegis-Token": "invalid_token_123"})
        self.assertEqual(code, 401)

        # Valid X-Aegis-Token -> 200
        code, body = self._req("/api/v1/projects", headers={"X-Aegis-Token": TEST_TOKEN})
        self.assertEqual(code, 200)

        # Valid Authorization: Bearer -> 200
        code, body = self._req("/api/v1/projects", headers={"Authorization": f"Bearer {TEST_TOKEN}"})
        self.assertEqual(code, 200)

        # Valid lowercase x-aegis-token -> 200
        code, body = self._req("/api/v1/projects", headers={"x-aegis-token": TEST_TOKEN})
        self.assertEqual(code, 200)

    # 3. Project Lifecycle
    def test_project_crud_and_missing_resource(self):
        # Missing project -> 404
        code, body = self._req("/api/v1/projects/proj_nonexistent_999")
        self.assertEqual(code, 404)
        self.assertEqual(body["error"]["code"], "NOT_FOUND")

        # Create project with invalid body -> 400
        code, body = self._req("/api/v1/projects", method="POST", body={})
        self.assertEqual(code, 400)
        self.assertEqual(body["error"]["code"], "VALIDATION_ERROR")

        # Register valid project -> 201
        code, body = self._req("/api/v1/projects", method="POST", body={
            "name": "Full Suite App",
            "path": str(self.sample_project_dir),
            "description": "Integration test project"
        })
        self.assertEqual(code, 201)
        self.assertTrue(body["success"])
        pid = body["data"]["id"]
        self.assertTrue(pid.startswith("proj_"))
        self.assertEqual(body["data"]["name"], "Full Suite App")

        # Get project -> 200
        code, body = self._req(f"/api/v1/projects/{pid}")
        self.assertEqual(code, 200)
        self.assertEqual(body["data"]["id"], pid)

        # Update project -> 200
        code, body = self._req(f"/api/v1/projects/{pid}", method="PUT", body={"description": "Updated desc"})
        self.assertEqual(code, 200)
        self.assertEqual(body["data"]["description"], "Updated desc")

        # Update missing project -> 404
        code, body = self._req("/api/v1/projects/proj_nonexistent", method="PUT", body={"name": "New"})
        self.assertEqual(code, 404)

        # Activate project -> 200
        code, body = self._req(f"/api/v1/projects/{pid}/activate", method="POST")
        self.assertEqual(code, 200)
        self.assertEqual(body["data"]["is_active"], 1)

        # Activate missing project -> 404
        code, body = self._req("/api/v1/projects/proj_nonexistent/activate", method="POST")
        self.assertEqual(code, 404)

        # Inspect project -> 200
        code, body = self._req(f"/api/v1/projects/{pid}/inspect", method="POST")
        self.assertEqual(code, 200)
        self.assertIn("filesystem", body["data"])
        self.assertIn("git", body["data"])

        # Inspect missing project -> 404
        code, body = self._req("/api/v1/projects/proj_nonexistent/inspect", method="POST")
        self.assertEqual(code, 404)

        # Project report -> 200
        code, body = self._req(f"/api/v1/projects/{pid}/report?type=status")
        self.assertEqual(code, 200)
        self.assertIn("report", body["data"])
        self.assertIn("STATUS REPORT", body["data"]["report"])

        # Report missing project -> 404
        code, body = self._req("/api/v1/projects/proj_nonexistent/report?type=status")
        self.assertEqual(code, 404)

        # Project context -> 200
        code, body = self._req(f"/api/v1/projects/{pid}/context")
        self.assertEqual(code, 200)
        self.assertIn("context", body["data"])
        self.assertIn("Full Suite App", body["data"]["context"])

        # Context missing project -> 404
        code, body = self._req("/api/v1/projects/proj_nonexistent/context")
        self.assertEqual(code, 404)

        # Compare projects -> 200
        code, body = self._req("/api/v1/projects/compare", method="POST", body={"project_ids": [pid]})
        self.assertEqual(code, 200)
        self.assertIsInstance(body["data"], list)
        self.assertEqual(len(body["data"]), 1)
        self.assertEqual(body["data"][0]["id"], pid)

        # Unregister project -> 200
        code, body = self._req(f"/api/v1/projects/{pid}", method="DELETE")
        self.assertEqual(code, 200)
        self.assertTrue(body["data"]["unregistered"])

        # Unregister again -> 404
        code, body = self._req(f"/api/v1/projects/{pid}", method="DELETE")
        self.assertEqual(code, 404)

    # 4. Task Management
    def test_task_endpoints_and_missing_resource(self):
        # Register a project first
        code, pbody = self._req("/api/v1/projects", method="POST", body={
            "name": "Task Test App",
            "path": str(self.sample_project_dir)
        })
        pid = pbody["data"]["id"]

        # List tasks on missing project -> 404
        code, body = self._req("/api/v1/projects/proj_ghost_404/tasks")
        self.assertEqual(code, 404)

        # Create task on missing project -> 404
        code, body = self._req("/api/v1/projects/proj_ghost_404/tasks", method="POST", body={"title": "Test"})
        self.assertEqual(code, 404)

        # Create task on valid project -> 201
        code, body = self._req(f"/api/v1/projects/{pid}/tasks", method="POST", body={
            "title": "Configure ESLint",
            "priority": "high",
            "status": "pending"
        })
        self.assertEqual(code, 201)
        tid = body["data"]["id"]
        self.assertTrue(tid.startswith("task_"))

        # List tasks -> 200
        code, body = self._req(f"/api/v1/projects/{pid}/tasks")
        self.assertEqual(code, 200)
        self.assertEqual(len(body["data"]), 1)

        # Update task -> 200
        code, body = self._req(f"/api/v1/projects/{pid}/tasks/{tid}", method="PUT", body={"status": "completed"})
        self.assertEqual(code, 200)
        self.assertEqual(body["data"]["status"], "completed")

        # Update missing task -> 404
        code, body = self._req(f"/api/v1/projects/{pid}/tasks/task_missing_999", method="PUT", body={"status": "completed"})
        self.assertEqual(code, 404)

        # Delete task -> 200
        code, body = self._req(f"/api/v1/projects/{pid}/tasks/{tid}", method="DELETE")
        self.assertEqual(code, 200)
        self.assertTrue(body["data"]["deleted"])

        # Delete missing task -> 404
        code, body = self._req(f"/api/v1/projects/{pid}/tasks/task_missing_999", method="DELETE")
        self.assertEqual(code, 404)

        # Clean up project
        self._req(f"/api/v1/projects/{pid}", method="DELETE")

    # 5. Bug Tracking
    def test_bug_endpoints_and_missing_resource(self):
        code, pbody = self._req("/api/v1/projects", method="POST", body={
            "name": "Bug Test App",
            "path": str(self.sample_project_dir)
        })
        pid = pbody["data"]["id"]

        # List bugs on missing project -> 404
        code, body = self._req("/api/v1/projects/proj_ghost_404/bugs")
        self.assertEqual(code, 404)

        # Create bug on missing project -> 404
        code, body = self._req("/api/v1/projects/proj_ghost_404/bugs", method="POST", body={"title": "Crash on click"})
        self.assertEqual(code, 404)

        # Create bug on valid project -> 201
        code, body = self._req(f"/api/v1/projects/{pid}/bugs", method="POST", body={
            "title": "Null pointer on login",
            "severity": "critical",
            "verification_status": "unverified"
        })
        self.assertEqual(code, 201)
        bid = body["data"]["id"]
        self.assertTrue(bid.startswith("bug_"))

        # List bugs -> 200
        code, body = self._req(f"/api/v1/projects/{pid}/bugs")
        self.assertEqual(code, 200)
        self.assertEqual(len(body["data"]), 1)

        # Update bug -> 200
        code, body = self._req(f"/api/v1/projects/{pid}/bugs/{bid}", method="PUT", body={
            "verification_status": "diagnosed",
            "diagnosis": "Missing check on user.profile"
        })
        self.assertEqual(code, 200)
        self.assertEqual(body["data"]["verification_status"], "diagnosed")

        # Update missing bug -> 404
        code, body = self._req(f"/api/v1/projects/{pid}/bugs/bug_ghost_999", method="PUT", body={"verification_status": "resolved"})
        self.assertEqual(code, 404)

        # Clean up project
        self._req(f"/api/v1/projects/{pid}", method="DELETE")

    # 6. Memory Store
    def test_memory_endpoints_and_missing_resource(self):
        code, pbody = self._req("/api/v1/projects", method="POST", body={
            "name": "Memory Test App",
            "path": str(self.sample_project_dir)
        })
        pid = pbody["data"]["id"]

        # Get memory on missing project -> 404
        code, body = self._req("/api/v1/projects/proj_ghost_404/memory")
        self.assertEqual(code, 404)

        # Create memory on missing project -> 404
        code, body = self._req("/api/v1/projects/proj_ghost_404/memory", method="POST", body={
            "title": "Decision",
            "content": "Use SQLite"
        })
        self.assertEqual(code, 404)

        # Create memory -> 201
        code, body = self._req(f"/api/v1/projects/{pid}/memory", method="POST", body={
            "title": "State Architecture",
            "content": "Redux Toolkit used for global client state.",
            "category": "architecture",
            "confidence": "verified"
        })
        self.assertEqual(code, 201)
        mid = body["data"]["id"]

        # Get memory -> 200
        code, body = self._req(f"/api/v1/projects/{pid}/memory?query=Redux")
        self.assertEqual(code, 200)
        self.assertEqual(len(body["data"]), 1)
        self.assertEqual(body["data"][0]["id"], mid)

        # Delete memory -> 200
        code, body = self._req(f"/api/v1/projects/{pid}/memory/{mid}", method="DELETE")
        self.assertEqual(code, 200)
        self.assertTrue(body["data"]["deleted"])

        # Delete missing memory -> 404
        code, body = self._req(f"/api/v1/projects/{pid}/memory/mem_missing_999", method="DELETE")
        self.assertEqual(code, 404)

        # Clean up project
        self._req(f"/api/v1/projects/{pid}", method="DELETE")

    # 7. Antigravity & Model Endpoints
    def test_model_and_usage_endpoints(self):
        # Models list -> 200
        code, body = self._req("/api/v1/agy/models")
        self.assertEqual(code, 200)
        self.assertIn("models", body["data"])
        self.assertIn("active_model", body["data"])

        # Switch to supported model -> 200
        code, body = self._req("/api/v1/agy/model/switch", method="POST", body={"model": "gemini-3.8-flash-high"})
        self.assertEqual(code, 200)
        self.assertTrue(body["data"]["success"])

        # Switch to invalid model -> 400
        code, body = self._req("/api/v1/agy/model/switch", method="POST", body={"model": "fake-unsupported-model-999"})
        self.assertEqual(code, 400)
        self.assertEqual(body["error"]["code"], "BAD_REQUEST")

        # Usage summary -> 200
        code, body = self._req("/api/v1/agy/usage")
        self.assertEqual(code, 200)
        self.assertEqual(body["data"]["account_quota"]["status"], "unsupported")
        self.assertEqual(body["data"]["local_session_usage"]["status"], "supported")

    # 8. Approvals & Audit Logs
    def test_approvals_and_audit_endpoints(self):
        # Approvals list -> 200
        code, body = self._req("/api/v1/approvals")
        self.assertEqual(code, 200)
        self.assertIsInstance(body["data"], list)

        # Decide missing approval -> 404
        code, body = self._req("/api/v1/approvals/appr_nonexistent_999/decision", method="POST", body={
            "decision": "APPROVED",
            "reason": "Testing 404"
        })
        self.assertEqual(code, 404)
        self.assertEqual(body["error"]["code"], "NOT_FOUND")

        # Audit logs -> 200
        code, body = self._req("/api/v1/audit/logs")
        self.assertEqual(code, 200)
        self.assertIsInstance(body["data"], list)

    # 9. Tools Dispatch
    def test_tool_dispatch(self):
        # Register a project first
        code, pbody = self._req("/api/v1/projects", method="POST", body={
            "name": "Dispatch Test App",
            "path": str(self.sample_project_dir)
        })
        pid = pbody["data"]["id"]

        # Tool dispatch: project_list -> 200
        code, body = self._req("/api/v1/tools/dispatch", method="POST", body={
            "tool": "project_list"
        })
        self.assertEqual(code, 200)
        self.assertTrue(any(p["id"] == pid for p in body["data"]))

        # Tool dispatch: task_create -> 200
        code, body = self._req("/api/v1/tools/dispatch", method="POST", body={
            "tool": "task_create",
            "params": {
                "project_id": pid,
                "title": "Dispatched Task",
                "priority": "medium"
            }
        })
        self.assertEqual(code, 200)
        self.assertTrue(body["data"]["id"].startswith("task_"))

        # Tool dispatch: projects_compare -> 200
        code, body = self._req("/api/v1/tools/dispatch", method="POST", body={
            "tool": "projects_compare",
            "params": {"project_ids": [pid]}
        })
        self.assertEqual(code, 200)
        self.assertEqual(len(body["data"]), 1)

        # Tool dispatch: project_context -> 200
        code, body = self._req("/api/v1/tools/dispatch", method="POST", body={
            "tool": "project_context",
            "params": {"project_id": pid}
        })
        self.assertEqual(code, 200)
        self.assertIn("context", body["data"])

        # Tool dispatch: gated action without approval -> 403
        code, body = self._req("/api/v1/tools/dispatch", method="POST", body={
            "tool": "delete_project_dir",
            "params": {"project_id": pid}
        })
        self.assertEqual(code, 403)
        self.assertEqual(body["error"]["code"], "APPROVAL_REQUIRED")
        self.assertIn("Approval ID", body["error"]["message"])

        # Clean up project
        self._req(f"/api/v1/projects/{pid}", method="DELETE")

if __name__ == "__main__":
    unittest.main()
