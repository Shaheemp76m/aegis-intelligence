"""Aegis Intelligence - HTTP Route Handlers

Dispatches authenticated HTTP requests to core and intelligence modules,
handles path variables, and returns standardized response envelopes.
"""

import re
import json
import urllib.parse
from typing import Callable, Any, Optional

from api.responses import success_response, error_response
from api.schemas import (
    validate_dict, validate_required_string, validate_optional_string,
    validate_optional_int, validate_optional_list, ValidationError
)
from intelligence.project_analyzer import ProjectAnalyzer
from intelligence.development_monitor import DevelopmentMonitor
from intelligence.task_manager import TaskManager
from intelligence.bug_tracker import BugTracker
from intelligence.project_memory import ProjectMemory
from intelligence.report_generator import ReportGenerator
from intelligence.context_builder import ContextBuilder
from integrations.model_manager import ModelManager
from integrations.usage_monitor import UsageMonitor
from core.execution_manager import ExecutionManager
from core.tool_router import ToolRouter
from core.permission_manager import PermissionManager
from security.approvals import list_approvals, get_approval, decide_approval, ApprovalRequiredException
from security.audit_log import get_recent_audit_logs

class Router:
    """Regex-based HTTP request dispatcher."""

    def __init__(self):
        # List of (method, compiled_regex, handler_func, path_param_keys)
        self.routes: list[tuple[str, re.Pattern, Callable, list[str]]] = []

    def add_route(self, method: str, path_pattern: str, handler: Callable):
        param_names = []
        regex_parts = []
        for segment in path_pattern.split('/'):
            if segment.startswith('{') and segment.endswith('}'):
                name = segment[1:-1]
                param_names.append(name)
                regex_parts.append(r'([^/]+)')
            else:
                regex_parts.append(re.escape(segment))
        regex = re.compile('^' + '/'.join(regex_parts) + '$')
        self.routes.append((method.upper(), regex, handler, param_names))

    def resolve(self, method: str, path: str) -> Optional[tuple[Callable, dict]]:
        norm_method = method.upper()
        clean_path = path.split('?')[0].rstrip('/')
        if not clean_path:
            clean_path = '/'

        for r_method, r_regex, r_handler, r_params in self.routes:
            if r_method == norm_method:
                m = r_regex.match(clean_path)
                if m:
                    kwargs = dict(zip(r_params, m.groups()))
                    return r_handler, kwargs
        return None

router = Router()

# ==================== Health & OpenAPI ====================
def handle_health(request: dict, kwargs: dict) -> tuple[int, bytes]:
    from config import Config
    import sqlite3
    db_ok = False
    try:
        from storage.database import get_connection
        conn = get_connection()
        conn.execute("SELECT 1").fetchone()
        db_ok = True
    except Exception:
        pass

    data = {
        "status": "healthy" if db_ok else "degraded",
        "service": "aegis-intelligence",
        "version": "1.0.0",
        "database": "connected" if db_ok else "disconnected",
        "host": Config.HOST,
        "port": Config.PORT
    }
    return success_response(data, request["request_id"])

def handle_openapi(request: dict, kwargs: dict) -> tuple[int, bytes]:
    from pathlib import Path
    from config import BASE_DIR
    schema_path = BASE_DIR / "docs" / "openapi.json"
    if schema_path.is_file():
        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                content = json.load(f)
            return success_response(content, request["request_id"])
        except Exception:
            pass
    return error_response("NOT_FOUND", "OpenAPI specification not found.", request["request_id"], 404)

router.add_route("GET", "/health", handle_health)
router.add_route("GET", "/openapi.json", handle_openapi)

# ==================== Projects ====================
def handle_list_projects(request: dict, kwargs: dict) -> tuple[int, bytes]:
    projs = ProjectAnalyzer.list_projects()
    return success_response(projs, request["request_id"])

def handle_create_project(request: dict, kwargs: dict) -> tuple[int, bytes]:
    body = validate_dict(request.get("body", {}))
    name = validate_required_string(body, "name")
    path = validate_required_string(body, "path")
    desc = validate_optional_string(body, "description")
    pid = validate_optional_string(body, "project_id") or None

    proj = ProjectAnalyzer.register_project(name=name, path=path, description=desc, project_id=pid)
    return success_response(proj, request["request_id"], status_code=201)

