"""Aegis Intelligence - Tool Router & Dispatcher

Provides a centralized registry of tools exposed to n8n and Gemini with
parameter validation, alias normalization, and permission enforcement.
"""

import time
from typing import Any, Optional
from storage.database import db_session
from core.permission_manager import PermissionManager
from core.execution_ledger import ExecutionLedger
from intelligence.project_analyzer import ProjectAnalyzer
from intelligence.development_monitor import DevelopmentMonitor
from intelligence.task_manager import TaskManager
from intelligence.bug_tracker import BugTracker
from intelligence.project_memory import ProjectMemory
from intelligence.context_builder import ContextBuilder
from intelligence.report_generator import ReportGenerator
from intelligence.session_manager import SessionManager
from integrations.git import GitIntegration
from integrations.filesystem import FilesystemIntegration
from integrations.model_manager import ModelManager
from integrations.usage_monitor import UsageMonitor
from core.execution_manager import ExecutionManager
from core.agy_instance_manager import AgyInstanceManager
from security.approvals import list_approvals, get_approval, decide_approval
from security.audit_log import get_recent_audit_logs
from skill_system.selector import SkillSelector

class ToolRouter:
    """Dispatches tool executions with parameter validation and permission checks."""

    # Comprehensive alias map normalizing verb-first or alternative names to canonical form
    ALIAS_MAP = {
        # Project aliases
        "list_projects": "project_list",
        "register_project": "project_register",
        "inspect_project": "project_inspect",
        "assess_project": "project_assessment",
        "project_assess": "project_assessment",
        "project_overview": "project_assessment",
        "project_status_report": "project_assessment",
        "get_project": "project_get",
        "project_detail": "project_get",
        "update_project": "project_update",
        "delete_project": "project_delete",
        "set_active_project": "project_set_active",
        "project_brief": "project_context",
        "projects_compare": "project_compare",
        "compare_projects": "project_compare",

        # Task aliases
        "list_tasks": "task_list",
        "create_task": "task_create",
        "update_task": "task_update",
        "complete_task": "task_complete",
        "delete_task": "task_delete",
        "get_task": "task_get",
        "overdue_tasks": "task_overdue",

        # Bug aliases
        "list_bugs": "bug_list",
        "create_bug": "bug_create",
        "update_bug": "bug_update",
        "resolve_bug": "bug_resolve",
        "delete_bug": "bug_delete",
        "get_bug": "bug_get",

        # Memory aliases
        "list_memory": "memory_search",
        "memory_list": "memory_search",
        "create_memory": "memory_record",
        "record_memory": "memory_record",
        "search_memory": "memory_search",
        "get_memory": "memory_get",
        "update_memory": "memory_update",
        "delete_memory": "memory_delete",

        # Git aliases
        "git_log": "git_commits",
        "get_contributors": "git_contributors",

        # Filesystem aliases
        "read_file": "file_read",
        "inspect_filesystem": "filesystem_inspect",
        "recent_files": "filesystem_recent_files",

        # Reports & Health aliases
        "generate_report": "report_generate",
        "health_check": "system_health",
        "health": "system_health",
        "check_health": "system_health",

        # Antigravity & Model aliases
        "list_models": "agy_models_list",
        "model_switch": "agy_model_switch",
        "usage_summary": "agy_usage_summary",
        "agy_execute_query": "agy_execute",
        "execute_agy": "agy_execute",
        "job_start": "job_start",
        "start_job": "job_start",
        "run_job": "job_start",
        "background_execute": "job_start",
        "bg_execute": "job_start",
        "list_jobs": "job_list",
        "get_jobs": "job_list",
        "get_job": "job_get",
        "job_status": "job_get",
        "job_logs": "job_logs",
        "get_job_logs": "job_logs",
        "job_log": "job_logs",
        "job_cancel": "job_cancel",
        "cancel_job": "job_cancel",
        "stop_job": "job_cancel",
        "kill_job": "job_cancel",

        # Antigravity Instance & Task aliases
        "list_agy_instances": "agy_instance_list",
        "agy_instances": "agy_instance_list",
        "active_agy_instances": "agy_instance_list",
        "get_agy_instance": "agy_instance_status",
        "agy_status": "agy_instance_status",
        "start_agy_instance": "agy_instance_start",
        "start_agy": "agy_instance_start",
        "stop_agy_instance": "agy_instance_stop",
        "kill_agy_instance": "agy_instance_stop",
        "stop_agy": "agy_instance_stop",
        "agy_output": "agy_instance_output",
        "agy_logs": "agy_instance_output",
        "get_agy_output": "agy_instance_output",
        "submit_agy_task": "agy_task_submit",
        "run_agy_task": "agy_task_submit",
        "get_agy_task_status": "agy_task_status",
        "agy_task_result": "agy_task_status",

        # Approval & Audit aliases
        "list_approvals": "approval_list",
        "get_approval": "approval_get",
        "decide_approval": "approval_decide",
        "get_audit_logs": "audit_logs_get",

        # Session aliases
        "get_or_create_session": "session_get_or_create",
        "add_turn": "session_add_turn",
        "close_session": "session_close",
        "stop_chat": "session_close",
        "check_dedup": "session_check_dedup",
        "get_session": "session_get",
        "list_sessions": "session_list",

        # Execution Ledger & Progress aliases
        "get_execution_progress": "execution_progress",
        "ledger_progress": "execution_progress",
        "ledger_get": "execution_progress",

        # Skill System aliases
        "search_skills": "skill_search",
        "select_skills": "skill_select",
        "inspect_skill": "skill_inspect",
        "activate_skill": "skill_activate",
    }

    @classmethod
    def dispatch(
        cls,
        tool_name: str,
        params: dict = None,
        approval_id: Optional[str] = None,
        execution_id: Optional[str] = None,
        session_id: Optional[str] = None,
        objective: Optional[str] = None
    ) -> Any:
        """Route and execute a tool by name with alias normalization, permission enforcement, and execution ledger safeguards."""
        p = params or {}
        exec_id = execution_id or p.get("execution_id")
        sess_id = session_id or p.get("session_id")
        obj = objective or p.get("objective")
        tool_raw = tool_name.lower().strip()
        tool = cls.ALIAS_MAP.get(tool_raw, tool_raw)

        # Permission gate check
        project_id = p.get("project_id")
        PermissionManager.enforce_permission(
            action=tool,
            params=p,
            approval_id=approval_id,
            project_id=project_id
        )

        start_time = time.time()
        if exec_id:
            is_allowed, cached_or_limit_resp, reason = ExecutionLedger.record_action_start(
                execution_id=exec_id,
                action=tool,
                params=p,
                session_id=sess_id,
                objective=obj
            )
            if not is_allowed:
                return cached_or_limit_resp

        try:
            res = cls._execute_action(tool, p)
            if exec_id:
                duration_ms = int((time.time() - start_time) * 1000)
                ExecutionLedger.record_action_success(
                    execution_id=exec_id,
                    action=tool,
                    params=p,
                    result=res,
                    duration_ms=duration_ms
                )
            return res
        except Exception as e:
            if exec_id:
                duration_ms = int((time.time() - start_time) * 1000)
                ExecutionLedger.record_action_failure(
                    execution_id=exec_id,
                    action=tool,
                    params=p,
                    error=str(e),
                    duration_ms=duration_ms
                )
            raise

    @classmethod
    def _execute_action(cls, tool: str, p: dict) -> Any:
        """Internal router dispatching verified actions to subsystem handlers."""
        # 1. Project Management
        if tool == "project_register":
            return ProjectAnalyzer.register_project(
                name=p["name"],
                path=p["path"],
                description=p.get("description", ""),
                project_id=p.get("project_id")
            )
        elif tool == "project_list":
            return ProjectAnalyzer.list_projects()
        elif tool == "project_get":
            pid = p.get("project_id") or (ProjectAnalyzer.get_active_project() or {}).get("id")
            if not pid:
                raise ValueError("Project ID is required or an active project must be set.")
            proj = ProjectAnalyzer.get_project(pid)
            if not proj:
                raise ValueError(f"Project '{pid}' not found.")
            with db_session() as conn:
                task_count = conn.execute("SELECT COUNT(*) FROM tasks WHERE project_id = ?", (pid,)).fetchone()[0]
                bug_count = conn.execute("SELECT COUNT(*) FROM bugs WHERE project_id = ?", (pid,)).fetchone()[0]
                mem_count = conn.execute("SELECT COUNT(*) FROM project_memory WHERE project_id = ?", (pid,)).fetchone()[0]
                proj["counts"] = {"tasks": task_count, "bugs": bug_count, "memory_items": mem_count}
            return proj
        elif tool == "project_update":
            pid = p.get("project_id") or (ProjectAnalyzer.get_active_project() or {}).get("id")
            if not pid:
                raise ValueError("Project ID is required or an active project must be set.")
            upd = {k: v for k, v in p.items() if k != "project_id"}
            return ProjectAnalyzer.update_project(pid, **upd)
        elif tool == "project_delete":
            pid = p.get("project_id")
            if not pid:
                raise ValueError("project_id is required to unregister a project.")
            success = ProjectAnalyzer.remove_project(pid)
            if not success:
                raise ValueError(f"Project '{pid}' not found.")
            return {"unregistered": True, "project_id": pid}
        elif tool == "project_inspect":
            pid = p.get("project_id") or (ProjectAnalyzer.get_active_project() or {}).get("id")
            if not pid:
                raise ValueError("No project specified or active.")
            return ProjectAnalyzer.inspect_project(pid)
        elif tool == "project_assessment":
            pid = p.get("project_id") or (ProjectAnalyzer.get_active_project() or {}).get("id")
            if not pid:
                raise ValueError("Project ID is required or an active project must be set.")
            sections = p.get("sections")
            if sections is not None and not isinstance(sections, list):
                raise ValueError("Parameter 'sections' must be a list of strings if provided.")
            return ProjectAnalyzer.assess_project(
                project_id=pid,
                sections=sections,
                memory_limit=int(p.get("memory_limit", 15)),
                recent_files_limit=int(p.get("recent_files_limit", 10)),
                commits_count=int(p.get("commits_count", 5)),
                execute_tests=bool(p.get("execute_tests", False))
            )
        elif tool == "project_set_active":
            return ProjectAnalyzer.set_active_project(p["project_id"])
        elif tool == "project_context":
            return {"context": ContextBuilder.build_agent_context(p.get("project_id"))}
        elif tool == "project_compare":
            pids = p.get("project_ids")
            if not pids:
                pids = [proj["id"] for proj in ProjectAnalyzer.list_projects()]
            return ProjectAnalyzer.compare_projects(pids)

        # 2. Project Health, Diagnostics & Reports
        elif tool == "system_health":
            from config import Config
            db_ok = False
            try:
                from storage.database import get_connection
                conn = get_connection()
                conn.execute("SELECT 1").fetchone()
                db_ok = True
            except Exception:
                pass
            return {
                "status": "healthy" if db_ok else "degraded",
                "service": "aegis-intelligence",
                "version": "1.0.0",
                "database": "connected" if db_ok else "disconnected",
                "host": Config.HOST,
                "port": Config.PORT
            }
        elif tool == "development_health":
            pid = p.get("project_id") or (ProjectAnalyzer.get_active_project() or {}).get("id")
            if not pid:
                raise ValueError("No project specified or active.")
            proj = ProjectAnalyzer.get_project(pid)
            if not proj:
                raise ValueError(f"Project '{pid}' not found.")
            execute_tests = bool(p.get("execute_tests", False))
            return DevelopmentMonitor.evaluate_health(pid, proj["path"], execute_tests=execute_tests)
        elif tool == "report_generate":
            return {"report": ReportGenerator.generate_report(p.get("report_type", "status"), p.get("project_id"))}

        # 3. Tasks
        elif tool == "task_create":
            return TaskManager.create_task(
                project_id=p["project_id"],
                title=p["title"],
                description=p.get("description", ""),
                status=p.get("status", "pending"),
                priority=p.get("priority", "medium"),
                due_date=p.get("due_date"),
                related_files=p.get("related_files"),
                notes=p.get("notes", "")
            )
        elif tool == "task_get":
            tid = p.get("task_id")
            if not tid:
                raise ValueError("task_id is required.")
            task = TaskManager.get_task(tid)
            if not task:
                raise ValueError(f"Task '{tid}' not found.")
            return task
        elif tool == "task_update":
            tid = p["task_id"]
            upd = {k: v for k, v in p.items() if k != "task_id"}
            return TaskManager.update_task(tid, **upd)
        elif tool == "task_complete":
            return TaskManager.complete_task(p["task_id"], notes=p.get("notes", ""))
        elif tool == "task_delete":
            tid = p.get("task_id")
            if not tid:
                raise ValueError("task_id is required.")
            success = TaskManager.delete_task(tid)
            if not success:
                raise ValueError(f"Task '{tid}' not found.")
            return {"deleted": True, "task_id": tid}
        elif tool == "task_list":
            return TaskManager.list_tasks(
                project_id=p.get("project_id"),
                status=p.get("status"),
                priority=p.get("priority"),
                limit=p.get("limit", 100)
            )
        elif tool == "task_summary":
            pid = p.get("project_id") or (ProjectAnalyzer.get_active_project() or {}).get("id")
            if not pid:
                raise ValueError("project_id is required or an active project must be set.")
            return TaskManager.get_summary(pid)
        elif tool == "task_overdue":
            pid = p.get("project_id") or (ProjectAnalyzer.get_active_project() or {}).get("id")
            return TaskManager.get_overdue_tasks(pid)

        # 4. Bugs
        elif tool == "bug_create":
            return BugTracker.create_bug(
                project_id=p["project_id"],
                title=p["title"],
                severity=p.get("severity", "medium"),
                reproduction_steps=p.get("reproduction_steps", ""),
                affected_files=p.get("affected_files"),
                diagnosis=p.get("diagnosis", ""),
                verification_status=p.get("verification_status", "unverified")
            )
        elif tool == "bug_get":
            bid = p.get("bug_id")
            if not bid:
                raise ValueError("bug_id is required.")
            bug = BugTracker.get_bug(bid)
            if not bug:
                raise ValueError(f"Bug '{bid}' not found.")
            return bug
        elif tool == "bug_update":
            bid = p["bug_id"]
            upd = {k: v for k, v in p.items() if k != "bug_id"}
            return BugTracker.update_bug(bid, **upd)
        elif tool == "bug_resolve":
            return BugTracker.resolve_bug(p["bug_id"], resolution=p.get("resolution", ""), verified=p.get("verified", False))
        elif tool == "bug_delete":
            bid = p.get("bug_id")
            if not bid:
                raise ValueError("bug_id is required.")
            success = BugTracker.delete_bug(bid)
            if not success:
                raise ValueError(f"Bug '{bid}' not found.")
            return {"deleted": True, "bug_id": bid}
        elif tool == "bug_list":
            return BugTracker.list_bugs(
                project_id=p.get("project_id"),
                severity=p.get("severity"),
                verification_status=p.get("verification_status"),
                limit=p.get("limit", 100)
            )
        elif tool == "bug_summary":
            pid = p.get("project_id") or (ProjectAnalyzer.get_active_project() or {}).get("id")
            if not pid:
                raise ValueError("project_id is required or an active project must be set.")
            return BugTracker.get_summary(pid)

        # 5. Persistent Memory
        elif tool == "memory_record":
            return ProjectMemory.record_memory(
                project_id=p["project_id"],
                title=p["title"],
                content=p["content"],
                category=p.get("category", "general"),
                source=p.get("source", "user"),
                confidence=p.get("confidence", "verified")
            )
        elif tool == "memory_get":
            mid = p.get("memory_id")
            if not mid:
                raise ValueError("memory_id is required.")
            mem = ProjectMemory.get_memory(mid)
            if not mem:
                raise ValueError(f"Memory '{mid}' not found.")
            return mem
        elif tool == "memory_update":
            mid = p.get("memory_id")
            if not mid:
                raise ValueError("memory_id is required.")
            upd = {k: v for k, v in p.items() if k != "memory_id"}
            return ProjectMemory.update_memory(mid, **upd)
        elif tool == "memory_delete":
            mid = p.get("memory_id")
            if not mid:
                raise ValueError("memory_id is required.")
            success = ProjectMemory.delete_memory(mid)
            if not success:
                raise ValueError(f"Memory '{mid}' not found.")
            return {"deleted": True, "memory_id": mid}
        elif tool == "memory_search":
            return ProjectMemory.search_memory(
                project_id=p["project_id"],
                query=p.get("query"),
                category=p.get("category"),
                limit=p.get("limit", 50)
            )

        # 6. Git Operations
        elif tool == "git_status":
            proj = ProjectAnalyzer.get_project(p.get("project_id")) if p.get("project_id") else ProjectAnalyzer.get_active_project()
            if not proj:
                raise ValueError("Project not found.")
            return GitIntegration.get_repo_status(proj["path"])
        elif tool == "git_commits":
            proj = ProjectAnalyzer.get_project(p.get("project_id")) if p.get("project_id") else ProjectAnalyzer.get_active_project()
            if not proj:
                raise ValueError("Project not found.")
            return GitIntegration.get_recent_commits(proj["path"], count=p.get("count", 10))
        elif tool == "git_diff":
            proj = ProjectAnalyzer.get_project(p.get("project_id")) if p.get("project_id") else ProjectAnalyzer.get_active_project()
            if not proj:
                raise ValueError("Project not found.")
            return {"diff": GitIntegration.get_diff(proj["path"], staged=p.get("staged", False))}
        elif tool == "git_contributors":
            proj = ProjectAnalyzer.get_project(p.get("project_id")) if p.get("project_id") else ProjectAnalyzer.get_active_project()
            if not proj:
                raise ValueError("Project not found.")
            return GitIntegration.get_contributors(proj["path"])

        # 7. Filesystem Operations
        elif tool == "file_read":
            proj = ProjectAnalyzer.get_project(p.get("project_id")) if p.get("project_id") else ProjectAnalyzer.get_active_project()
            if not proj:
                raise ValueError("Project not found.")
            return {"content": FilesystemIntegration.read_file_content(proj["path"], p["path"])}
        elif tool == "filesystem_inspect":
            proj = ProjectAnalyzer.get_project(p.get("project_id")) if p.get("project_id") else ProjectAnalyzer.get_active_project()
            if not proj:
                raise ValueError("Project not found.")
            max_depth = int(p.get("max_depth", 3))
            max_files = int(p.get("max_files", 200))
            return FilesystemIntegration.inspect_directory(proj["path"], max_depth=max_depth, max_files=max_files)
        elif tool == "filesystem_recent_files":
            proj = ProjectAnalyzer.get_project(p.get("project_id")) if p.get("project_id") else ProjectAnalyzer.get_active_project()
            if not proj:
                raise ValueError("Project not found.")
            limit = int(p.get("limit", 15))
            return FilesystemIntegration.get_recently_modified_files(proj["path"], limit=limit)

        # 8. Antigravity Execution & Jobs
        elif tool == "agy_models_list":
            return {"models": ModelManager.list_models(), "active_model": ModelManager.get_active_model()}
        elif tool == "agy_model_switch":
            return ModelManager.switch_model(p["model"])
        elif tool == "agy_usage_summary":
            return UsageMonitor.get_usage_summary()
        elif tool == "agy_execute":
            proj = ProjectAnalyzer.get_project(p.get("project_id")) if p.get("project_id") else ProjectAnalyzer.get_active_project()
            if not proj:
                raise ValueError("No active project found for execution.")
            return ExecutionManager.execute_job(
                project_path=proj["path"],
                prompt=p["prompt"],
                project_id=proj["id"],
                action=p.get("action", "execute"),
                model=p.get("model"),
                timeout=p.get("timeout"),
                mode=p.get("mode"),
                async_run=p.get("async", False)
            )
        elif tool == "job_start":
            cmd = p.get("command") or p.get("cmd")
            if not cmd:
                raise ValueError("Field 'command' is required for job_start.")
            pid = p.get("project_id")
            cwd = p.get("cwd") or p.get("working_directory")
            timeout = p.get("timeout")
            action_type = p.get("action")
            chat_id = p.get("telegram_chat_id")
            sess_id = p.get("session_id")
            if not chat_id and sess_id:
                try:
                    sess = SessionManager.get_session(sess_id)
                    if sess:
                        chat_id = sess.get("telegram_chat_id")
                except Exception:
                    pass
            return ExecutionManager.start_job(
                command=cmd,
                project_id=pid,
                cwd=cwd,
                timeout=timeout,
                action=action_type,
                telegram_chat_id=chat_id,
                session_id=sess_id
            )
        elif tool == "job_list":
            pid = p.get("project_id")
            status = p.get("status")
            limit = int(p.get("limit", 25))
            return ExecutionManager.list_jobs(project_id=pid, status=status, limit=limit)
        elif tool == "job_get":
            jid = p.get("job_id")
            if not jid:
                raise ValueError("job_id is required.")
            job = ExecutionManager.get_job(jid)
            if not job:
                raise ValueError(f"Job '{jid}' not found.")
            return job
        elif tool == "job_logs":
            jid = p.get("job_id")
            if not jid:
                raise ValueError("job_id is required.")
            lines = int(p.get("lines", 50))
            tail = bool(p.get("tail", True))
            return ExecutionManager.get_job_logs(job_id=jid, lines=lines, tail=tail)
        elif tool == "job_cancel":
            jid = p.get("job_id")
            if not jid:
                raise ValueError("job_id is required.")
            return ExecutionManager.cancel_job(job_id=jid)

        # Antigravity Instances & Task Orchestration
        elif tool == "agy_instance_list":
            include_hist = p.get("include_historical", True)
            if isinstance(include_hist, str):
                include_hist = include_hist.lower() not in ("false", "0", "no")
            limit = int(p.get("limit", 20))
            return AgyInstanceManager.discover_instances(include_historical=include_hist, limit=limit)
        elif tool == "agy_instance_status":
            target = p.get("instance_id") or p.get("pid") or p.get("target") or p.get("job_id")
            if not target:
                raise ValueError("Parameter 'instance_id' or 'pid' is required for agy_instance_status.")
            status_info = AgyInstanceManager.get_instance_status(target)
            if not status_info:
                raise ValueError(f"Instance '{target}' not found.")
            return status_info
        elif tool == "agy_instance_start":
            pid = p.get("project_id")
            prompt = p.get("prompt")
            model = p.get("model")
            agent = p.get("agent")
            mode = p.get("mode")
            conv_id = p.get("conversation_id")
            timeout = p.get("timeout")
            chat_id = p.get("telegram_chat_id")
            return AgyInstanceManager.start_instance(
                project_id=pid,
                prompt=prompt,
                model=model,
                agent=agent,
                mode=mode,
                conversation_id=conv_id,
                timeout=timeout,
                telegram_chat_id=chat_id
            )
        elif tool == "agy_instance_stop":
            target = p.get("instance_id") or p.get("pid") or p.get("target") or p.get("job_id")
            if not target:
                raise ValueError("Parameter 'instance_id' or 'pid' is required for agy_instance_stop.")
            return AgyInstanceManager.stop_instance(target)
        elif tool == "agy_instance_output":
            target = p.get("instance_id") or p.get("pid") or p.get("target") or p.get("job_id")
            if not target:
                raise ValueError("Parameter 'instance_id' or 'pid' is required for agy_instance_output.")
            lines = int(p.get("lines", 50))
            tail = bool(p.get("tail", True)) if "tail" in p else True
            return AgyInstanceManager.get_instance_output(target, lines=lines, tail=tail)
        elif tool == "agy_task_submit":
            prompt = p.get("prompt")
            if not prompt:
                raise ValueError("Field 'prompt' is required for agy_task_submit.")
            pid = p.get("project_id")
            conv_id = p.get("conversation_id")
            model = p.get("model")
            agent = p.get("agent")
            mode = p.get("mode")
            timeout = p.get("timeout")
            chat_id = p.get("telegram_chat_id")
            return AgyInstanceManager.submit_task(
                prompt=prompt,
                project_id=pid,
                conversation_id=conv_id,
                model=model,
                agent=agent,
                mode=mode,
                timeout=timeout,
                telegram_chat_id=chat_id
            )
        elif tool == "agy_task_status":
            task_id = p.get("task_id") or p.get("job_id") or p.get("instance_id")
            if not task_id:
                raise ValueError("Parameter 'task_id' is required for agy_task_status.")
            return AgyInstanceManager.get_task_status(task_id)

        # 9. Approvals & Auditing
        elif tool == "approval_list":
            return list_approvals(status=p.get("status"))
        elif tool == "approval_get":
            aid = p.get("approval_id")
            if not aid:
                raise ValueError("approval_id is required.")
            appr = get_approval(aid)
            if not appr:
                raise ValueError(f"Approval '{aid}' not found.")
            return appr
        elif tool == "approval_decide":
            return decide_approval(
                approval_id=p["approval_id"],
                decision=p["decision"],
                reason=p.get("reason", ""),
                actor=p.get("actor", "telegram_user")
            )
        elif tool == "audit_logs_get":
            return get_recent_audit_logs(limit=p.get("limit", 50), action=p.get("action"))

        # 10. Conversation Sessions
        elif tool == "session_get_or_create":
            return SessionManager.get_or_create_session(
                telegram_chat_id=p["telegram_chat_id"],
                telegram_user_id=p["telegram_user_id"],
                project_id=p.get("project_id"),
                message_id=p.get("message_id"),
                user_prompt=p.get("user_prompt", "")
            )
        elif tool == "session_add_turn":
            return SessionManager.add_turn(
                session_id=p["session_id"],
                user_text=p["user_text"],
                agent_output=p["agent_output"],
                max_turns=int(p.get("max_turns", 15))
            )
        elif tool == "session_close":
            return SessionManager.close_session(
                session_id=p.get("session_id"),
                telegram_chat_id=p.get("telegram_chat_id"),
                telegram_user_id=p.get("telegram_user_id"),
                status=p.get("status", "completed"),
                reason=p.get("reason", "")
            )
        elif tool == "session_check_dedup":
            is_dup = SessionManager.check_dedup(
                chat_id=p["chat_id"],
                message_id=p["message_id"]
            )
            return {"is_duplicate": is_dup}
        elif tool == "session_get":
            sid = p.get("session_id")
            if not sid:
                raise ValueError("session_id is required.")
            res = SessionManager.get_session(sid)
            if not res:
                raise ValueError(f"Session '{sid}' not found.")
            return res
        elif tool == "session_list":
            return SessionManager.list_sessions(
                telegram_chat_id=p.get("telegram_chat_id"),
                status=p.get("status"),
                limit=int(p.get("limit", 20))
            )

        # 11. Execution Ledger & Progress
        elif tool == "execution_progress":
            target_exec = p.get("execution_id")
            if not target_exec:
                raise ValueError("Parameter 'execution_id' is required for execution_progress.")
            return ExecutionLedger.get_execution_progress(target_exec)

        # 12. Centralized Skill System & Intelligent Routing
        elif tool == "skill_search":
            return SkillSelector.search_catalog(
                query=p.get("query", ""),
                category=p.get("category"),
                agent_id=p.get("agent_id"),
                limit=int(p.get("limit", 10))
            )
        elif tool == "skill_select":
            task_desc = p.get("task") or p.get("task_description") or p.get("query", "")
            return SkillSelector.select_skills_for_task(
                task_description=task_desc,
                agent_id=p.get("agent_id", "aegis-orchestrator"),
                project_tech_stack=p.get("tech_stack"),
                max_skills=int(p.get("max_skills", 3))
            )
        elif tool == "skill_inspect":
            sid = p.get("skill_id")
            if not sid:
                raise ValueError("Parameter 'skill_id' is required.")
            instructions = SkillSelector.load_skill_instructions(sid)
            audit = SkillSelector.audit_skill_content(sid, instructions or "")
            return {
                "skill_id": sid,
                "is_vaulted": instructions is not None,
                "security_audit": audit,
                "instructions_preview": instructions[:500] if instructions else None
            }
        elif tool == "skill_activate":
            sid = p.get("skill_id")
            if not sid:
                raise ValueError("Parameter 'skill_id' is required.")
            ws_path = p.get("workspace_path") or p.get("path")
            if not ws_path:
                pid = p.get("project_id")
                if pid:
                    proj = ProjectAnalyzer.get_project(pid)
                    if proj:
                        ws_path = proj.get("path")
            if not ws_path:
                raise ValueError("Parameter 'workspace_path' or 'project_id' is required to activate a skill.")
            return SkillSelector.activate_for_workspace(sid, ws_path)

        else:
            raise ValueError(f"Unknown tool name '{tool}'.")
