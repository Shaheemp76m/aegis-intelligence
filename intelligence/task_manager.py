"""Aegis Intelligence - Task Management Module

Maintains persistent task records, status transitions, blocker tracking, and task summaries.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from storage.database import db_session, row_to_dict, rows_to_dict_list

VALID_STATUSES = {"backlog", "pending", "in_progress", "blocked", "completed", "cancelled"}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}

class TaskManager:
    """Persistent task tracker for registered projects."""

    @classmethod
    def create_task(
        cls,
        project_id: str,
        title: str,
        description: str = "",
        status: str = "pending",
        priority: str = "medium",
        due_date: Optional[str] = None,
        related_files: Optional[list[str]] = None,
        notes: str = ""
    ) -> dict:
        """Create and store a new task record."""
        if not title or not title.strip():
            raise ValueError("Task title is required.")

        status = status.lower().strip()
        if status not in VALID_STATUSES:
            raise ValueError(f"Invalid status '{status}'. Must be one of: {', '.join(sorted(VALID_STATUSES))}")

        priority = priority.lower().strip()
        if priority not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority '{priority}'. Must be one of: {', '.join(sorted(VALID_PRIORITIES))}")

        task_id = f"task_{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        completed_at = now_iso if status == "completed" else None
        files_json = json.dumps(related_files or [])

        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO tasks (
                    id, project_id, title, description, status, priority,
                    due_date, related_files, notes, created_at, updated_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id, project_id, title.strip(), description.strip(),
                    status, priority, due_date, files_json, notes.strip(),
                    now_iso, now_iso, completed_at
                )
            )

        return cls.get_task(task_id)

    @classmethod
    def get_task(cls, task_id: str) -> Optional[dict]:
        """Retrieve task by ID."""
        with db_session() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not row:
                return None
            data = row_to_dict(row)
            try:
                data["related_files"] = json.loads(data.get("related_files", "[]"))
            except Exception:
                data["related_files"] = []
            return data

    @classmethod
    def update_task(cls, task_id: str, **updates) -> dict:
        """Update fields of an existing task."""
        current = cls.get_task(task_id)
        if not current:
            raise ValueError(f"Task '{task_id}' not found.")

        allowed_fields = {"title", "description", "status", "priority", "due_date", "related_files", "notes"}
        set_clauses = []
        params = []

        now_iso = datetime.now(timezone.utc).isoformat()

        for field, val in updates.items():
            if field not in allowed_fields or val is None:
                continue

            if field == "status":
                val = val.lower().strip()
                if val not in VALID_STATUSES:
                    raise ValueError(f"Invalid status '{val}'.")
                if val == "completed" and current.get("status") != "completed":
                    set_clauses.append("completed_at = ?")
                    params.append(now_iso)
                elif val != "completed" and current.get("status") == "completed":
                    set_clauses.append("completed_at = NULL")

            elif field == "priority":
                val = val.lower().strip()
                if val not in VALID_PRIORITIES:
                    raise ValueError(f"Invalid priority '{val}'.")

            elif field == "related_files":
                val = json.dumps(val if isinstance(val, list) else [])

            set_clauses.append(f"{field} = ?")
            params.append(val)

        if not set_clauses:
            return current

        set_clauses.append("updated_at = ?")
        params.append(now_iso)
        params.append(task_id)

        sql = f"UPDATE tasks SET {', '.join(set_clauses)} WHERE id = ?"
        with db_session() as conn:
            conn.execute(sql, params)

        return cls.get_task(task_id)

    @classmethod
    def complete_task(cls, task_id: str, notes: str = "") -> dict:
        """Mark a task as completed."""
        updates = {"status": "completed"}
        if notes:
            current = cls.get_task(task_id)
            existing_notes = current.get("notes", "")
            updates["notes"] = f"{existing_notes}\n[Completed]: {notes}".strip()
        return cls.update_task(task_id, **updates)

    @classmethod
    def delete_task(cls, task_id: str) -> bool:
        """Delete a task record."""
        with db_session() as conn:
            cur = conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            return cur.rowcount > 0

    @classmethod
    def list_tasks(
        cls,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        limit: int = 100
    ) -> list[dict]:
        """List tasks matching optional filters."""
        sql = "SELECT * FROM tasks WHERE 1=1"
        params = []

        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)

        if status:
            sql += " AND status = ?"
            params.append(status.lower().strip())

        if priority:
            sql += " AND priority = ?"
            params.append(priority.lower().strip())

        sql += " ORDER BY CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END, created_at DESC LIMIT ?"
        params.append(limit)

        with db_session() as conn:
            rows = conn.execute(sql, params).fetchall()
            results = []
            for r in rows_to_dict_list(rows):
                try:
                    r["related_files"] = json.loads(r.get("related_files", "[]"))
                except Exception:
                    r["related_files"] = []
                results.append(r)
            return results

    @classmethod
    def get_blockers(cls, project_id: str) -> list[dict]:
        """Retrieve all currently blocked tasks for a project."""
        return cls.list_tasks(project_id=project_id, status="blocked")

    @classmethod
    def get_overdue_tasks(cls, project_id: Optional[str] = None) -> list[dict]:
        """Identify tasks with due_date in the past that are not completed or cancelled."""
        now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        sql = "SELECT * FROM tasks WHERE due_date IS NOT NULL AND due_date != '' AND due_date < ? AND status NOT IN ('completed', 'cancelled')"
        params = [now_date]

        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)

        with db_session() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [cls.get_task(r["id"]) for r in rows]

    @classmethod
    def get_summary(cls, project_id: str) -> dict:
        """Generate counts and breakdown of tasks for a project."""
        tasks = cls.list_tasks(project_id=project_id, limit=500)
        summary = {
            "total": len(tasks),
            "by_status": {s: 0 for s in VALID_STATUSES},
            "by_priority": {p: 0 for p in VALID_PRIORITIES},
            "blocked_count": 0,
            "overdue_count": 0
        }

        now_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        for t in tasks:
            s = t.get("status", "pending")
            p = t.get("priority", "medium")
            if s in summary["by_status"]:
                summary["by_status"][s] += 1
            if p in summary["by_priority"]:
                summary["by_priority"][p] += 1
            if s == "blocked":
                summary["blocked_count"] += 1
            due = t.get("due_date")
            if due and due < now_date and s not in ("completed", "cancelled"):
                summary["overdue_count"] += 1

        return summary
