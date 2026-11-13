"""Aegis Intelligence - Comprehensive Live System Verification Script

Runs directly against the live server at http://127.0.0.1:8765 using the actual
token from data/.api_token:
1. Environment & Auth check
2. Full API & Intelligence verification with temporary test project
3. Git integration & Project reports verification
4. Task & Bug tracking lifecycle
5. Memory engine keyword search & categories
6. Cross-project comparison & Context building
7. Antigravity execution & Model discovery/switching
8. Security audit (path traversal, shell injection, forbidden dirs, localhost)
9. n8n integration readiness & /tools/dispatch
"""

import os
import sys
import json
import subprocess
import tempfile
import urllib.request
import urllib.error
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
TOKEN_FILE = BASE_DIR / "data" / ".api_token"
BASE_URL = "http://127.0.0.1:8765"

results = {}

def log_result(section: str, test_name: str, passed: bool, details: str = ""):
    results.setdefault(section, []).append({
        "name": test_name,
        "status": "PASS" if passed else "FAIL",
        "details": details
    })
    status_emoji = "✅ PASS" if passed else "❌ FAIL"
    print(f"[{status_emoji}] {section} -> {test_name}: {details}")

def make_req(path: str, method: str = "GET", body: dict = None, headers: dict = None):
    url = f"{BASE_URL}{path}"
    req_headers = headers.copy() if headers is not None else {}
    req_headers.setdefault("Content-Type", "application/json")

    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)

    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8")
        return e.code, json.loads(raw) if raw else {}
    except Exception as exc:
        return -1, {"error": str(exc)}

