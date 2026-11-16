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
from intelligence.session_manager import SessionManager
from integrations.telegram_typing import TelegramTypingService
from intelligence.context_builder import ContextBuilder
from integrations.model_manager import ModelManager
from integrations.usage_monitor import UsageMonitor
from core.execution_manager import ExecutionManager
from core.agy_instance_manager import AgyInstanceManager
from core.tool_router import ToolRouter
from core.permission_manager import PermissionManager
from security.approvals import list_approvals, get_approval, decide_approval, ApprovalRequiredException
from security.audit_log import get_recent_audit_logs
from skill_system.selector import SkillSelector

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

def handle_project_assessment(request: dict, kwargs: dict) -> tuple[int, bytes]:
    pid = kwargs["project_id"]
    if not ProjectAnalyzer.get_project(pid):
        return error_response("NOT_FOUND", f"Project '{pid}' not found.", request["request_id"], 404)
    q = request.get("query_params", {})
    raw_sections = q.get("sections", [None])[0]
    sections = [s.strip() for s in raw_sections.split(",")] if raw_sections else None
    execute_tests = q.get("execute_tests", ["false"])[0].lower() in ("true", "1", "yes")

    assessment = ProjectAnalyzer.assess_project(
        project_id=pid,
        sections=sections,
        execute_tests=execute_tests
    )
    return success_response(assessment, request["request_id"])

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
router.add_route("GET", "/api/v1/projects/{project_id}/assessment", handle_project_assessment)

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

def handle_start_job(request: dict, kwargs: dict) -> tuple[int, bytes]:
    body = validate_dict(request.get("body", {}))
    cmd = body.get("command") or body.get("cmd")
    if not cmd:
        raise ValidationError("Field 'command' is required.")
    pid = validate_optional_string(body, "project_id")
    cwd = validate_optional_string(body, "cwd") or validate_optional_string(body, "working_directory")
    timeout = body.get("timeout")
    action_type = validate_optional_string(body, "action")
    chat_id = validate_optional_string(body, "telegram_chat_id")
    res = ExecutionManager.start_job(
        command=cmd,
        project_id=pid or None,
        cwd=cwd or None,
        timeout=int(timeout) if timeout else None,
        action=action_type or None,
        telegram_chat_id=chat_id or None
    )
    return success_response(res, request["request_id"])

def handle_list_jobs(request: dict, kwargs: dict) -> tuple[int, bytes]:
    q = request.get("query_params", {})
    pid = q.get("project_id", [None])[0]
    status = q.get("status", [None])[0]
    limit = int(q.get("limit", [25])[0])
    jobs = ExecutionManager.list_jobs(project_id=pid, status=status, limit=limit)
    return success_response(jobs, request["request_id"])

def handle_get_job(request: dict, kwargs: dict) -> tuple[int, bytes]:
    jid = kwargs["job_id"]
    job = ExecutionManager.get_job(jid)
    if not job:
        return error_response("NOT_FOUND", f"Job '{jid}' not found.", request["request_id"], 404)
    return success_response(job, request["request_id"])

def handle_get_job_logs(request: dict, kwargs: dict) -> tuple[int, bytes]:
    jid = kwargs["job_id"]
    q = request.get("query_params", {})
    lines = int(q.get("lines", [50])[0])
    tail_param = q.get("tail", ["true"])[0]
    tail = tail_param.lower() in ("true", "1", "yes")
    res = ExecutionManager.get_job_logs(job_id=jid, lines=lines, tail=tail)
    return success_response(res, request["request_id"])

def handle_cancel_job(request: dict, kwargs: dict) -> tuple[int, bytes]:
    jid = kwargs["job_id"]
    res = ExecutionManager.cancel_job(jid)
    return success_response(res, request["request_id"])

router.add_route("POST", "/api/v1/agy/execute", handle_execute_agy)
router.add_route("GET", "/api/v1/agy/models", handle_list_models)
router.add_route("POST", "/api/v1/agy/model/switch", handle_switch_model)
router.add_route("GET", "/api/v1/agy/usage", handle_get_usage)
router.add_route("POST", "/api/v1/jobs/start", handle_start_job)
router.add_route("GET", "/api/v1/jobs", handle_list_jobs)
router.add_route("GET", "/api/v1/jobs/{job_id}", handle_get_job)
router.add_route("GET", "/api/v1/jobs/{job_id}/logs", handle_get_job_logs)
router.add_route("POST", "/api/v1/jobs/{job_id}/cancel", handle_cancel_job)

