"""Aegis Intelligence - Execution Manager & Job Tracker

Tracks running and completed development jobs in SQLite, coordinates background threads,
and persists execution outputs and token usage metrics.
"""

import json
import uuid
import threading
from datetime import datetime, timezone
from typing import Optional
from config import Config
from storage.database import db_session, row_to_dict, rows_to_dict_list
from core.agy_executor import AgyExecutor
from security.audit_log import log_audit

class ExecutionManager:
    """Coordinates execution jobs with persistent state tracking."""

    @classmethod
    def create_job_record(
        cls,
        project_id: Optional[str],
        action: str,
        prompt: str,
        model: Optional[str] = None
    ) -> str:
        """Create a new job entry in SQLite."""
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO execution_jobs (
                    id, project_id, action, prompt, model, status,
                    exit_code, duration_seconds, stdout, stderr,
                    result_json, token_usage, created_at
                ) VALUES (?, ?, ?, ?, ?, 'queued', NULL, NULL, '', '', '{}', '{}', ?)
                """,
                (job_id, project_id, action, prompt, model or Config.AGY_DEFAULT_MODEL, now_iso)
            )

        return job_id

    @classmethod
    def get_job(cls, job_id: str) -> Optional[dict]:
        """Retrieve job record by ID."""
        with db_session() as conn:
            row = conn.execute("SELECT * FROM execution_jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return None
            data = row_to_dict(row)
            try:
                data["result_json"] = json.loads(data.get("result_json", "{}"))
                data["token_usage"] = json.loads(data.get("token_usage", "{}"))
            except Exception:
                pass
            return data

    @classmethod
    def list_jobs(cls, project_id: Optional[str] = None, limit: int = 25) -> list[dict]:
        """List recent execution jobs."""
        sql = "SELECT * FROM execution_jobs WHERE 1=1"
        params = []
        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        with db_session() as conn:
            rows = conn.execute(sql, params).fetchall()
            results = []
            for r in rows_to_dict_list(rows):
                try:
                    r["result_json"] = json.loads(r.get("result_json", "{}"))
                    r["token_usage"] = json.loads(r.get("token_usage", "{}"))
                except Exception:
                    pass
                results.append(r)
            return results

    @classmethod
    def execute_job(
        cls,
        project_path: str,
        prompt: str,
        project_id: Optional[str] = None,
        action: str = "execute",
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        mode: Optional[str] = None,
        async_run: bool = False
    ) -> dict:
        """Execute a development task synchronously or asynchronously."""
        chosen_model = model or Config.AGY_DEFAULT_MODEL
        job_id = cls.create_job_record(
            project_id=project_id,
            action=action,
            prompt=prompt,
            model=chosen_model
        )

        def _worker():
            # Mark running
            with db_session() as conn:
                conn.execute("UPDATE execution_jobs SET status = 'running' WHERE id = ?", (job_id,))

            result = AgyExecutor.execute(
                prompt=prompt,
                project_path=project_path,
                model=chosen_model,
                timeout=timeout,
                mode=mode
            )

            now_iso = datetime.now(timezone.utc).isoformat()
            final_status = "completed" if result.exit_code == 0 else ("timed_out" if result.timed_out else "failed")

            with db_session() as conn:
                conn.execute(
                    """
                    UPDATE execution_jobs
                    SET status = ?, exit_code = ?, duration_seconds = ?,
                        stdout = ?, stderr = ?, result_json = ?, token_usage = ?,
                        completed_at = ?
                    WHERE id = ?
                    """,
                    (
                        final_status,
                        result.exit_code,
                        result.duration_seconds,
                        result.response,
                        result.raw_stderr,
                        json.dumps(result.to_dict()),
                        json.dumps(result.usage),
                        now_iso,
                        job_id
                    )
                )

            log_audit(
                action="JOB_COMPLETED",
                actor="system",
                resource_type="job",
                resource_id=job_id,
                details={"status": final_status, "duration": result.duration_seconds, "tokens": result.usage}
            )

        if async_run:
            thread = threading.Thread(target=_worker, daemon=True)
            thread.start()
            return {
                "job_id": job_id,
                "status": "queued",
                "async": True,
                "message": f"Job {job_id} scheduled for background execution."
            }
        else:
            _worker()
            return cls.get_job(job_id)
