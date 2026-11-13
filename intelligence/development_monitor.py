"""Aegis Intelligence - Development Health & Progress Monitor

Performs empirical fact gathering, health assessment, test detection,
blocker evaluation, and distinguishes verified facts from inferred conclusions.
"""

import os
from typing import Optional
from integrations.git import GitIntegration
from integrations.filesystem import FilesystemIntegration
from integrations.terminal import safe_run_command
from intelligence.task_manager import TaskManager
from intelligence.bug_tracker import BugTracker
from storage.database import db_session

class DevelopmentMonitor:
    """Monitors development activity, test status, blockers, and health."""

    @classmethod
    def detect_test_framework(cls, project_path: str) -> Optional[dict]:
        """Detect configured test runners in the project."""
        # Check npm package.json for test scripts
        pkg_path = os.path.join(project_path, "package.json")
        if os.path.isfile(pkg_path):
            try:
                import json
                with open(pkg_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    scripts = data.get("scripts", {})
                    if "test" in scripts:
                        return {
                            "runner": "npm test",
                            "command": ["npm", "test", "--", "--run"],
                            "type": "javascript"
                        }
            except Exception:
                pass

        # Check Python pytest or unittest
        if os.path.isfile(os.path.join(project_path, "pytest.ini")) or \
           os.path.isfile(os.path.join(project_path, "pyproject.toml")) or \
           os.path.isdir(os.path.join(project_path, "tests")):
            return {
                "runner": "pytest/unittest",
                "command": ["python3", "-m", "unittest", "discover", "tests"],
                "type": "python"
            }

        return None

    @classmethod
    def run_tests_if_configured(cls, project_path: str, timeout: int = 45) -> dict:
        """Run project tests safely if a non-destructive test suite is detected."""
        detector = cls.detect_test_framework(project_path)
        if not detector:
            return {
                "tested": False,
                "passed": False,
                "status": "No test runner configured",
                "details": "No test runner detected in project root."
            }

        cmd = detector["command"]
        res = safe_run_command(cmd, cwd=project_path, timeout=timeout)
        passed = (res.exit_code == 0)

        return {
            "tested": True,
            "passed": passed,
            "exit_code": res.exit_code,
            "runner": detector["runner"],
            "stdout": res.stdout[:2000] if res.stdout else "",
            "stderr": res.stderr[:2000] if res.stderr else "",
            "duration_seconds": res.duration_seconds
        }

    @classmethod
    def detect_technical_debt(cls, project_path: str) -> dict:
        """Scan source files for explicit TODO, FIXME, HACK markers."""
        todo_count = 0
        fixme_count = 0
        debt_files = []

        res = safe_run_command(
            ["grep", "-rnE", "(TODO|FIXME):", "--exclude-dir=node_modules", "--exclude-dir=.git", "--exclude-dir=dist", "."],
            cwd=project_path,
            timeout=10
        )

        if res.exit_code == 0 and res.stdout:
            lines = res.stdout.splitlines()
            for l in lines[:100]:
                if "TODO" in l:
                    todo_count += 1
                if "FIXME" in l:
                    fixme_count += 1
                parts = l.split(":", 2)
                if len(parts) >= 3 and parts[0] not in debt_files:
                    debt_files.append(parts[0])

        return {
            "todo_count": todo_count,
            "fixme_count": fixme_count,
            "affected_files_count": len(debt_files),
            "sample_files": debt_files[:10]
        }

    @classmethod
    def evaluate_health(cls, project_id: str, project_path: str, execute_tests: bool = False) -> dict:
        """Perform comprehensive health check distinguishing verified facts from inferences."""
        # 1. Facts: Git repository state
        git_status = GitIntegration.get_repo_status(project_path)
        recent_commits = GitIntegration.get_recent_commits(project_path, count=5)

        # 2. Facts: Filesystem state
        recent_modifications = FilesystemIntegration.get_recently_modified_files(project_path, limit=8)

        # 3. Facts: Database tasks and blockers
        task_summary = TaskManager.get_summary(project_id)
        blockers = TaskManager.get_blockers(project_id)
        bug_summary = BugTracker.get_summary(project_id)

        # 4. Optional: Actual test execution
        test_result = None
        if execute_tests:
            test_result = cls.run_tests_if_configured(project_path)

        # 5. Technical debt
        tech_debt = cls.detect_technical_debt(project_path)

        # Verified facts list
        verified_facts = [
            f"Git repository on branch '{git_status.get('branch', 'unknown')}' is {'clean' if git_status.get('is_clean') else 'dirty'}.",
            f"{git_status.get('modified_count', 0)} modified file(s), {git_status.get('staged_count', 0)} staged, {git_status.get('untracked_count', 0)} untracked.",
            f"{task_summary.get('total', 0)} persistent tasks tracked ({task_summary['by_status'].get('completed', 0)} completed, {task_summary.get('blocked_count', 0)} blocked).",
            f"{bug_summary.get('total', 0)} bugs recorded ({bug_summary.get('unresolved_critical_high', 0)} critical/high open)."
        ]
        if test_result and test_result.get("tested"):
            test_status_text = "PASSED" if test_result.get("passed") else "FAILED"
            verified_facts.append(f"Automated test run ({test_result.get('runner')}): {test_status_text} in {test_result.get('duration_seconds')}s.")

        # Inferred conclusions
        inferred_conclusions = []
        if git_status.get("modified_count", 0) > 10:
            inferred_conclusions.append("High number of uncommitted changes indicates an active, unfinished feature branch.")
        if task_summary.get("blocked_count", 0) > 0:
            inferred_conclusions.append(f"Development progress is currently constrained by {task_summary['blocked_count']} blocked task(s).")
        if bug_summary.get("unresolved_critical_high", 0) > 0:
            inferred_conclusions.append(f"Immediate risk detected: {bug_summary['unresolved_critical_high']} high-severity bug(s) require diagnosis.")
        if not inferred_conclusions:
            inferred_conclusions.append("Development baseline appears stable with no blocking anomalies.")

        # Unknown information
        unknown_information = []
        if not test_result or not test_result.get("tested"):
            unknown_information.append("Current test suite pass/fail status is UNVERIFIED (test run not triggered).")
        unknown_information.append("Production runtime performance and memory limits on deployment targets are UNKNOWN.")

        # Recommended next actions
        recommendations = []
        if bug_summary.get("unresolved_critical_high", 0) > 0:
            recommendations.append("Investigate and resolve open critical/high bugs before shipping new features.")
        if task_summary.get("blocked_count", 0) > 0:
            recommendations.append("Review blocked tasks to eliminate dependencies or re-assign priorities.")
        if not git_status.get("is_clean"):
            recommendations.append("Review uncommitted git modifications and commit incremental progress.")
        if not recommendations:
            recommendations.append("Proceed with next pending backlog tasks.")

        return {
            "verified_facts": verified_facts,
            "inferred_conclusions": inferred_conclusions,
            "unknown_information": unknown_information,
            "recommended_actions": recommendations,
            "git_state": git_status,
            "recent_commits": recent_commits,
            "recent_files": recent_modifications,
            "task_summary": task_summary,
            "bug_summary": bug_summary,
            "blockers": blockers,
            "technical_debt": tech_debt,
            "test_result": test_result
        }