# ==================== Antigravity Instances & Tasks ====================
def handle_list_agy_instances(request: dict, kwargs: dict) -> tuple[int, bytes]:
    q = request.get("query_params", {})
    inc_hist = q.get("include_historical", ["true"])[0].lower() not in ("false", "0", "no")
    limit = int(q.get("limit", [20])[0])
    instances = AgyInstanceManager.discover_instances(include_historical=inc_hist, limit=limit)
    return success_response(instances, request["request_id"])

def handle_get_agy_instance(request: dict, kwargs: dict) -> tuple[int, bytes]:
    iid = kwargs["instance_id"]
    inst = AgyInstanceManager.get_instance_status(iid)
    if not inst:
        return error_response("NOT_FOUND", f"Antigravity instance '{iid}' not found.", request["request_id"], 404)
    return success_response(inst, request["request_id"])

def handle_start_agy_instance(request: dict, kwargs: dict) -> tuple[int, bytes]:
    body = validate_dict(request.get("body", {}))
    pid = validate_optional_string(body, "project_id")
    prompt = validate_optional_string(body, "prompt")
    model = validate_optional_string(body, "model")
    agent = validate_optional_string(body, "agent")
    mode = validate_optional_string(body, "mode")
    conv_id = validate_optional_string(body, "conversation_id")
    timeout = validate_optional_int(body, "timeout")
    chat_id = validate_optional_string(body, "telegram_chat_id")
    res = AgyInstanceManager.start_instance(
        project_id=pid,
        prompt=prompt,
        model=model,
        agent=agent,
        mode=mode,
        conversation_id=conv_id,
        timeout=timeout,
        telegram_chat_id=chat_id
    )
    return success_response(res, request["request_id"], status_code=201)

def handle_stop_agy_instance(request: dict, kwargs: dict) -> tuple[int, bytes]:
    iid = kwargs["instance_id"]
    res = AgyInstanceManager.stop_instance(iid)
    return success_response(res, request["request_id"])

def handle_get_agy_instance_output(request: dict, kwargs: dict) -> tuple[int, bytes]:
    iid = kwargs["instance_id"]
    q = request.get("query_params", {})
    lines = int(q.get("lines", [50])[0])
    tail_param = q.get("tail", ["true"])[0]
    tail = tail_param.lower() in ("true", "1", "yes")
    res = AgyInstanceManager.get_instance_output(iid, lines=lines, tail=tail)
    return success_response(res, request["request_id"])

def handle_submit_agy_task(request: dict, kwargs: dict) -> tuple[int, bytes]:
    body = validate_dict(request.get("body", {}))
    prompt = validate_required_string(body, "prompt")
    pid = validate_optional_string(body, "project_id")
    conv_id = validate_optional_string(body, "conversation_id")
    model = validate_optional_string(body, "model")
    agent = validate_optional_string(body, "agent")
    mode = validate_optional_string(body, "mode")
    timeout = validate_optional_int(body, "timeout")
    chat_id = validate_optional_string(body, "telegram_chat_id")
    res = AgyInstanceManager.submit_task(
        prompt=prompt,
        project_id=pid,
        conversation_id=conv_id,
        model=model,
        agent=agent,
        mode=mode,
        timeout=timeout,
        telegram_chat_id=chat_id
    )
    return success_response(res, request["request_id"], status_code=201)

def handle_get_agy_task_status(request: dict, kwargs: dict) -> tuple[int, bytes]:
    tid = kwargs["task_id"]
    res = AgyInstanceManager.get_task_status(tid)
    return success_response(res, request["request_id"])

router.add_route("GET", "/api/v1/agy/instances", handle_list_agy_instances)
router.add_route("GET", "/api/v1/agy/instances/{instance_id}", handle_get_agy_instance)
router.add_route("POST", "/api/v1/agy/instances/start", handle_start_agy_instance)
router.add_route("POST", "/api/v1/agy/instances/{instance_id}/stop", handle_stop_agy_instance)
router.add_route("GET", "/api/v1/agy/instances/{instance_id}/output", handle_get_agy_instance_output)
router.add_route("POST", "/api/v1/agy/tasks/submit", handle_submit_agy_task)
router.add_route("GET", "/api/v1/agy/tasks/{task_id}", handle_get_agy_task_status)

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