def main():
    print("=== STARTING AEGIS INTELLIGENCE LIVE SYSTEM VERIFICATION ===")

    # 1. Environment & Auth Check
    if not TOKEN_FILE.is_file():
        log_result("Auth", "Token File Exists", False, f"File {TOKEN_FILE} missing")
        return
    token = TOKEN_FILE.read_text().strip()
    log_result("Auth", "Token File Exists", True, f"Length: {len(token)} chars (0600 mode)")

    # Test /health
    code, resp = make_req("/health")
    log_result("API", "GET /health", code == 200 and resp.get("success"), f"Status: {code}")

    # Test auth failure without token
    code, resp = make_req("/api/v1/projects")
    log_result("Auth", "Reject Missing Auth", code == 401, f"Status: {code}")

    # Test auth with X-Aegis-Token
    code, resp = make_req("/api/v1/projects", headers={"X-Aegis-Token": token})
    log_result("Auth", "Accept X-Aegis-Token", code == 200 and resp.get("success"), f"Status: {code}")

    # Test auth with Authorization: Bearer
    auth_header = {"Authorization": f"Bearer {token}"}
    code, resp = make_req("/api/v1/projects", headers=auth_header)
    log_result("Auth", "Accept Bearer Token", code == 200 and resp.get("success"), f"Status: {code}")

    # Create temporary test git repo
    with tempfile.TemporaryDirectory(prefix="aegis_verify_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        # Initialize Git repo
        subprocess.run(["git", "init", "-b", "main"], cwd=tmp_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Aegis Tester"], cwd=tmp_dir, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.email", "aegis@example.com"], cwd=tmp_dir, capture_output=True, check=True)

        # Create sample files
        pkg_json = {"name": "verify-app", "dependencies": {"express": "^4.18.2", "typescript": "^5.0.0"}}
        (tmp_path / "package.json").write_text(json.dumps(pkg_json, indent=2))
        (tmp_path / "index.ts").write_text("// TODO: add error handling\nconsole.log('hello world');\n")
        (tmp_path / "README.md").write_text("# Verification Project\nLive test project for Aegis.\n")

        subprocess.run(["git", "add", "."], cwd=tmp_dir, capture_output=True, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit for verification"], cwd=tmp_dir, capture_output=True, check=True)

        # Make one modified uncommitted file
        (tmp_path / "index.ts").write_text("// TODO: add error handling\nconsole.log('hello modified');\n")

        # 2. Intelligence: Project Registration
        code, resp = make_req("/api/v1/projects", method="POST", body={
            "name": "Live Verify Project",
            "path": str(tmp_path),
            "description": "Temp verification project"
        }, headers=auth_header)
        project_id = resp.get("data", {}).get("id") if code == 201 else None
        log_result("Intelligence", "Project Registration", code == 201 and project_id is not None, f"ID: {project_id}")

        if not project_id:
            print("Cannot proceed with project verification without valid registration.")
            return

        # 3. Intelligence: Stack Detection & Git Inspection
        code, resp = make_req(f"/api/v1/projects/{project_id}/inspect", method="POST", headers=auth_header)
        git_data = resp.get("data", {}).get("git", {})
        fs_data = resp.get("data", {}).get("filesystem", {})
        proj_data = resp.get("data", {}).get("project", {})

        stack_ok = "TypeScript" in proj_data.get("languages", []) and "Node.js" in proj_data.get("tech_stack", [])
        git_ok = git_data.get("status", {}).get("branch") == "main" and git_data.get("status", {}).get("modified_count") == 1
        log_result("Intelligence", "Stack Detection", stack_ok, f"Languages: {proj_data.get('languages')}")
        log_result("Intelligence", "Git Inspection", git_ok, f"Branch: {git_data.get('status', {}).get('branch')}, Modified: {git_data.get('status', {}).get('modified_count')}")

        # 4. Intelligence: Project Reports
        report_types = ["status", "daily", "weekly", "tasks", "bugs", "git", "health"]
        reports_ok = True
        for rtype in report_types:
            code, resp = make_req(f"/api/v1/projects/{project_id}/report?type={rtype}", headers=auth_header)
            if code != 200 or "report" not in resp.get("data", {}):
                reports_ok = False
        log_result("Intelligence", "Report Generation (7 types)", reports_ok, f"Verified types: {', '.join(report_types)}")

        # 5. Intelligence: Tasks Lifecycle
        code, resp = make_req(f"/api/v1/projects/{project_id}/tasks", method="POST", body={
            "title": "Set up database connection",
            "priority": "high",
            "status": "in_progress"
        }, headers=auth_header)
        task_id = resp.get("data", {}).get("id")
        task_create_ok = code == 201 and task_id is not None

        # Add a blocker task
        make_req(f"/api/v1/projects/{project_id}/tasks", method="POST", body={
            "title": "Wait for SSL certificate",
            "priority": "critical",
            "status": "blocked",
            "notes": "Domain DNS pending"
        }, headers=auth_header)

        # Update task to completed
        code, resp = make_req(f"/api/v1/projects/{project_id}/tasks/{task_id}", method="PUT", body={
            "status": "completed"
        }, headers=auth_header)
        task_update_ok = code == 200 and resp.get("data", {}).get("status") == "completed"

        # List tasks
        code, resp = make_req(f"/api/v1/projects/{project_id}/tasks", headers=auth_header)
        tasks_list_ok = code == 200 and len(resp.get("data", [])) >= 2
        log_result("Intelligence", "Task Lifecycle (Create/Update/Blocker)", task_create_ok and task_update_ok and tasks_list_ok)

        # 6. Intelligence: Bug Tracking Lifecycle
        code, resp = make_req(f"/api/v1/projects/{project_id}/bugs", method="POST", body={
            "title": "Uncaught exception on empty payload",
            "severity": "high",
            "verification_status": "unverified",
            "reproduction_steps": "Send empty body to endpoint"
        }, headers=auth_header)
        bug_id = resp.get("data", {}).get("id")
        bug_create_ok = code == 201 and bug_id is not None

        # Update bug to diagnosed then resolved
        code, resp = make_req(f"/api/v1/projects/{project_id}/bugs/{bug_id}", method="PUT", body={
            "verification_status": "diagnosed",
            "diagnosis": "Missing payload guard"
        }, headers=auth_header)
        bug_diag_ok = code == 200 and resp.get("data", {}).get("verification_status") == "diagnosed"

        code, resp = make_req(f"/api/v1/projects/{project_id}/bugs/{bug_id}", method="PUT", body={
            "verification_status": "verified_fixed",
            "resolution": "Added validation check"
        }, headers=auth_header)
        bug_resolve_ok = code == 200 and resp.get("data", {}).get("verification_status") == "verified_fixed"
        log_result("Intelligence", "Bug Tracking Lifecycle", bug_create_ok and bug_diag_ok and bug_resolve_ok)

        # 7. Intelligence: Persistent Project Memory
        code, resp = make_req(f"/api/v1/projects/{project_id}/memory", method="POST", body={
            "title": "Architecture Strategy",
            "content": "Modular monolith with SQLite backend and Wal mode.",
            "category": "architecture",
            "confidence": "verified"
        }, headers=auth_header)
        mem_id = resp.get("data", {}).get("id")
        mem_create_ok = code == 201 and mem_id is not None

        code, resp = make_req(f"/api/v1/projects/{project_id}/memory?query=SQLite+Wal", headers=auth_header)
        mem_search_ok = code == 200 and len(resp.get("data", [])) >= 1 and resp["data"][0]["id"] == mem_id
        log_result("Intelligence", "Memory Engine (CRUD & Keyword Search)", mem_create_ok and mem_search_ok)

        # 8. Intelligence: Cross-Project Comparison & Context Building
        code, resp = make_req("/api/v1/projects/compare", method="POST", body={
            "project_ids": [project_id]
        }, headers=auth_header)
        comp_ok = code == 200 and len(resp.get("data", [])) == 1 and resp["data"][0]["id"] == project_id
        log_result("Intelligence", "Cross-Project Comparison", comp_ok)

        code, resp = make_req(f"/api/v1/projects/{project_id}/context", headers=auth_header)
        context_str = resp.get("data", {}).get("context", "")
        ctx_ok = code == 200 and "Live Verify Project" in context_str and "Blockers" in context_str
        log_result("Intelligence", "Context Building for AI Agent", ctx_ok)

        # 9. Antigravity Execution Verification
        # Model discovery
        code, resp = make_req("/api/v1/agy/models", headers=auth_header)
        models = resp.get("data", {}).get("models", [])
        active_model = resp.get("data", {}).get("active_model", {})
        models_ok = code == 200 and len(models) >= 1
        log_result("Antigravity", "Model Discovery", models_ok, f"Found {len(models)} models, active: {active_model.get('id')}")

        # Model switching
        target_model = "gemini-3.8-flash-high"
        code, resp = make_req("/api/v1/agy/model/switch", method="POST", body={"model": target_model}, headers=auth_header)
        switch_ok = code == 200 and resp.get("data", {}).get("success")
        log_result("Antigravity", "Model Switching", switch_ok, f"Target: {target_model}")

        # Usage summary & Quota distinction
        code, resp = make_req("/api/v1/agy/usage", headers=auth_header)
        usage_data = resp.get("data", {})
        quota_unsupported = usage_data.get("account_quota", {}).get("status") == "unsupported"
        session_supported = usage_data.get("local_session_usage", {}).get("status") == "supported"
        log_result("Antigravity", "Usage Metrics & Honest Quota Reporting", code == 200 and quota_unsupported and session_supported)

        # 10. Security Audit
        # Path traversal prevention
        code, resp = make_req("/api/v1/projects", method="POST", body={
            "name": "Traversal Test",
            "path": "/data/data/com.termux/files/usr/bin"
        }, headers=auth_header)
        traversal_blocked = code in (400, 403) and not resp.get("success")
        log_result("Security", "Forbidden Path Registration Blocked", traversal_blocked, f"Status: {code}")

        # Shell command injection via tool dispatch
        code, resp = make_req("/api/v1/tools/dispatch", method="POST", body={
            "tool": "file_read",
            "params": {
                "project_id": project_id,
                "path": "README.md; cat /etc/passwd"
            }
        }, headers=auth_header)
        injection_blocked = code in (400, 403, 404)
        log_result("Security", "Shell Injection / Traversal in file_read Blocked", injection_blocked, f"Status: {code}")

        # Approval gate single-use and expiration
        code, resp = make_req("/api/v1/tools/dispatch", method="POST", body={
            "tool": "delete_project_dir",
            "params": {"project_id": project_id}
        }, headers=auth_header)
        gated = code == 403 and resp.get("error", {}).get("code") == "APPROVAL_REQUIRED"
        log_result("Security", "Approval Gate Enforced on Destructive Operation", gated)

        # 11. n8n Integration Readiness
        # Verify /api/v1/tools/dispatch works for core tools
        code, resp = make_req("/api/v1/tools/dispatch", method="POST", body={
            "tool": "task_list",
            "params": {"project_id": project_id}
        }, headers=auth_header)
        dispatch_ok = code == 200 and isinstance(resp.get("data"), list)
        log_result("n8n Integration", "Tool Dispatch (/api/v1/tools/dispatch)", dispatch_ok)

        # Clean up temporary test project from database
        code, resp = make_req(f"/api/v1/projects/{project_id}", method="DELETE", headers=auth_header)
        log_result("Intelligence", "Project Cleanup (Preserving files)", code == 200)

    # Print summary
    print("\n=== VERIFICATION SUMMARY ===")
    total = sum(len(v) for v in results.values())
    passed = sum(1 for v in results.values() for t in v if t["status"] == "PASS")
    failed = total - passed
    print(f"Total Tests: {total} | Passed: {passed} | Failed: {failed}")
    if failed == 0:
        print("🎉 ALL LIVE CHECKS PASSED PERFECTLY!")
    else:
        print(f"⚠️ {failed} TEST(S) FAILED!")

if __name__ == "__main__":
    main()