def handle_compare_projects(request: dict, kwargs: dict) -> tuple[int, bytes]:
    body = request.get("body", {}) or {}
    project_ids = body.get("project_ids")
    if not project_ids or not isinstance(project_ids, list):
        project_ids = [p["id"] for p in ProjectAnalyzer.list_projects()]
    comparison = ProjectAnalyzer.compare_projects(project_ids)
    return success_response(comparison, request["request_id"])

def handle_get_project(request: dict, kwargs: dict) -> tuple[int, bytes]:
    pid = kwargs["project_id"]
    proj = ProjectAnalyzer.get_project(pid)
    if not proj:
        return error_response("NOT_FOUND", f"Project '{pid}' not found.", request["request_id"], 404)
    return success_response(proj, request["request_id"])

def handle_update_project(request: dict, kwargs: dict) -> tuple[int, bytes]:
    pid = kwargs["project_id"]
    if not ProjectAnalyzer.get_project(pid):
        return error_response("NOT_FOUND", f"Project '{pid}' not found.", request["request_id"], 404)
    body = validate_dict(request.get("body", {}))
    proj = ProjectAnalyzer.update_project(pid, **body)
    return success_response(proj, request["request_id"])

def handle_delete_project(request: dict, kwargs: dict) -> tuple[int, bytes]:
    pid = kwargs["project_id"]
    success = ProjectAnalyzer.remove_project(pid)
    if not success:
        return error_response("NOT_FOUND", f"Project '{pid}' not found.", request["request_id"], 404)
    return success_response({"unregistered": True, "project_id": pid}, request["request_id"])

def handle_activate_project(request: dict, kwargs: dict) -> tuple[int, bytes]:
    pid = kwargs["project_id"]
    if not ProjectAnalyzer.get_project(pid):
        return error_response("NOT_FOUND", f"Project '{pid}' not found.", request["request_id"], 404)
    proj = ProjectAnalyzer.set_active_project(pid)
    return success_response(proj, request["request_id"])

def handle_inspect_project(request: dict, kwargs: dict) -> tuple[int, bytes]:
    pid = kwargs["project_id"]
    if not ProjectAnalyzer.get_project(pid):
        return error_response("NOT_FOUND", f"Project '{pid}' not found.", request["request_id"], 404)
    inspection = ProjectAnalyzer.inspect_project(pid)
    return success_response(inspection, request["request_id"])

def handle_project_report(request: dict, kwargs: dict) -> tuple[int, bytes]:
    pid = kwargs["project_id"]
    if not ProjectAnalyzer.get_project(pid):
        return error_response("NOT_FOUND", f"Project '{pid}' not found.", request["request_id"], 404)
    query = request.get("query_params", {})
    report_type = query.get("type", ["status"])[0]
    report_text = ReportGenerator.generate_report(report_type, pid)
    return success_response({"project_id": pid, "report_type": report_type, "report": report_text}, request["request_id"])

def handle_project_context(request: dict, kwargs: dict) -> tuple[int, bytes]:
    pid = kwargs["project_id"]
    if not ProjectAnalyzer.get_project(pid):
        return error_response("NOT_FOUND", f"Project '{pid}' not found.", request["request_id"], 404)
    context_text = ContextBuilder.build_agent_context(pid)
    return success_response({"project_id": pid, "context": context_text}, request["request_id"])

router.add_route("GET", "/api/v1/projects", handle_list_projects)
router.add_route("POST", "/api/v1/projects", handle_create_project)
router.add_route("POST", "/api/v1/projects/compare", handle_compare_projects)
router.add_route("GET", "/api/v1/projects/{project_id}", handle_get_project)
router.add_route("PUT", "/api/v1/projects/{project_id}", handle_update_project)
router.add_route("DELETE", "/api/v1/projects/{project_id}", handle_delete_project)
router.add_route("POST", "/api/v1/projects/{project_id}/activate", handle_activate_project)
router.add_route("POST", "/api/v1/projects/{project_id}/inspect", handle_inspect_project)
router.add_route("GET", "/api/v1/projects/{project_id}/report", handle_project_report)
router.add_route("GET", "/api/v1/projects/{project_id}/context", handle_project_context)