# ==================== Telegram Conversation Sessions ====================
def handle_get_or_create_session(request: dict, kwargs: dict) -> tuple[int, bytes]:
    body = validate_dict(request.get("body", {}))
    chat_id = validate_required_string(body, "telegram_chat_id")
    user_id = validate_required_string(body, "telegram_user_id")
    project_id = validate_optional_string(body, "project_id", default="")
    message_id = validate_optional_string(body, "message_id", default="")
    user_prompt = validate_optional_string(body, "user_prompt", default="")
    res = SessionManager.get_or_create_session(
        telegram_chat_id=chat_id,
        telegram_user_id=user_id,
        project_id=project_id or None,
        message_id=message_id or None,
        user_prompt=user_prompt
    )
    return success_response(res, request["request_id"])

def handle_add_session_turn(request: dict, kwargs: dict) -> tuple[int, bytes]:
    body = validate_dict(request.get("body", {}))
    session_id = validate_required_string(body, "session_id")
    user_text = validate_required_string(body, "user_text")
    agent_output = validate_required_string(body, "agent_output")
    max_turns = int(body.get("max_turns", 15))
    res = SessionManager.add_turn(
        session_id=session_id,
        user_text=user_text,
        agent_output=agent_output,
        max_turns=max_turns
    )
    return success_response(res, request["request_id"])

def handle_close_session(request: dict, kwargs: dict) -> tuple[int, bytes]:
    body = validate_dict(request.get("body", {}))
    session_id = validate_optional_string(body, "session_id", default="")
    chat_id = validate_optional_string(body, "telegram_chat_id", default="")
    user_id = validate_optional_string(body, "telegram_user_id", default="")
    status = validate_optional_string(body, "status", default="completed")
    reason = validate_optional_string(body, "reason", default="")
    res = SessionManager.close_session(
        session_id=session_id or None,
        telegram_chat_id=chat_id or None,
        telegram_user_id=user_id or None,
        status=status,
        reason=reason
    )
    return success_response(res, request["request_id"])

def handle_get_active_session(request: dict, kwargs: dict) -> tuple[int, bytes]:
    q = request.get("query_params", {})
    chat_id = (q.get("telegram_chat_id") or q.get("chat_id") or [None])[0]
    user_id = (q.get("telegram_user_id") or q.get("user_id") or [None])[0]
    if not chat_id or not user_id:
        raise ValidationError("telegram_chat_id and telegram_user_id query params are required.")
    res = SessionManager.get_active_session(chat_id, user_id)
    return success_response(res, request["request_id"])

def handle_start_typing(request: dict, kwargs: dict) -> tuple[int, bytes]:
    body = validate_dict(request.get("body", {}))
    session_id = validate_required_string(body, "session_id")
    chat_id = validate_required_string(body, "chat_id")
    interval = float(body.get("interval", 4.0))
    started = TelegramTypingService.start_heartbeat(session_id, chat_id, interval=interval)
    return success_response({"session_id": session_id, "started": started}, request["request_id"])

def handle_stop_typing(request: dict, kwargs: dict) -> tuple[int, bytes]:
    body = validate_dict(request.get("body", {}))
    session_id = validate_required_string(body, "session_id")
    stopped = TelegramTypingService.stop_heartbeat(session_id)
    return success_response({"session_id": session_id, "stopped": stopped}, request["request_id"])

router.add_route("POST", "/api/v1/sessions/get-or-create", handle_get_or_create_session)
router.add_route("POST", "/api/v1/sessions/add-turn", handle_add_session_turn)
router.add_route("POST", "/api/v1/sessions/close", handle_close_session)
router.add_route("GET", "/api/v1/sessions/active", handle_get_active_session)
router.add_route("POST", "/api/v1/sessions/typing/start", handle_start_typing)
router.add_route("POST", "/api/v1/sessions/typing/stop", handle_stop_typing)

