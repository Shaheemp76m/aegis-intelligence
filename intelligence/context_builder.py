"""Aegis Intelligence - Context Builder Module

Assembles high-signal, compact project context payloads for the Gemini AI agent in n8n.
"""

from typing import Optional
from intelligence.project_analyzer import ProjectAnalyzer
from intelligence.task_manager import TaskManager
from intelligence.bug_tracker import BugTracker
from intelligence.project_memory import ProjectMemory
from integrations.git import GitIntegration

class ContextBuilder:
    """Builds structured Markdown/JSON context representations for reasoning engines."""

    @classmethod
    def build_agent_context(cls, project_id: Optional[str] = None, max_tasks: int = 5, max_memories: int = 5) -> str:
        """Assemble a cohesive Markdown briefing designed for Gemini's reasoning prompt."""
        proj = ProjectAnalyzer.get_project(project_id) if project_id else ProjectAnalyzer.get_active_project()
        if not proj:
            return "No active project registered in Aegis Intelligence. Register a project first using /api/v1/projects."

        pid = proj["id"]
        path = proj["path"]

        # Git status
        git_info = GitIntegration.get_repo_status(path)
        branch = git_info.get("branch", "unknown")
        clean_desc = "clean" if git_info.get("is_clean") else f"{git_info.get('modified_count', 0)} modified, {git_info.get('staged_count', 0)} staged"

        # Tasks & Blockers
        active_tasks = TaskManager.list_tasks(project_id=pid, status="in_progress", limit=max_tasks)
        pending_tasks = TaskManager.list_tasks(project_id=pid, status="pending", limit=max_tasks)
        blockers = TaskManager.get_blockers(pid)

        # Bugs
        open_bugs = BugTracker.list_bugs(project_id=pid, limit=5)
        unresolved_bugs = [b for b in open_bugs if b.get("verification_status") not in ("resolved", "verified_fixed")]

        # Key architectural decisions & memories
        memories = ProjectMemory.search_memory(project_id=pid, category="architecture", limit=3)
        if len(memories) < max_memories:
            decisions = ProjectMemory.search_memory(project_id=pid, category="decision", limit=max_memories - len(memories))
            memories.extend(decisions)

        # Build Markdown
        lines = [
            f"# Aegis Project Brief: {proj['name']} ({pid})",
            f"- **Path**: `{path}`",
            f"- **Languages / Stack**: {', '.join(proj.get('languages', []))} | {', '.join(proj.get('tech_stack', []))}",
            f"- **Git Status**: Branch `{branch}` ({clean_desc})",
            ""
        ]

        # Blockers
        if blockers:
            lines.append("## 🚨 Blockers")
            for b in blockers:
                lines.append(f"- **[BLOCKER]** {b['title']} (Priority: {b['priority']})")
            lines.append("")

        # Tasks
        lines.append("## 📋 Active & Pending Tasks")
        if not active_tasks and not pending_tasks:
            lines.append("- No pending tasks.")
        else:
            for t in active_tasks:
                lines.append(f"- [IN PROGRESS] {t['title']} (Priority: {t['priority']})")
            for t in pending_tasks:
                lines.append(f"- [PENDING] {t['title']} (Priority: {t['priority']})")
        lines.append("")

        # Bugs
        if unresolved_bugs:
            lines.append("## 🐛 Known Defects")
            for bug in unresolved_bugs:
                lines.append(f"- [{bug['severity'].upper()}] {bug['title']} (Status: {bug['verification_status']})")
            lines.append("")

        # Memory / Architectural decisions
        if memories:
            lines.append("## 🧠 Architectural Principles & Memory")
            for m in memories:
                lines.append(f"- **{m['title']}** ({m['category']}): {m['content'][:200]}")
            lines.append("")

        return "\n".join(lines)