# ==================== Tasks ====================
def handle_list_tasks(request: dict, kwargs: dict) -> tuple[int, bytes]:
    pid = kwargs["project_id"]
    if not ProjectAnalyzer.get_project(pid):
        return error_response("NOT_FOUND", f"Project '{pid}' not found.", request["request_id"], 404)
    q = request.get("query_params", {})
    status = q.get("status", [None])[0]
    priority = q.get("priority", [None])[0]
    tasks = TaskManager.list_tasks(project_id=pid, status=status, priority=priority)
    return success_response(tasks, request["request_id"])

def handle_create_task(request: dict, kwargs: dict) -> tuple[int, bytes]:
    pid = kwargs["project_id"]
    if not ProjectAnalyzer.get_project(pid):
        return error_response("NOT_FOUND", f"Project '{pid}' not found.", request["request_id"], 404)
    body = validate_dict(request.get("body", {}))
    title = validate_required_string(body, "title")
    desc = validate_optional_string(body, "description")
    status = validate_optional_string(body, "status", "pending")
    priority = validate_optional_string(body, "priority", "medium")
    due_date = validate_optional_string(body, "due_date") or None
    related = validate_optional_list(body, "related_files")
    notes = validate_optional_string(body, "notes")

    task = TaskManager.create_task(
        project_id=pid,
        title=title,
        description=desc,
        status=status,
        priority=priority,
        due_date=due_date,
        related_files=related,
        notes=notes
    )
    return success_response(task, request["request_id"], status_code=201)

def handle_update_task(request: dict, kwargs: dict) -> tuple[int, bytes]:
    tid = kwargs["task_id"]
    if not TaskManager.get_task(tid):
        return error_response("NOT_FOUND", f"Task '{tid}' not found.", request["request_id"], 404)
    body = validate_dict(request.get("body", {}))
    task = TaskManager.update_task(tid, **body)
    return success_response(task, request["request_id"])

def handle_delete_task(request: dict, kwargs: dict) -> tuple[int, bytes]:
    tid = kwargs["task_id"]
    success = TaskManager.delete_task(tid)
    if not success:
        return error_response("NOT_FOUND", f"Task '{tid}' not found.", request["request_id"], 404)
    return success_response({"deleted": True, "task_id": tid}, request["request_id"])

router.add_route("GET", "/api/v1/projects/{project_id}/tasks", handle_list_tasks)
router.add_route("POST", "/api/v1/projects/{project_id}/tasks", handle_create_task)
router.add_route("PUT", "/api/v1/projects/{project_id}/tasks/{task_id}", handle_update_task)
router.add_route("DELETE", "/api/v1/projects/{project_id}/tasks/{task_id}", handle_delete_task)

# ==================== Bugs ====================
def handle_list_bugs(request: dict, kwargs: dict) -> tuple[int, bytes]:
    pid = kwargs["project_id"]
    if not ProjectAnalyzer.get_project(pid):
        return error_response("NOT_FOUND", f"Project '{pid}' not found.", request["request_id"], 404)
    q = request.get("query_params", {})
    sev = q.get("severity", [None])[0]
    vstat = q.get("verification_status", [None])[0]
    bugs = BugTracker.list_bugs(project_id=pid, severity=sev, verification_status=vstat)
    return success_response(bugs, request["request_id"])

def handle_create_bug(request: dict, kwargs: dict) -> tuple[int, bytes]:
    pid = kwargs["project_id"]
    if not ProjectAnalyzer.get_project(pid):
        return error_response("NOT_FOUND", f"Project '{pid}' not found.", request["request_id"], 404)
    body = validate_dict(request.get("body", {}))
    title = validate_required_string(body, "title")
    sev = validate_optional_string(body, "severity", "medium")
    repro = validate_optional_string(body, "reproduction_steps")
    files = validate_optional_list(body, "affected_files")
    diag = validate_optional_string(body, "diagnosis")
    vstat = validate_optional_string(body, "verification_status", "unverified")

    bug = BugTracker.create_bug(
        project_id=pid,
        title=title,
        severity=sev,
        reproduction_steps=repro,
        affected_files=files,
        diagnosis=diag,
        verification_status=vstat
    )
    return success_response(bug, request["request_id"], status_code=201)

