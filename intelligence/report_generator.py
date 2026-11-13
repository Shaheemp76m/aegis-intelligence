"""Aegis Intelligence - Development Report Generator

Generates 8 structured, Telegram-optimized Markdown reports distinguishing
empirically verified facts from inferred conclusions and unknown information.
"""

from datetime import datetime, timezone
from typing import Optional
from intelligence.project_analyzer import ProjectAnalyzer
from intelligence.development_monitor import DevelopmentMonitor
from intelligence.task_manager import TaskManager
from intelligence.bug_tracker import BugTracker
from intelligence.project_memory import ProjectMemory
from integrations.git import GitIntegration

class ReportGenerator:
    """Produces Telegram-friendly Markdown reports."""

    @classmethod
    def generate_report(cls, report_type: str, project_id: Optional[str] = None) -> str:
        """Route report generation by type."""
        rtype = report_type.lower().strip()
        proj = ProjectAnalyzer.get_project(project_id) if project_id else ProjectAnalyzer.get_active_project()

        if rtype == "multi_project" or rtype == "overview":
            return cls.generate_multi_project_overview()

        if not proj:
            return "❌ No active project registered in Aegis Intelligence. Please register or select a project first."

        if rtype in ("status", "project_status"):
            return cls.generate_project_status_report(proj)
        elif rtype in ("daily", "daily_development"):
            return cls.generate_daily_report(proj)
        elif rtype in ("weekly", "weekly_summary"):
            return cls.generate_weekly_summary(proj)
        elif rtype in ("tasks", "pending_tasks"):
            return cls.generate_pending_task_report(proj)
        elif rtype in ("bugs", "blockers", "bug_and_blocker"):
            return cls.generate_bug_and_blocker_report(proj)
        elif rtype in ("git", "git_activity"):
            return cls.generate_git_activity_report(proj)
        elif rtype in ("health", "project_health"):
            return cls.generate_health_report(proj)
        else:
            return cls.generate_project_status_report(proj)

    @classmethod
    def generate_project_status_report(cls, proj: dict) -> str:
        """A. Project status report."""
        pid = proj["id"]
        git_info = GitIntegration.get_repo_status(proj["path"])
        task_sum = TaskManager.get_summary(pid)
        bug_sum = BugTracker.get_summary(pid)

        lines = [
            f"📊 *AEGIS STATUS REPORT: {proj['name']}*",
            f"🆔 `{pid}` | Branch: `{git_info.get('branch', 'unknown')}`",
            "",
            "🔍 *Verified Facts:*",
            f"• Git Working Tree: {'Clean ✅' if git_info.get('is_clean') else 'Dirty ⚠️'}",
            f"• Modifications: {git_info.get('modified_count', 0)} files, {git_info.get('staged_count', 0)} staged",
            f"• Tasks: {task_sum['by_status'].get('completed', 0)}/{task_sum['total']} completed ({task_sum.get('blocked_count', 0)} blocked)",
            f"• Bugs: {bug_sum['total']} logged ({bug_sum.get('unresolved_critical_high', 0)} high/critical open)",
            "",
            "💡 *Inferred Assessment:*",
            "• Project is progressing with active changes in the working tree." if not git_info.get("is_clean") else "• Working directory is stable with no outstanding uncommitted diffs.",
            "",
            "❓ *Unknowns:*",
            "• End-to-end user acceptance status remains unverified until test run."
        ]
        return "\n".join(lines)

    @classmethod
    def generate_daily_report(cls, proj: dict) -> str:
        """B. Daily development report."""
        pid = proj["id"]
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        commits = GitIntegration.get_recent_commits(proj["path"], count=5)
        completed_today = [
            t for t in TaskManager.list_tasks(project_id=pid, status="completed", limit=20)
            if t.get("completed_at", "").startswith(today)
        ]

        lines = [
            f"📅 *AEGIS DAILY REPORT ({today})*",
            f"📂 Project: *{proj['name']}*",
            "",
            "✅ *Verified Completed Today:*",
        ]
        if completed_today:
            for t in completed_today:
                lines.append(f"• `{t['id']}` {t['title']}")
        else:
            lines.append("• No tasks marked completed in Aegis today.")

        lines.append("")
        lines.append("📝 *Recent Commits:*")
        if commits:
            for c in commits[:3]:
                lines.append(f"• `{c['hash']}` {c['message']} ({c['author']})")
        else:
            lines.append("• No recent commits recorded.")

        lines.append("")
        lines.append("💡 *Next Recommended Focus:*")
        pending = TaskManager.list_tasks(project_id=pid, status="pending", limit=2)
        if pending:
            for p in pending:
                lines.append(f"• [P-{p['priority'].upper()}] {p['title']}")
        else:
            lines.append("• Review backlog or log new engineering milestones.")

        return "\n".join(lines)

    @classmethod
    def generate_weekly_summary(cls, proj: dict) -> str:
        """C. Weekly development summary."""
        pid = proj["id"]
        commits = GitIntegration.get_recent_commits(proj["path"], count=15)
        task_sum = TaskManager.get_summary(pid)
        bug_sum = BugTracker.get_summary(pid)

        lines = [
            f"📈 *AEGIS WEEKLY SUMMARY: {proj['name']}*",
            "",
            "🔍 *Verified Metrics:*",
            f"• Total Commits Examined: {len(commits)}",
            f"• Tasks Completed Total: {task_sum['by_status'].get('completed', 0)} of {task_sum['total']}",
            f"• Tasks In Progress: {task_sum['by_status'].get('in_progress', 0)}",
            f"• Bugs Resolved: {bug_sum['by_status'].get('resolved', 0) + bug_sum['by_status'].get('verified_fixed', 0)} of {bug_sum['total']}",
            "",
            "💡 *Strategic Assessment:*",
            "• Velocity is consistent with active repository commits." if commits else "• Repository activity has been dormant or untracked this period."
        ]
        return "\n".join(lines)

    @classmethod
    def generate_pending_task_report(cls, proj: dict) -> str:
        """D. Pending task report."""
        pid = proj["id"]
        in_progress = TaskManager.list_tasks(project_id=pid, status="in_progress")
        pending = TaskManager.list_tasks(project_id=pid, status="pending")
        overdue = TaskManager.get_overdue_tasks(project_id=pid)

        lines = [
            f"📋 *AEGIS TASK REPORT: {proj['name']}*",
            f"Total Active Tasks: {len(in_progress) + len(pending)}",
            ""
        ]

        if overdue:
            lines.append("⏰ *Overdue Tasks:*")
            for o in overdue:
                lines.append(f"• ⚠️ `{o['id']}` *{o['title']}* (Due: {o.get('due_date')})")
            lines.append("")

        lines.append("🏃 *In Progress:*")
        if in_progress:
            for t in in_progress:
                lines.append(f"• [{t['priority'].upper()}] `{t['id']}` {t['title']}")
        else:
            lines.append("• No tasks currently in progress.")

        lines.append("")
        lines.append("⏳ *Pending Tasks:*")
        if pending:
            for t in pending[:8]:
                lines.append(f"• [{t['priority'].upper()}] `{t['id']}` {t['title']}")
        else:
            lines.append("• No pending tasks.")

        return "\n".join(lines)

    @classmethod
    def generate_bug_and_blocker_report(cls, proj: dict) -> str:
        """E. Bug and blocker report."""
        pid = proj["id"]
        blockers = TaskManager.get_blockers(pid)
        bugs = BugTracker.list_bugs(project_id=pid)
        open_bugs = [b for b in bugs if b.get("verification_status") not in ("resolved", "verified_fixed")]

        lines = [
            f"🚨 *AEGIS BUGS & BLOCKERS: {proj['name']}*",
            ""
        ]

        lines.append("🚧 *Active Blockers:*")
        if blockers:
            for b in blockers:
                lines.append(f"• 🛑 `{b['id']}` *{b['title']}* ({b['notes'] or 'No blocker notes'})")
        else:
            lines.append("• No active blockers recorded. ✅")

        lines.append("")
        lines.append("🐛 *Open Defects & Suspicions:*")
        if open_bugs:
            for bug in open_bugs:
                ver_emoji = "⚠️" if bug["verification_status"] == "unverified" else "🔴"
                lines.append(f"• {ver_emoji} [{bug['severity'].upper()}] `{bug['id']}` *{bug['title']}* (Status: {bug['verification_status']})")
        else:
            lines.append("• No open defects recorded. ✅")

        return "\n".join(lines)

    @classmethod
    def generate_git_activity_report(cls, proj: dict) -> str:
        """F. Git activity report."""
        git_info = GitIntegration.get_repo_status(proj["path"])
        commits = GitIntegration.get_recent_commits(proj["path"], count=6)
        contributors = GitIntegration.get_contributors(proj["path"])

        lines = [
            f"🌿 *AEGIS GIT REPORT: {proj['name']}*",
            f"Branch: `{git_info.get('branch', 'unknown')}` | Origin: `{git_info.get('origin', 'none')}`",
            "",
            "📌 *Working Tree:*",
            f"• State: {'Clean ✅' if git_info.get('is_clean') else 'Modified ⚠️'}",
            f"• Ahead: {git_info.get('ahead', 0)} commit(s) | Behind: {git_info.get('behind', 0)} commit(s)",
            f"• Modified: {git_info.get('modified_count', 0)} | Staged: {git_info.get('staged_count', 0)} | Untracked: {git_info.get('untracked_count', 0)}",
            "",
            "📜 *Latest Commits:*",
        ]
        for c in commits:
            lines.append(f"• `{c['hash']}` {c['message']} - _{c['author']}_")

        if contributors:
            lines.append("")
            lines.append("👥 *Contributors:*")
            for ct in contributors[:4]:
                lines.append(f"• {ct['name']}: {ct['commits']} commit(s)")

        return "\n".join(lines)

    @classmethod
    def generate_health_report(cls, proj: dict) -> str:
        """G. Project health report."""
        health = DevelopmentMonitor.evaluate_health(proj["id"], proj["path"], execute_tests=False)

        lines = [
            f"🩺 *AEGIS HEALTH CHECK: {proj['name']}*",
            "",
            "🔍 *Verified Facts:*",
        ]
        for f in health["verified_facts"]:
            lines.append(f"• {f}")

        lines.append("")
        lines.append("💡 *Inferred Conclusions:*")
        for c in health["inferred_conclusions"]:
            lines.append(f"• {c}")

        lines.append("")
        lines.append("❓ *Unknowns:*")
        for u in health["unknown_information"]:
            lines.append(f"• {u}")

        lines.append("")
        lines.append("🎯 *Recommended Next Actions:*")
        for a in health["recommended_actions"]:
            lines.append(f"• {a}")

        return "\n".join(lines)

    @classmethod
    def generate_multi_project_overview(cls) -> str:
        """H. Multi-project overview."""
        projects = ProjectAnalyzer.list_projects()
        if not projects:
            return "📁 No projects currently registered in Aegis Intelligence."

        lines = [
            "🌐 *AEGIS MULTI-PROJECT OVERVIEW*",
            f"Registered Projects: {len(projects)}",
            ""
        ]

        for p in projects:
            active_marker = "⭐ [ACTIVE]" if p.get("is_active") else "📁"
            c = p.get("counts", {})
            lines.append(
                f"{active_marker} *{p['name']}* (`{p['id']}`)\n"
                f"  Path: `{p['path']}`\n"
                f"  Branch: `{p.get('git_branch', 'n/a')}` | Tasks: {c.get('tasks', 0)} | Bugs: {c.get('bugs', 0)} | Memory: {c.get('memory_items', 0)}\n"
            )

        return "\n".join(lines)
