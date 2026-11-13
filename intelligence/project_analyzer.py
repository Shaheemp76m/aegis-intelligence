"""Aegis Intelligence - Multi-Project Analyzer & Registry

Manages registered projects, performs deep inspection of source code and git status,
and provides multi-project comparisons without filesystem risk.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from storage.database import db_session, row_to_dict, rows_to_dict_list
from security.path_validator import is_safe_project_directory
from security.audit_log import log_audit
from integrations.git import GitIntegration
from integrations.filesystem import FilesystemIntegration

class ProjectAnalyzer:
    """Manages project lifecycle, inspection, and multi-project metadata."""

    @classmethod
    def register_project(
        cls,
        name: str,
        path: str,
        description: str = "",
        project_id: Optional[str] = None
    ) -> dict:
        """Register a new project after strict safety verification of directory path."""
        if not name or not name.strip():
            raise ValueError("Project name is required.")

        is_safe, canonical_or_err = is_safe_project_directory(path)
        if not is_safe:
            raise ValueError(f"Cannot register project: {canonical_or_err}")

        canonical_path = canonical_or_err
        pid = project_id or f"proj_{name.lower().replace(' ', '_')}_{uuid.uuid4().hex[:6]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Initial inspection of stack and git
        git_status = GitIntegration.get_repo_status(canonical_path)
        languages, stack = FilesystemIntegration.detect_tech_stack(canonical_path)

        with db_session() as conn:
            # Check for duplicate path
            existing = conn.execute("SELECT id FROM projects WHERE path = ?", (canonical_path,)).fetchone()
            if existing:
                raise ValueError(f"A project is already registered at path '{canonical_path}' (ID: {existing['id']}).")

            conn.execute(
                """
                INSERT INTO projects (
                    id, name, path, description, git_origin, git_branch,
                    languages, tech_stack, status, is_active, created_at,
                    updated_at, last_inspected_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active', 0, ?, ?, ?)
                """,
                (
                    pid, name.strip(), canonical_path, description.strip(),
                    git_status.get("origin") or "", git_status.get("branch") or "",
                    json.dumps(languages), json.dumps(stack), now_iso, now_iso, now_iso
                )
            )

        log_audit(
            action="PROJECT_REGISTERED",
            actor="system",
            resource_type="project",
            resource_id=pid,
            details={"name": name, "path": canonical_path}
        )

        return cls.get_project(pid)

    @classmethod
    def get_project(cls, project_id: str) -> Optional[dict]:
        """Retrieve project details by ID with parsed JSON structures."""
        with db_session() as conn:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            if not row:
                return None
            data = row_to_dict(row)
            try:
                data["languages"] = json.loads(data.get("languages", "[]"))
                data["tech_stack"] = json.loads(data.get("tech_stack", "[]"))
            except Exception:
                data["languages"] = []
                data["tech_stack"] = []
            return data

    @classmethod
    def get_active_project(cls) -> Optional[dict]:
        """Retrieve currently marked active project."""
        with db_session() as conn:
            row = conn.execute("SELECT * FROM projects WHERE is_active = 1 LIMIT 1").fetchone()
            if not row:
                # Return the most recently updated project if none explicitly marked
                row = conn.execute("SELECT * FROM projects ORDER BY updated_at DESC LIMIT 1").fetchone()
            if not row:
                return None
            return cls.get_project(row["id"])

    @classmethod
    def set_active_project(cls, project_id: str) -> dict:
        """Set a project as the currently active project."""
        proj = cls.get_project(project_id)
        if not proj:
            raise ValueError(f"Project '{project_id}' not found.")

        with db_session() as conn:
            conn.execute("UPDATE projects SET is_active = 0")
            conn.execute("UPDATE projects SET is_active = 1 WHERE id = ?", (project_id,))

        log_audit(
            action="PROJECT_ACTIVATED",
            actor="system",
            resource_type="project",
            resource_id=project_id,
            details={"name": proj["name"]}
        )
        return cls.get_project(project_id)

    @classmethod
    def list_projects(cls) -> list[dict]:
        """List all registered projects with aggregated stats."""
        with db_session() as conn:
            rows = conn.execute("SELECT * FROM projects ORDER BY is_active DESC, updated_at DESC").fetchall()
            projects = []
            for r in rows:
                p = cls.get_project(r["id"])
                # Add counts
                task_count = conn.execute("SELECT COUNT(*) FROM tasks WHERE project_id = ?", (p["id"],)).fetchone()[0]
                bug_count = conn.execute("SELECT COUNT(*) FROM bugs WHERE project_id = ?", (p["id"],)).fetchone()[0]
                mem_count = conn.execute("SELECT COUNT(*) FROM project_memory WHERE project_id = ?", (p["id"],)).fetchone()[0]
                p["counts"] = {
                    "tasks": task_count,
                    "bugs": bug_count,
                    "memory_items": mem_count
                }
                projects.append(p)
            return projects

    @classmethod
    def update_project(cls, project_id: str, **updates) -> dict:
        """Update project name, description, or status."""
        current = cls.get_project(project_id)
        if not current:
            raise ValueError(f"Project '{project_id}' not found.")

        allowed = {"name", "description", "status"}
        set_clauses = []
        params = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for field, val in updates.items():
            if field in allowed and val is not None:
                set_clauses.append(f"{field} = ?")
                params.append(val.strip() if isinstance(val, str) else val)

        if not set_clauses:
            return current

        set_clauses.append("updated_at = ?")
        params.append(now_iso)
        params.append(project_id)

        with db_session() as conn:
            conn.execute(f"UPDATE projects SET {', '.join(set_clauses)} WHERE id = ?", params)

        return cls.get_project(project_id)

    @classmethod
    def remove_project(cls, project_id: str) -> bool:
        """Unregister project from Aegis WITHOUT deleting project files from filesystem."""
        proj = cls.get_project(project_id)
        if not proj:
            return False

        with db_session() as conn:
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))

        log_audit(
            action="PROJECT_UNREGISTERED",
            actor="system",
            resource_type="project",
            resource_id=project_id,
            details={"name": proj["name"], "path": proj["path"]}
        )
        return True

    @classmethod
    def inspect_project(cls, project_id: str) -> dict:
        """Run deep inspection of git repository, directory tree, and technology stack."""
        proj = cls.get_project(project_id)
        if not proj:
            raise ValueError(f"Project '{project_id}' not found.")

        project_path = proj["path"]
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Git inspection
        git_status = GitIntegration.get_repo_status(project_path)
        recent_commits = GitIntegration.get_recent_commits(project_path, count=5)
        contributors = GitIntegration.get_contributors(project_path)

        # 2. Filesystem inspection
        fs_info = FilesystemIntegration.inspect_directory(project_path, max_depth=3, max_files=150)
        recent_files = FilesystemIntegration.get_recently_modified_files(project_path, limit=10)
        languages, stack = FilesystemIntegration.detect_tech_stack(project_path)

        # 3. Update project record
        with db_session() as conn:
            conn.execute(
                """
                UPDATE projects
                SET git_origin = ?, git_branch = ?, languages = ?,
                    tech_stack = ?, last_inspected_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    git_status.get("origin") or "",
                    git_status.get("branch") or "",
                    json.dumps(languages),
                    json.dumps(stack),
                    now_iso,
                    now_iso,
                    project_id
                )
            )

        log_audit(
            action="PROJECT_INSPECTED",
            actor="system",
            resource_type="project",
            resource_id=project_id,
            details={"branch": git_status.get("branch"), "files_count": fs_info.get("total_files")}
        )

        return {
            "project": cls.get_project(project_id),
            "git": {
                "status": git_status,
                "recent_commits": recent_commits,
                "contributors": contributors
            },
            "filesystem": {
                "total_files": fs_info.get("total_files"),
                "total_size": fs_info.get("total_size_human"),
                "config_files": fs_info.get("config_files"),
                "doc_files": fs_info.get("doc_files"),
                "tree_sample": fs_info.get("tree_sample"),
                "recently_modified": recent_files
            },
            "inspected_at": now_iso
        }

    @classmethod
    def compare_projects(cls, project_ids: list[str]) -> list[dict]:
        """Compare development state and metrics across multiple projects."""
        results = []
        for pid in project_ids:
            proj = cls.get_project(pid)
            if not proj:
                continue
            git_info = GitIntegration.get_repo_status(proj["path"])
            from intelligence.task_manager import TaskManager
            from intelligence.bug_tracker import BugTracker
            task_sum = TaskManager.get_summary(pid)
            bug_sum = BugTracker.get_summary(pid)
            results.append({
                "id": proj["id"],
                "name": proj["name"],
                "path": proj["path"],
                "branch": git_info.get("branch"),
                "is_clean": git_info.get("is_clean"),
                "languages": proj.get("languages", []),
                "tech_stack": proj.get("tech_stack", []),
                "task_summary": task_sum,
                "bug_summary": bug_sum,
                "last_inspected_at": proj.get("last_inspected_at")
            })
        return results