def handle_update_bug(request: dict, kwargs: dict) -> tuple[int, bytes]:
    bid = kwargs["bug_id"]
    if not BugTracker.get_bug(bid):
        return error_response("NOT_FOUND", f"Bug '{bid}' not found.", request["request_id"], 404)
    body = validate_dict(request.get("body", {}))
    bug = BugTracker.update_bug(bid, **body)
    return success_response(bug, request["request_id"])

router.add_route("GET", "/api/v1/projects/{project_id}/bugs", handle_list_bugs)
router.add_route("POST", "/api/v1/projects/{project_id}/bugs", handle_create_bug)
router.add_route("PUT", "/api/v1/projects/{project_id}/bugs/{bug_id}", handle_update_bug)

# ==================== Memory ====================
def handle_get_memory(request: dict, kwargs: dict) -> tuple[int, bytes]:
    pid = kwargs["project_id"]
    if not ProjectAnalyzer.get_project(pid):
        return error_response("NOT_FOUND", f"Project '{pid}' not found.", request["request_id"], 404)
    q = request.get("query_params", {})
    query_str = q.get("query", [None])[0]
    cat = q.get("category", [None])[0]
    limit = int(q.get("limit", [50])[0])
    memories = ProjectMemory.search_memory(project_id=pid, query=query_str, category=cat, limit=limit)
    return success_response(memories, request["request_id"])

def handle_create_memory(request: dict, kwargs: dict) -> tuple[int, bytes]:
    pid = kwargs["project_id"]
    if not ProjectAnalyzer.get_project(pid):
        return error_response("NOT_FOUND", f"Project '{pid}' not found.", request["request_id"], 404)
    body = validate_dict(request.get("body", {}))
    title = validate_required_string(body, "title")
    content = validate_required_string(body, "content")
    category = validate_optional_string(body, "category", "general")
    source = validate_optional_string(body, "source", "user")
    conf = validate_optional_string(body, "confidence", "verified")

    mem = ProjectMemory.record_memory(
        project_id=pid,
        title=title,
        content=content,
        category=category,
        source=source,
        confidence=conf
    )
    return success_response(mem, request["request_id"], status_code=201)

def handle_delete_memory(request: dict, kwargs: dict) -> tuple[int, bytes]:
    mid = kwargs["memory_id"]
    success = ProjectMemory.delete_memory(mid)
    if not success:
        return error_response("NOT_FOUND", f"Memory entry '{mid}' not found.", request["request_id"], 404)
    return success_response({"deleted": True, "memory_id": mid}, request["request_id"])

router.add_route("GET", "/api/v1/projects/{project_id}/memory", handle_get_memory)
router.add_route("POST", "/api/v1/projects/{project_id}/memory", handle_create_memory)
router.add_route("DELETE", "/api/v1/projects/{project_id}/memory/{memory_id}", handle_delete_memory)

# ==================== Antigravity & Execution ====================
def handle_execute_agy(request: dict, kwargs: dict) -> tuple[int, bytes]:
    body = validate_dict(request.get("body", {}))
    prompt = validate_required_string(body, "prompt")
    pid = validate_optional_string(body, "project_id") or None
    model = validate_optional_string(body, "model") or None
    timeout = validate_optional_int(body, "timeout")
    mode = validate_optional_string(body, "mode") or None
    is_async = bool(body.get("async", False))

    proj = ProjectAnalyzer.get_project(pid) if pid else ProjectAnalyzer.get_active_project()
    if not proj:
        return error_response("BAD_REQUEST", "No active project registered for execution.", request["request_id"], 400)

    res = ExecutionManager.execute_job(
        project_path=proj["path"],
        prompt=prompt,
        project_id=proj["id"],
        action=validate_optional_string(body, "action", "execute"),
        model=model,
        timeout=timeout,
        mode=mode,
        async_run=is_async
    )
    return success_response(res, request["request_id"])

