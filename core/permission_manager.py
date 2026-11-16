"""Aegis Intelligence - Autonomy & Permission Manager

Classifies operations by risk, defines autonomy boundaries, and enforces
mandatory approval gates according to safety protocols.
"""

from typing import Optional
from security.approvals import (
    create_approval_request,
    verify_and_consume_approval,
    ApprovalRequiredException
)

class RiskLevel:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

# Prohibited destructive git commands and flags
DESTRUCTIVE_GIT_FLAGS = {
    "--hard",
    "-fdx",
    "-f",
    "--force",
    "--force-with-lease",
}

class PermissionManager:
    """Evaluates operations and enforces autonomy rules vs approval gates."""

    @staticmethod
    def classify_action(action: str, params: dict = None) -> tuple[str, bool, str]:
        """Classify an action into (risk_level, requires_approval, rationale)."""
        p = params or {}
        act = action.lower().strip()

        # Check for system/n8n/termux tampering
        if act in ("system_install", "apt_install", "pkg_install"):
            return RiskLevel.HIGH, True, "System-wide package installation requires approval."

        if act in ("modify_n8n", "edit_n8n_config"):
            return RiskLevel.CRITICAL, True, "Modifying n8n infrastructure is strictly gated."

        if act in ("delete_project_dir", "delete_project_files", "delete_project", "project_delete"):
            return RiskLevel.CRITICAL, True, "Deleting or unregistering a project requires explicit confirmation."

        if act == "bulk_file_delete":
            return RiskLevel.HIGH, True, "Bulk file deletion (>3 files) triggers safety gate."

        # Database record deletions (autonomous, medium risk)
        if act in ("task_delete", "delete_task", "bug_delete", "delete_bug", "memory_delete", "delete_memory"):
            return RiskLevel.MEDIUM, False, "Autonomous deletion of task, bug, or memory database record."

        # Check Git operations
        if act == "git_command":
            subcmd = p.get("git_subcommand", "")
            args = p.get("args", [])
            if "push" in subcmd and any(f in args for f in ("--force", "-f", "--force-with-lease")):
                return RiskLevel.CRITICAL, True, "Git force pushing is a destructive operation."
            if "reset" in subcmd and "--hard" in args:
                return RiskLevel.CRITICAL, True, "Git reset --hard destroys uncommitted changes."
            if "clean" in subcmd and any(f in args for f in ("-fdx", "-f", "-fd")):
                return RiskLevel.HIGH, True, "Git clean destroys untracked files."

        # Out-of-bounds path check
        if p.get("is_out_of_bounds", False):
            return RiskLevel.CRITICAL, True, "Operation attempts to touch filesystem outside registered project root."

        # Autonomous read and inspection operations (support both tool_action and action_tool naming)
        if act in (
            "read_file", "file_read",
            "filesystem_inspect", "inspect_filesystem",
            "filesystem_recent_files", "recent_files",
            "inspect_project", "project_inspect",
            "project_assessment", "assess_project", "project_assess", "project_overview", "project_status_report",
            "project_list", "list_projects",
            "project_get", "get_project", "project_detail",
            "project_update", "update_project",
            "project_register", "register_project",
            "project_set_active", "set_active_project",
            "project_brief", "project_context",
            "project_compare", "projects_compare", "compare_projects",
            "git_status", "git_log", "git_commits", "git_diff", "git_contributors", "get_contributors",
            "analyze_code",
            "generate_report", "report_generate",
            "development_health", "system_health", "health_check", "health", "check_health",
            "list_tasks", "task_list", "task_summary", "get_task", "task_get", "task_overdue",
            "create_task", "task_create",
            "update_task", "task_update",
            "complete_task", "task_complete",
            "list_bugs", "bug_list", "bug_summary", "get_bug", "bug_get",
            "create_bug", "bug_create",
            "update_bug", "bug_update",
            "resolve_bug", "bug_resolve",
            "list_memory", "memory_list", "get_memory", "memory_get",
            "create_memory", "record_memory", "memory_record",
            "update_memory", "memory_update",
            "search_memory", "memory_search",
            "run_tests",
            "list_jobs", "get_jobs", "job_list", "get_job", "job_get",
            "job_start", "start_job", "run_job", "background_execute", "bg_execute",
            "job_logs", "get_job_logs", "job_log",
            "job_cancel", "cancel_job", "stop_job", "kill_job",
            "agy_instance_list", "list_agy_instances", "agy_instances", "active_agy_instances",
            "agy_instance_status", "get_agy_instance", "agy_status",
            "agy_instance_start", "start_agy_instance", "start_agy",
            "agy_instance_stop", "stop_agy_instance", "kill_agy_instance", "stop_agy",
            "agy_instance_output", "agy_output", "agy_logs", "get_agy_output",
            "agy_task_submit", "submit_agy_task", "run_agy_task",
            "agy_task_status", "get_agy_task_status", "agy_task_result",
            "list_models", "agy_models_list",
            "model_switch", "agy_model_switch",
            "usage_summary", "agy_usage_summary",
            "agy_execute", "agy_execute_query", "execute_agy",
            "approval_list", "list_approvals", "approval_get", "get_approval",
            "approval_decide", "decide_approval",
            "audit_logs_get", "get_audit_logs",
            "session_get_or_create", "get_or_create_session",
            "session_add_turn", "add_turn",
            "session_close", "close_session", "stop_chat",
            "session_check_dedup", "check_dedup",
            "session_get", "get_session", "session_list", "list_sessions",
            "execution_progress", "get_execution_progress", "ledger_progress", "ledger_get",
            "skill_search", "search_skills", "skill_select", "select_skills",
            "skill_inspect", "inspect_skill", "skill_activate", "activate_skill"
        ):
            return RiskLevel.LOW, False, "Autonomous read, monitoring, or non-destructive operation."

        # Normal development edits inside validated project
        if act in ("edit_file", "create_file"):
            return RiskLevel.LOW, False, "Standard development file edit within registered project boundary."

        # Default fallback: medium risk, require approval if unspecified
        return RiskLevel.MEDIUM, False, "Standard operation."

    @classmethod
    def enforce_permission(
        cls,
        action: str,
        params: dict = None,
        approval_id: Optional[str] = None,
        project_id: Optional[str] = None
    ) -> None:
        """Check if action is permitted autonomously; if not, require valid approval."""
        risk, requires_approval, reason = cls.classify_action(action, params)

        if not requires_approval:
            # Autonomous execution granted
            return

        # Requires approval: check if a valid approval was provided
        if not approval_id:
            affected_paths = params.get("affected_paths", []) if params else []
            appr = create_approval_request(
                action=action,
                risk_classification=risk,
                reason=reason,
                project_id=project_id,
                affected_paths=affected_paths
            )
            raise ApprovalRequiredException(
                approval_id=appr["id"],
                action=action,
                risk=risk,
                reason=reason
            )

        # Verify and consume the supplied approval
        if not verify_and_consume_approval(approval_id, expected_action=action):
            raise PermissionError(
                f"Approval '{approval_id}' is invalid, expired, already consumed, or does not match action '{action}'."
            )
