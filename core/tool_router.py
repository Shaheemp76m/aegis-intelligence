"""Aegis Intelligence - Tool Router & Dispatcher

Provides a centralized registry of tools exposed to n8n and Gemini with
parameter validation and permission enforcement.
"""

from typing import Any, Optional
from core.permission_manager import PermissionManager
from intelligence.project_analyzer import ProjectAnalyzer
from intelligence.development_monitor import DevelopmentMonitor
from intelligence.task_manager import TaskManager
from intelligence.bug_tracker import BugTracker
from intelligence.project_memory import ProjectMemory
from intelligence.context_builder import ContextBuilder
from intelligence.report_generator import ReportGenerator
from integrations.git import GitIntegration
from integrations.filesystem import FilesystemIntegration
from integrations.model_manager import ModelManager
from integrations.usage_monitor import UsageMonitor
from core.execution_manager import ExecutionManager
from security.approvals import list_approvals, decide_approval
from security.audit_log import get_recent_audit_logs

class ToolRouter:
    """Dispatches tool executions with parameter validation and permission checks."""

    @classmethod
    def dispatch(cls, tool_name: str, params: dict = None, approval_id: Optional[str] = None) -> Any:
        """Route and execute a tool by name."""
        p = params or {}
        tool = tool_name.lower().strip()

        # Permission gate check
        project_id = p.get("project_id")
        PermissionManager.enforce_permission(
            action=tool,
            params=p,
            approval_id=approval_id,
            project_id=project_id
        )

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
        elif tool == "project_inspect":
            pid = p.get("project_id") or (ProjectAnalyzer.get_active_project() or {}).get("id")
            if not pid:
                raise ValueError("No project specified or active.")
            return ProjectAnalyzer.inspect_project(pid)
        elif tool == "project_set_active":
            return ProjectAnalyzer.set_active_project(p["project_id"])
        elif tool == "project_brief" or tool == "project_context":
            return {"context": ContextBuilder.build_agent_context(p.get("project_id"))}
        elif tool in ("project_compare", "projects_compare"):
            pids = p.get("project_ids")
            if not pids:
                pids = [proj["id"] for proj in ProjectAnalyzer.list_projects()]
            return ProjectAnalyzer.compare_projects(pids)

        # 2. Git & Filesystem
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
        elif tool == "file_read":
            proj = ProjectAnalyzer.get_project(p.get("project_id")) if p.get("project_id") else ProjectAnalyzer.get_active_project()
            if not proj:
                raise ValueError("Project not found.")
            return {"content": FilesystemIntegration.read_file_content(proj["path"], p["path"])}

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
        elif tool == "task_update":
            tid = p["task_id"]
            upd = {k: v for k, v in p.items() if k != "task_id"}
            return TaskManager.update_task(tid, **upd)
        elif tool == "task_complete":
            return TaskManager.complete_task(p["task_id"], notes=p.get("notes", ""))
        elif tool == "task_list":
            return TaskManager.list_tasks(
                project_id=p.get("project_id"),
                status=p.get("status"),
                priority=p.get("priority"),
                limit=p.get("limit", 100)
            )
        elif tool == "task_summary":
            return TaskManager.get_summary(p["project_id"])

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
        elif tool == "bug_update":
            bid = p["bug_id"]
            upd = {k: v for k, v in p.items() if k != "bug_id"}
            return BugTracker.update_bug(bid, **upd)
        elif tool == "bug_resolve":
            return BugTracker.resolve_bug(p["bug_id"], resolution=p.get("resolution", ""), verified=p.get("verified", False))
        elif tool == "bug_list":
            return BugTracker.list_bugs(
                project_id=p.get("project_id"),
                severity=p.get("severity"),
                verification_status=p.get("verification_status"),
                limit=p.get("limit", 100)
            )

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
        elif tool == "memory_search":
            return ProjectMemory.search_memory(
                project_id=p["project_id"],
                query=p.get("query"),
                category=p.get("category"),
                limit=p.get("limit", 50)
            )

        # 6. Reports
        elif tool == "report_generate":
            return {"report": ReportGenerator.generate_report(p.get("report_type", "status"), p.get("project_id"))}

        # 7. Antigravity & Execution
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

        # 8. Approvals & Auditing
        elif tool == "approval_list":
            return list_approvals(status=p.get("status"))
        elif tool == "approval_decide":
            return decide_approval(
                approval_id=p["approval_id"],
                decision=p["decision"],
                reason=p.get("reason", ""),
                actor=p.get("actor", "telegram_user")
            )
        elif tool == "audit_logs_get":
            return get_recent_audit_logs(limit=p.get("limit", 50), action=p.get("action"))

        else:
            raise ValueError(f"Unknown tool name '{tool_name}'.")