def handle_list_models(request: dict, kwargs: dict) -> tuple[int, bytes]:
    models = ModelManager.list_models()
    active = ModelManager.get_active_model()
    return success_response({"models": models, "active_model": active}, request["request_id"])

def handle_switch_model(request: dict, kwargs: dict) -> tuple[int, bytes]:
    body = validate_dict(request.get("body", {}))
    model_id = validate_required_string(body, "model")
    result = ModelManager.switch_model(model_id)
    return success_response(result, request["request_id"])

def handle_get_usage(request: dict, kwargs: dict) -> tuple[int, bytes]:
    summary = UsageMonitor.get_usage_summary()
    return success_response(summary, request["request_id"])

def handle_list_jobs(request: dict, kwargs: dict) -> tuple[int, bytes]:
    q = request.get("query_params", {})
    pid = q.get("project_id", [None])[0]
    limit = int(q.get("limit", [25])[0])
    jobs = ExecutionManager.list_jobs(project_id=pid, limit=limit)
    return success_response(jobs, request["request_id"])

def handle_get_job(request: dict, kwargs: dict) -> tuple[int, bytes]:
    jid = kwargs["job_id"]
    job = ExecutionManager.get_job(jid)
    if not job:
        return error_response("NOT_FOUND", f"Job '{jid}' not found.", request["request_id"], 404)
    return success_response(job, request["request_id"])

router.add_route("POST", "/api/v1/agy/execute", handle_execute_agy)
router.add_route("GET", "/api/v1/agy/models", handle_list_models)
router.add_route("POST", "/api/v1/agy/model/switch", handle_switch_model)
router.add_route("GET", "/api/v1/agy/usage", handle_get_usage)
router.add_route("GET", "/api/v1/jobs", handle_list_jobs)
router.add_route("GET", "/api/v1/jobs/{job_id}", handle_get_job)

# ==================== Approvals & Audit ====================
def handle_list_approvals(request: dict, kwargs: dict) -> tuple[int, bytes]:
    q = request.get("query_params", {})
    status = q.get("status", [None])[0]
    apprs = list_approvals(status=status)
    return success_response(apprs, request["request_id"])

def handle_decide_approval(request: dict, kwargs: dict) -> tuple[int, bytes]:
    aid = kwargs["approval_id"]
    if not get_approval(aid):
        return error_response("NOT_FOUND", f"Approval '{aid}' not found.", request["request_id"], 404)
    body = validate_dict(request.get("body", {}))
    decision = validate_required_string(body, "decision")
    reason = validate_optional_string(body, "reason")
    actor = validate_optional_string(body, "actor", "telegram_user")

    result = decide_approval(approval_id=aid, decision=decision, reason=reason, actor=actor)
    return success_response(result, request["request_id"])

def handle_get_audit_logs(request: dict, kwargs: dict) -> tuple[int, bytes]:
    q = request.get("query_params", {})
    action = q.get("action", [None])[0]
    limit = int(q.get("limit", [50])[0])
    logs = get_recent_audit_logs(limit=limit, action=action)
    return success_response(logs, request["request_id"])

router.add_route("GET", "/api/v1/approvals", handle_list_approvals)
router.add_route("POST", "/api/v1/approvals/{approval_id}/decision", handle_decide_approval)
router.add_route("GET", "/api/v1/audit/logs", handle_get_audit_logs)

# ==================== Generic Tool Dispatch ====================
def handle_tool_dispatch(request: dict, kwargs: dict) -> tuple[int, bytes]:
    """Single dispatch endpoint for n8n AI Agent tool calling."""
    body = validate_dict(request.get("body", {}))
    tool_name = validate_required_string(body, "tool")
    params = body.get("params", {})
    approval_id = body.get("approval_id")

    try:
        res = ToolRouter.dispatch(tool_name, params=params, approval_id=approval_id)
        return success_response(res, request["request_id"])
    except ApprovalRequiredException as are:
        return error_response(
            code="APPROVAL_REQUIRED",
            message=str(are),
            request_id=request["request_id"],
            status_code=403
        )

router.add_route("POST", "/api/v1/tools/dispatch", handle_tool_dispatch)
