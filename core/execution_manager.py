"""Aegis Intelligence - Execution Manager & Asynchronous Job Tracker

Provides persistent SQLite-backed process lifecycle management, continuous file-based
stdout/stderr logging, operation-specific timeouts, background monitoring, process group
isolation, process recovery on restart, and independent Telegram completion notifications.
"""

import os
import sys
import json
import uuid
import time
import shlex
import signal
import logging
import threading
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union, List, Dict, Any

from config import Config
from storage.database import db_session, row_to_dict, rows_to_dict_list
from core.agy_executor import AgyExecutor
from intelligence.project_analyzer import ProjectAnalyzer
from security.path_validator import validate_path_within_project, canonicalize_path, PathValidationError
from security.audit_log import log_audit
from integrations.terminal import STRIPPED_ENV_VARS
from integrations.telegram_typing import send_telegram_message

logger = logging.getLogger("aegis.execution_manager")

# Potentially catastrophic root-level commands disallowed outright from autonomous execution
FORBIDDEN_COMMAND_PATTERNS = (
    "rm -rf /",
    "rm -rf /*",
    "mkfs",
    "dd if=",
    ":(){ :|:& };:",
    "> /dev/sda",
    "> /dev/nvme",
)


def is_process_running(pid: Optional[int]) -> bool:
    """Check whether a process with given PID is currently active."""
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class ExecutionManager:
    """Coordinates asynchronous long-running development jobs with persistent state tracking."""

    # In-memory mapping of active Popen instances and PGIDs for signal dispatching
    _active_processes: Dict[str, subprocess.Popen] = {}
    _active_pgids: Dict[str, int] = {}
    _monitor_threads: Dict[str, threading.Thread] = {}
    _lock = threading.Lock()

    @classmethod
    def create_job_record(
        cls,
        project_id: Optional[str],
        action: str,
        prompt: str,
        model: Optional[str] = None,
        command: str = "",
        working_directory: str = "",
        timeout_seconds: int = 1800,
        telegram_chat_id: Optional[str] = None,
        log_file: str = ""
    ) -> str:
        """Create a new job entry in SQLite."""
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO execution_jobs (
                    id, project_id, action, prompt, model, status,
                    command, working_directory, timeout_seconds, telegram_chat_id,
                    log_file, exit_code, duration_seconds, stdout, stderr,
                    result_json, token_usage, created_at, error_message
                ) VALUES (?, ?, ?, ?, ?, 'queued', ?, ?, ?, ?, ?, NULL, NULL, '', '', '{}', '{}', ?, '')
                """,
                (
                    job_id,
                    project_id,
                    action,
                    prompt,
                    model or Config.AGY_DEFAULT_MODEL,
                    command,
                    working_directory,
                    timeout_seconds,
                    str(telegram_chat_id) if telegram_chat_id else None,
                    log_file,
                    now_iso
                )
            )

        return job_id

    @classmethod
    def start_job(
        cls,
        command: Union[str, List[str]],
        project_id: Optional[str] = None,
        cwd: Optional[str] = None,
        timeout: Optional[int] = None,
        action: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Start a command as a detached background process and return immediately.
        
        Guarantees:
        - Path boundary validation (must reside within registered project directory).
        - Shell injection protection (pre-tokenized command array executed with shell=False).
        - Operation-specific timeout configuration.
        - Continuous stdout/stderr file logging to data/jobs/{job_id}.log.
        - Process group isolation (start_new_session=True) allowing reliable group cleanup.
        - Asynchronous Telegram completion notification if telegram_chat_id is provided.
        """
        # 1. Parse and sanitize command
        if isinstance(command, (list, tuple)):
            cmd_args = [str(a) for a in command if str(a).strip()]
            command_str = " ".join(cmd_args)
        elif isinstance(command, str) and command.strip():
            command_str = command.strip()
            try:
                cmd_args = shlex.split(command_str)
            except ValueError as ve:
                raise ValueError(f"Invalid command syntax: {ve}")
        else:
            raise ValueError("Command must be a non-empty string or list of argument strings.")

        if not cmd_args:
            raise ValueError("Parsed command arguments list cannot be empty.")

        # Check for catastrophic root patterns
        for bad_pattern in FORBIDDEN_COMMAND_PATTERNS:
            if bad_pattern in command_str:
                raise PermissionError(f"Command contains prohibited destructive pattern: '{bad_pattern}'")

        # 2. Resolve project and working directory
        proj = None
        if project_id:
            proj = ProjectAnalyzer.get_project(project_id)
            if not proj:
                raise ValueError(f"Project '{project_id}' not found.")
        else:
            proj = ProjectAnalyzer.get_active_project()

        if not proj:
            raise ValueError("No project specified and no active project is registered.")

        resolved_pid = proj["id"]
        project_root = proj["path"]

        # Validate working directory within project boundary
        if cwd:
            canonical_cwd = validate_path_within_project(project_root, cwd)
        else:
            canonical_cwd = canonicalize_path(project_root)

        if not os.path.isdir(canonical_cwd):
            raise PathValidationError(f"Working directory '{canonical_cwd}' is not an accessible directory.")

        # 3. Determine operation-specific timeout
        resolved_action = action or cls._detect_action_type(command_str)
        if timeout is not None and int(timeout) > 0:
            timeout_seconds = int(timeout)
        else:
            timeout_seconds = cls._resolve_default_timeout(resolved_action, command_str)

        # 4. Concurrency & Deduplication check
        with db_session() as conn:
            existing = conn.execute(
                """
                SELECT id, pid, command, status FROM execution_jobs
                WHERE project_id = ? AND command = ? AND status = 'running'
                LIMIT 1
                """,
                (resolved_pid, command_str)
            ).fetchone()
            if existing:
                existing_dict = row_to_dict(existing)
                # Check if it is genuinely still running
                if is_process_running(existing_dict.get("pid")):
                    logger.info(f"Duplicate job skipped: identical job '{existing_dict['id']}' is already running.")
                    return {
                        "job_id": existing_dict["id"],
                        "status": "running",
                        "already_running": True,
                        "command": command_str,
                        "project_id": resolved_pid,
                        "working_directory": canonical_cwd,
                        "message": f"Identical command is already executing under job '{existing_dict['id']}'."
                    }

        # 5. Prepare job log file
        Config.ensure_directories()
        job_id = f"job_{uuid.uuid4().hex[:12]}"
        log_file_path = Config.JOBS_DIR / f"{job_id}.log"
        now_iso = datetime.now(timezone.utc).isoformat()

        # 6. Sanitize environment
        clean_env = {k: v for k, v in os.environ.items() if k not in STRIPPED_ENV_VARS}
        # Provide PATH and standard TERM for npm/build scripts
        if "PATH" not in clean_env:
            clean_env["PATH"] = os.environ.get("PATH", "/data/data/com.termux/files/usr/bin:/bin:/usr/bin")
        clean_env["TERM"] = "dumb"  # Suppress complex curses spinners in non-interactive logs

        # 7. Create database record
        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO execution_jobs (
                    id, project_id, action, prompt, model, status,
                    command, working_directory, timeout_seconds, telegram_chat_id,
                    log_file, exit_code, duration_seconds, stdout, stderr,
                    result_json, token_usage, created_at, started_at, error_message
                ) VALUES (?, ?, ?, ?, ?, 'running', ?, ?, ?, ?, ?, NULL, NULL, '', '', '{}', '{}', ?, ?, '')
                """,
                (
                    job_id,
                    resolved_pid,
                    resolved_action,
                    command_str,
                    "",
                    command_str,
                    canonical_cwd,
                    timeout_seconds,
                    str(telegram_chat_id) if telegram_chat_id else None,
                    str(log_file_path),
                    now_iso,
                    now_iso
                )
            )

        # 8. Spawn process with process group isolation
        log_f = open(log_file_path, "a", encoding="utf-8")
        try:
            proc = subprocess.Popen(
                cmd_args,
                cwd=canonical_cwd,
                stdout=log_f,
                stderr=subprocess.STDOUT,  # Combine stderr into stdout log stream
                env=clean_env,
                start_new_session=True      # Detaches process into its own session & PGID
            )
        except Exception as e:
            log_f.close()
            with db_session() as conn:
                conn.execute(
                    "UPDATE execution_jobs SET status = 'failed', error_message = ?, completed_at = ? WHERE id = ?",
                    (str(e), datetime.now(timezone.utc).isoformat(), job_id)
                )
            raise RuntimeError(f"Failed to spawn background command '{command_str}': {e}")

        # Update process PID and PGID
        pid = proc.pid
        try:
            pgid = os.getpgid(pid)
        except Exception:
            pgid = pid

        with db_session() as conn:
            conn.execute(
                "UPDATE execution_jobs SET pid = ?, pgid = ? WHERE id = ?",
                (pid, pgid, job_id)
            )

        with cls._lock:
            cls._active_processes[job_id] = proc
            cls._active_pgids[job_id] = pgid

        # 9. Start background monitor thread
        monitor_t = threading.Thread(
            target=cls._monitor_job,
            args=(job_id, proc, pgid, timeout_seconds, log_file_path, log_f, telegram_chat_id, proj.get("name")),
            name=f"aegis-job-monitor-{job_id}",
            daemon=True
        )
        with cls._lock:
            cls._monitor_threads[job_id] = monitor_t
        monitor_t.start()

        log_audit(
            action="JOB_STARTED",
            actor=f"tg_{telegram_chat_id}" if telegram_chat_id else "system",
            resource_type="job",
            resource_id=job_id,
            details={"command": command_str, "project_id": resolved_pid, "pid": pid, "timeout": timeout_seconds}
        )

        return {
            "job_id": job_id,
            "status": "running",
            "command": command_str,
            "project_id": resolved_pid,
            "working_directory": canonical_cwd,
            "started_at": now_iso,
            "timeout_seconds": timeout_seconds,
            "log_file": str(log_file_path),
            "message": f"Command started in background as job '{job_id}' (PID: {pid})."
        }

    @classmethod
    def _monitor_job(
        cls,
        job_id: str,
        proc: subprocess.Popen,
        pgid: int,
        timeout_seconds: int,
        log_file_path: Path,
        log_f: Any,
        telegram_chat_id: Optional[str],
        project_name: Optional[str]
    ) -> None:
        """Background thread monitoring process execution, enforcing timeout, and recording final state."""
        start_time = time.time()
        timed_out = False
        exit_code = None

        try:
            while True:
                ret = proc.poll()
                if ret is not None:
                    exit_code = ret
                    break

                elapsed = time.time() - start_time
                if elapsed >= timeout_seconds:
                    logger.warning(f"Job {job_id} exceeded timeout of {timeout_seconds}s. Terminating process group {pgid}.")
                    timed_out = True
                    try:
                        os.killpg(pgid, signal.SIGTERM)
                    except Exception:
                        pass
                    # Wait up to 3 seconds for graceful exit
                    for _ in range(6):
                        if proc.poll() is not None:
                            break
                        time.sleep(0.5)
                    if proc.poll() is None:
                        try:
                            os.killpg(pgid, signal.SIGKILL)
                        except Exception:
                            pass
                    exit_code = proc.poll() if proc.poll() is not None else -9
                    break

                time.sleep(0.5)
        finally:
            try:
                log_f.flush()
                log_f.close()
            except Exception:
                pass

        duration = round(time.time() - start_time, 2)
        now_iso = datetime.now(timezone.utc).isoformat()

        # Read log summary from disk (tail of output)
        tail_output = cls._read_log_tail(log_file_path, max_bytes=16384)

        if timed_out:
            final_status = "timed_out"
            error_msg = f"Job timed out after exceeding execution limit of {timeout_seconds}s."
        elif exit_code == 0:
            final_status = "completed"
            error_msg = ""
        else:
            final_status = "failed"
            error_msg = f"Process exited with non-zero return code {exit_code}."

        with db_session() as conn:
            conn.execute(
                """
                UPDATE execution_jobs
                SET status = ?, exit_code = ?, duration_seconds = ?, stdout = ?,
                    completed_at = ?, error_message = ?
                WHERE id = ?
                """,
                (final_status, exit_code, duration, tail_output, now_iso, error_msg, job_id)
            )

        with cls._lock:
            cls._active_processes.pop(job_id, None)
            cls._active_pgids.pop(job_id, None)
            cls._monitor_threads.pop(job_id, None)

        log_audit(
            action="JOB_COMPLETED",
            actor="system",
            resource_type="job",
            resource_id=job_id,
            details={"status": final_status, "duration": duration, "exit_code": exit_code}
        )

        # 10. Asynchronous Telegram Completion Notification
        if telegram_chat_id:
            cls._send_telegram_notification(
                telegram_chat_id=telegram_chat_id,
                job_id=job_id,
                status=final_status,
                project_name=project_name or "Project",
                duration=duration,
                exit_code=exit_code,
                tail_output=tail_output,
                error_msg=error_msg
            )

    @classmethod
    def get_job(cls, job_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full standardized job record by ID with live state reconciliation."""
        with db_session() as conn:
            row = conn.execute("SELECT * FROM execution_jobs WHERE id = ?", (job_id,)).fetchone()
            if not row:
                return None
            data = row_to_dict(row)

        # Reconcile if marked running but process died externally without an active monitor
        if data["status"] == "running":
            with cls._lock:
                has_active_monitor = job_id in cls._active_processes or job_id in cls._monitor_threads
            if not has_active_monitor:
                # Re-check database in case monitor thread just finalized and committed final state
                with db_session() as conn:
                    fresh_row = conn.execute("SELECT * FROM execution_jobs WHERE id = ?", (job_id,)).fetchone()
                    if fresh_row:
                        fresh_data = row_to_dict(fresh_row)
                        if fresh_data["status"] != "running":
                            return cls._format_job_record(fresh_data)

                pid = data.get("pid")
                if not is_process_running(pid):
                    # Process died without monitor finalizing (e.g. killed during daemon downtime)
                    now_iso = datetime.now(timezone.utc).isoformat()
                    log_tail = cls._read_log_tail(Path(data.get("log_file", "")))
                    final_status = "failed"
                    err = "Process terminated externally (killed by OS or server restart)."
                    with db_session() as conn:
                        conn.execute(
                            "UPDATE execution_jobs SET status = ?, error_message = ?, stdout = ?, completed_at = ? WHERE id = ?",
                            (final_status, err, log_tail, now_iso, job_id)
                        )
                    data["status"] = final_status
                    data["error_message"] = err
                    data["stdout"] = log_tail
                    data["completed_at"] = now_iso

        return cls._format_job_record(data)

    @classmethod
    def list_jobs(
        cls,
        project_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 25
    ) -> List[Dict[str, Any]]:
        """List execution jobs with optional filtering."""
        sql = "SELECT * FROM execution_jobs WHERE 1=1"
        params: List[Any] = []

        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)
        if status:
            sql += " AND status = ?"
            params.append(status)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))

        with db_session() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [cls._format_job_record(row_to_dict(r)) for r in rows]

    @classmethod
    def get_job_logs(cls, job_id: str, lines: int = 50, tail: bool = True) -> Dict[str, Any]:
        """Extract lines of logs from disk for a given job."""
        job = cls.get_job(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        log_path_str = job.get("log_file")
        log_text = ""

        if log_path_str and os.path.exists(log_path_str):
            try:
                with open(log_path_str, "r", encoding="utf-8", errors="replace") as f:
                    all_lines = f.readlines()
                    if tail:
                        selected = all_lines[-lines:] if len(all_lines) > lines else all_lines
                    else:
                        selected = all_lines[:lines]
                    log_text = "".join(selected)
            except Exception as e:
                log_text = f"Error reading log file: {e}"
        else:
            # Fall back to stdout in DB record
            log_text = job.get("stdout") or "No logs recorded."

        return {
            "job_id": job_id,
            "status": job.get("status"),
            "lines_requested": lines,
            "tail": tail,
            "logs": log_text
        }

    @classmethod
    def cancel_job(cls, job_id: str) -> Dict[str, Any]:
        """Cancel a running or queued job by terminating its process group."""
        job = cls.get_job(job_id)
        if not job:
            raise ValueError(f"Job '{job_id}' not found.")

        current_status = job.get("status")
        if current_status not in ("queued", "running"):
            return {
                "job_id": job_id,
                "status": current_status,
                "success": False,
                "message": f"Job is already in terminal state '{current_status}'."
            }

        pid = job.get("pid")
        pgid = job.get("pgid")
        now_iso = datetime.now(timezone.utc).isoformat()

        # Terminate process group if alive
        if pid and is_process_running(pid):
            try:
                target_pgid = pgid or os.getpgid(pid)
                os.killpg(target_pgid, signal.SIGTERM)
                time.sleep(0.3)
                if is_process_running(pid):
                    os.killpg(target_pgid, signal.SIGKILL)
            except Exception as e:
                logger.debug(f"Process termination signal exception: {e}")

        # Update database
        with db_session() as conn:
            conn.execute(
                """
                UPDATE execution_jobs
                SET status = 'cancelled', exit_code = -15, completed_at = ?,
                    error_message = 'Job was cancelled by user request.'
                WHERE id = ?
                """,
                (now_iso, job_id)
            )

        with cls._lock:
            cls._active_processes.pop(job_id, None)
            cls._active_pgids.pop(job_id, None)
            cls._monitor_threads.pop(job_id, None)

        log_audit(
            action="JOB_CANCELLED",
            actor="system",
            resource_type="job",
            resource_id=job_id,
            details={"status": "cancelled", "reason": "user_cancelled"}
        )

        return {
            "job_id": job_id,
            "status": "cancelled",
            "success": True,
            "message": f"Job '{job_id}' was cancelled successfully."
        }

    @classmethod
    def recover_jobs(cls) -> int:
        """Scan SQLite on daemon startup and reconcile orphaned or crashed jobs."""
        recovered_count = 0
        now_iso = datetime.now(timezone.utc).isoformat()

        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM execution_jobs WHERE status IN ('queued', 'running')"
            ).fetchall()

            for r in rows:
                data = row_to_dict(r)
                jid = data["id"]
                pid = data.get("pid")

                if is_process_running(pid):
                    # Process survived daemon restart (common in detached Termux sessions)
                    # Re-attach lightweight monitor thread
                    logger.info(f"Re-attaching monitor to running process for job '{jid}' (PID: {pid})")
                    try:
                        pgid = data.get("pgid") or os.getpgid(pid)
                    except Exception:
                        pgid = pid

                    log_file = Path(data.get("log_file", ""))
                    timeout = int(data.get("timeout_seconds") or 1800)
                    chat_id = data.get("telegram_chat_id")

                    def _recovered_worker():
                        while is_process_running(pid):
                            time.sleep(1.0)
                        # Process ended
                        tail = cls._read_log_tail(log_file)
                        with db_session() as c:
                            c.execute(
                                """
                                UPDATE execution_jobs
                                SET status = 'completed', completed_at = ?, stdout = ?
                                WHERE id = ?
                                """,
                                (datetime.now(timezone.utc).isoformat(), tail, jid)
                            )
                        if chat_id:
                            cls._send_telegram_notification(
                                telegram_chat_id=chat_id,
                                job_id=jid,
                                status="completed",
                                project_name="Project",
                                duration=0.0,
                                exit_code=0,
                                tail_output=tail,
                                error_msg=""
                            )

                    t = threading.Thread(target=_recovered_worker, name=f"aegis-recovered-{jid}", daemon=True)
                    t.start()
                    recovered_count += 1
                else:
                    # Process died during server downtime
                    tail = cls._read_log_tail(Path(data.get("log_file", "")))
                    conn.execute(
                        """
                        UPDATE execution_jobs
                        SET status = 'failed', completed_at = ?, stdout = ?,
                            error_message = 'Process terminated during server restart.'
                        WHERE id = ?
                        """,
                        (now_iso, tail, jid)
                    )
                    recovered_count += 1

        if recovered_count > 0:
            logger.info(f"Job recovery reconciled {recovered_count} active/orphaned execution job(s).")
        return recovered_count

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
    ) -> Dict[str, Any]:
        """Backward-compatible wrapper for Antigravity AI CLI execution."""
        chosen_model = model or Config.AGY_DEFAULT_MODEL
        timeout_seconds = timeout or Config.AGY_DEFAULT_TIMEOUT
        job_id = cls.create_job_record(
            project_id=project_id,
            action=action,
            prompt=prompt,
            model=chosen_model,
            command=f"agy -p '{prompt[:50]}...'",
            working_directory=project_path,
            timeout_seconds=timeout_seconds
        )

        def _worker():
            with db_session() as conn:
                conn.execute(
                    "UPDATE execution_jobs SET status = 'running', started_at = ? WHERE id = ?",
                    (datetime.now(timezone.utc).isoformat(), job_id)
                )

            result = AgyExecutor.execute(
                prompt=prompt,
                project_path=project_path,
                model=chosen_model,
                timeout=timeout,
                mode=mode
            )

            now_iso = datetime.now(timezone.utc).isoformat()
            final_status = "completed" if result.exit_code == 0 else ("timed_out" if result.timed_out else "failed")
            error_msg = result.raw_stderr if final_status != "completed" else ""

            with db_session() as conn:
                conn.execute(
                    """
                    UPDATE execution_jobs
                    SET status = ?, exit_code = ?, duration_seconds = ?,
                        stdout = ?, stderr = ?, result_json = ?, token_usage = ?,
                        completed_at = ?, error_message = ?
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
                        error_msg,
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
                "message": f"Antigravity job '{job_id}' scheduled for background execution."
            }
        else:
            _worker()
            return cls.get_job(job_id) or {}

    @classmethod
    def _read_log_tail(cls, log_path: Path, max_bytes: int = 16384) -> str:
        """Read the trailing bytes of a log file safely."""
        if not log_path or not os.path.exists(log_path):
            return ""
        try:
            size = os.path.getsize(log_path)
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                if size > max_bytes:
                    f.seek(size - max_bytes)
                return f.read()
        except Exception as e:
            return f"[Log read error: {e}]"

    @classmethod
    def _detect_action_type(cls, command_str: str) -> str:
        """Infer action type from command text."""
        cmd_lower = command_str.lower()
        if any(k in cmd_lower for k in ("build", "compile", "bundle", "make", "webpack", "vite build")):
            return "build"
        if any(k in cmd_lower for k in ("install", "npm i", "add", "pip install", "yarn add")):
            return "install"
        if any(k in cmd_lower for k in ("test", "pytest", "jest", "vitest", "npm test")):
            return "test"
        if "git " in cmd_lower:
            return "git"
        return "command"

    @classmethod
    def _resolve_default_timeout(cls, action_type: str, command_str: str) -> int:
        """Select sensible execution timeout based on command semantics."""
        if action_type == "build":
            return Config.JOB_TIMEOUT_BUILD
        if action_type == "install":
            return Config.JOB_TIMEOUT_INSTALL
        if action_type == "test":
            return Config.JOB_TIMEOUT_TEST
        return Config.JOB_TIMEOUT_DEFAULT

    @classmethod
    def _send_telegram_notification(
        cls,
        telegram_chat_id: str,
        job_id: str,
        status: str,
        project_name: str,
        duration: float,
        exit_code: Optional[int],
        tail_output: str,
        error_msg: str
    ) -> None:
        """Deliver asynchronous Telegram completion notification independently of n8n."""
        status_icons = {
            "completed": "✅",
            "failed": "❌",
            "timed_out": "⏱️",
            "cancelled": "⛔"
        }
        icon = status_icons.get(status, "ℹ️")
        headline = status.replace("_", " ").upper()

        # Format output preview (last 600 characters max, HTML escaped)
        preview = (tail_output or error_msg or "No output produced.").strip()
        if len(preview) > 600:
            preview = "...\n" + preview[-600:]

        escaped_preview = (
            preview.replace("&", "&amp;")
                   .replace("<", "&lt;")
                   .replace(">", "&gt;")
        )

        msg = (
            f"{icon} <b>Background Job {headline}</b>\n\n"
            f"• <b>Job ID:</b> <code>{job_id}</code>\n"
            f"• <b>Project:</b> {project_name}\n"
            f"• <b>Duration:</b> {duration}s\n"
            f"• <b>Exit Code:</b> <code>{exit_code if exit_code is not None else 'N/A'}</code>\n\n"
            f"<b>Output Preview:</b>\n"
            f"<pre>{escaped_preview}</pre>"
        )

        try:
            send_telegram_message(telegram_chat_id, msg)
        except Exception as e:
            logger.debug(f"Failed to deliver Telegram background job notification: {e}")

    @classmethod
    def _format_job_record(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Produce standardized clean dictionary for API and agent consumers."""
        try:
            data["result_json"] = json.loads(data.get("result_json", "{}"))
        except Exception:
            pass
        try:
            data["token_usage"] = json.loads(data.get("token_usage", "{}"))
        except Exception:
            pass

        # Ensure all required user-facing fields exist
        return {
            "id": data.get("id"),
            "job_id": data.get("id"),
            "status": data.get("status", "unknown"),
            "command": data.get("command") or data.get("prompt", ""),
            "action": data.get("action", "command"),
            "project_id": data.get("project_id"),
            "working_directory": data.get("working_directory", ""),
            "started_at": data.get("started_at") or data.get("created_at"),
            "finished_at": data.get("completed_at"),
            "duration": data.get("duration_seconds"),
            "exit_code": data.get("exit_code"),
            "stdout": data.get("stdout", ""),
            "stderr": data.get("stderr", ""),
            "log_file": data.get("log_file", ""),
            "error": data.get("error_message", ""),
            "timeout_seconds": data.get("timeout_seconds"),
            "created_at": data.get("created_at"),
            "result": data.get("result_json", {}),
            "token_usage": data.get("token_usage", {})
        }