# ==================== Centralized Skill System ====================
def handle_search_skills(request: dict, kwargs: dict) -> tuple[int, bytes]:
    body = request.get("body", {}) or {}
    qp = request.get("query_params", {})
    query = body.get("query") or (qp.get("query", [""])[0] if "query" in qp else "")
    category = body.get("category") or (qp.get("category", [None])[0] if "category" in qp else None)
    agent_id = body.get("agent_id") or (qp.get("agent_id", [None])[0] if "agent_id" in qp else None)
    limit = body.get("limit") or (int(qp.get("limit", [10])[0]) if "limit" in qp else 10)
    results = SkillSelector.search_catalog(query=query, category=category, agent_id=agent_id, limit=int(limit))
    return success_response(results, request["request_id"])

def handle_select_skills(request: dict, kwargs: dict) -> tuple[int, bytes]:
    body = validate_dict(request.get("body", {}))
    task_desc = body.get("task") or body.get("task_description") or body.get("query", "")
    agent_id = body.get("agent_id", "aegis-orchestrator")
    tech_stack = body.get("tech_stack")
    max_skills = int(body.get("max_skills", 3))
    res = SkillSelector.select_skills_for_task(
        task_description=task_desc,
        agent_id=agent_id,
        project_tech_stack=tech_stack,
        max_skills=max_skills
    )
    return success_response(res, request["request_id"])

def handle_inspect_skill(request: dict, kwargs: dict) -> tuple[int, bytes]:
    sid = kwargs.get("skill_id")
    if not sid:
        raise ValidationError("Parameter 'skill_id' is required.")
    instructions = SkillSelector.load_skill_instructions(sid)
    audit = SkillSelector.audit_skill_content(sid, instructions or "")
    res = {
        "skill_id": sid,
        "is_vaulted": instructions is not None,
        "security_audit": audit,
        "instructions_preview": instructions[:500] if instructions else None
    }
    return success_response(res, request["request_id"])

def handle_activate_skill(request: dict, kwargs: dict) -> tuple[int, bytes]:
    body = validate_dict(request.get("body", {}))
    sid = validate_required_string(body, "skill_id")
    ws_path = body.get("workspace_path") or body.get("path")
    if not ws_path:
        pid = body.get("project_id")
        if pid:
            proj = ProjectAnalyzer.get_project(pid)
            if proj:
                ws_path = proj.get("path")
    if not ws_path:
        raise ValidationError("Parameter 'workspace_path' or 'project_id' is required to activate a skill.")
    res = SkillSelector.activate_for_workspace(sid, ws_path)
    return success_response(res, request["request_id"])

router.add_route("GET", "/api/v1/skills/search", handle_search_skills)
router.add_route("POST", "/api/v1/skills/search", handle_search_skills)
router.add_route("POST", "/api/v1/skills/select", handle_select_skills)
router.add_route("GET", "/api/v1/skills/inspect/{skill_id}", handle_inspect_skill)
router.add_route("POST", "/api/v1/skills/activate", handle_activate_skill)

# ==================== Generic Tool Dispatch ====================
def handle_tool_dispatch(request: dict, kwargs: dict) -> tuple[int, bytes]:
    """Single dispatch endpoint for n8n AI Agent tool calling."""
    body = validate_dict(request.get("body", {}))
    tool_name = body.get("tool") or body.get("action")
    if not tool_name or not isinstance(tool_name, str) or not tool_name.strip():
        raise ValidationError("Field 'tool' (or 'action') is required and must be a non-empty string.")
    tool_name = tool_name.strip()

    params = body.get("params")
    if params is None:
        params = body.get("parameters", {})
    if not isinstance(params, dict):
        params = {}

    approval_id = body.get("approval_id") or body.get("approval_token")
    headers = request.get("headers", {})
    execution_id = body.get("execution_id") or params.get("execution_id") or headers.get("x-execution-id")
    session_id = body.get("session_id") or params.get("session_id") or headers.get("x-session-id")
    objective = body.get("objective") or params.get("objective")

    try:
        res = ToolRouter.dispatch(
            tool_name,
            params=params,
            approval_id=approval_id,
            execution_id=execution_id,
            session_id=session_id,
            objective=objective
        )
        return success_response(res, request["request_id"])
    except ApprovalRequiredException as are:
        return error_response(
            code="APPROVAL_REQUIRED",
            message=str(are),
            request_id=request["request_id"],
            status_code=403
        )

router.add_route("POST", "/api/v1/tools/dispatch", handle_tool_dispatch)
