"""Aegis Intelligence - Antigravity CLI Instance Manager & Control Plane

Provides live OS process discovery via /proc, persistent lifecycle tracking in SQLite,
continuous stdout/stderr capture, conversation ID resolution, safe process termination,
and natural language task orchestration for Antigravity instances.
"""

import os
import sys
import glob
import json
import uuid
import time
import signal
import logging
import threading
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union, List, Dict, Any

from config import Config
from storage.database import db_session, row_to_dict, rows_to_dict_list
from intelligence.project_analyzer import ProjectAnalyzer
from security.path_validator import validate_path_within_project, canonicalize_path, PathValidationError
from security.audit_log import log_audit
from integrations.terminal import STRIPPED_ENV_VARS
from integrations.telegram_typing import send_telegram_message

logger = logging.getLogger("aegis.agy_instance_manager")

# Standard Antigravity system directories in user home
AGY_HOME = Path(os.path.expanduser("~")) / ".gemini" / "antigravity-cli"
AGY_PRESENCE_DIR = AGY_HOME / "presence"
AGY_LOG_DIR = AGY_HOME / "log"
AGY_CONVERSATIONS_DIR = AGY_HOME / "conversations"


def is_pid_alive(pid: Optional[int]) -> bool:
    """Check whether a process with the given PID is currently active."""
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


class AgyInstanceManager:
    """Intelligent control plane and lifecycle manager for Antigravity instances."""

    _active_processes: Dict[str, subprocess.Popen] = {}
    _active_pgids: Dict[str, int] = {}
    _monitor_threads: Dict[str, threading.Thread] = {}
    _lock = threading.Lock()

    # ------------------------------------------------------------------
    # 1. Live OS Process & Instance Discovery
    # ------------------------------------------------------------------

    @classmethod
    def discover_instances(
        cls,
        include_historical: bool = True,
        limit: int = 15
    ) -> List[Dict[str, Any]]:
        """Discover live Antigravity instances by scanning /proc and reconcile with SQLite records."""
        live_instances: List[Dict[str, Any]] = []
        seen_pids = set()

        # 1. Load registered projects from database for directory mapping
        projects_by_path: Dict[str, Dict[str, Any]] = {}
        with db_session() as conn:
            proj_rows = conn.execute("SELECT id, name, path FROM projects").fetchall()
            for p in proj_rows:
                canon = canonicalize_path(p["path"])
                projects_by_path[canon] = {"id": p["id"], "name": p["name"], "path": canon}

        # 2. Scan /proc for running agy / agy.va39 processes
        for proc_entry in glob.glob("/proc/[0-9]*"):
            try:
                pid = int(os.path.basename(proc_entry))
                cmdline_path = f"{proc_entry}/cmdline"
                if not os.path.exists(cmdline_path):
                    continue

                with open(cmdline_path, "rb") as f:
                    cmd_raw = f.read()
                if not cmd_raw:
                    continue

                args = [a.decode("utf-8", errors="replace") for a in cmd_raw.split(b"\0") if a]
                if not args:
                    continue

                # Filter out python scripts (e.g. test runners or server.py)
                if any("python" in os.path.basename(arg).lower() for arg in args[:2]):
                    continue

                # Identify if process is an Antigravity instance
                is_agy = any("agy" in arg or "antigravity" in arg for arg in args)
                if not is_agy:
                    continue

                seen_pids.add(pid)

                # Resolve current working directory
                cwd = ""
                cwd_link = f"{proc_entry}/cwd"
                if os.path.exists(cwd_link):
                    try:
                        cwd = os.readlink(cwd_link)
                    except Exception:
                        cwd = ""

                # Map cwd to registered Aegis project
                matched_project_id = None
                matched_project_name = None
                if cwd:
                    canon_cwd = canonicalize_path(cwd)
                    for p_path, p_info in projects_by_path.items():
                        if canon_cwd == p_path or canon_cwd.startswith(f"{p_path}/"):
                            matched_project_id = p_info["id"]
                            matched_project_name = p_info["name"]
                            break

                # Resolve process start time
                started_iso = None
                try:
                    stat_ctime = os.stat(proc_entry).st_ctime
                    started_iso = datetime.fromtimestamp(stat_ctime, tz=timezone.utc).isoformat()
                except Exception:
                    started_iso = datetime.now(timezone.utc).isoformat()

                # Inspect open file descriptors for session lock, database, or log file
                conversation_id = None
                log_file = None
                is_interactive = False
                fd_dir = f"{proc_entry}/fd"
                if os.path.exists(fd_dir):
                    try:
                        for fd in os.listdir(fd_dir):
                            try:
                                target = os.readlink(f"{fd_dir}/{fd}")
                                if "presence/" in target and target.endswith(".lock"):
                                    conversation_id = os.path.basename(target).replace(".lock", "")
                                elif "log/cli-" in target and target.endswith(".log"):
                                    log_file = target
                                elif target.startswith("/dev/pts/"):
                                    is_interactive = True
                            except Exception:
                                pass
                    except Exception:
                        pass

                # Reconcile with SQLite job record if launched by Aegis
                job_id = None
                job_status = "running"
                job_prompt = ""
                with db_session() as conn:
                    job_row = conn.execute(
                        "SELECT id, prompt, command, status, log_file FROM execution_jobs WHERE pid = ? ORDER BY created_at DESC LIMIT 1",
                        (pid,)
                    ).fetchone()
                    if job_row:
                        job_id = job_row["id"]
                        job_status = job_row["status"]
                        job_prompt = job_row["prompt"]
                        if not log_file and job_row["log_file"]:
                            log_file = job_row["log_file"]

                instance_id = job_id or f"inst_live_{pid}"
                cmd_summary = " ".join(args)

                live_instances.append({
                    "instance_id": instance_id,
                    "pid": pid,
                    "status": "running",
                    "mode": "interactive" if is_interactive else "headless",
                    "project_id": matched_project_id,
                    "project_name": matched_project_name or (os.path.basename(cwd) if cwd else "unknown"),
                    "working_directory": cwd,
                    "conversation_id": conversation_id,
                    "log_file": log_file,
                    "started_at": started_iso,
                    "command": cmd_summary[:200],
                    "prompt": job_prompt[:200] if job_prompt else "",
                    "is_live_process": True
                })
            except Exception as e:
                logger.debug(f"Error inspecting proc entry {proc_entry}: {e}")
                continue

        # 3. Reconcile historical SQLite jobs
        if include_historical:
            with db_session() as conn:
                hist_rows = conn.execute(
                    """
                    SELECT j.*, p.name as project_name
                    FROM execution_jobs j
                    LEFT JOIN projects p ON j.project_id = p.id
                    WHERE j.action LIKE '%agy%' OR j.command LIKE '%agy%' OR j.action = 'execute'
                    ORDER BY j.created_at DESC
                    LIMIT ?
                    """,
                    (limit,)
                ).fetchall()

                for r in hist_rows:
                    r_dict = row_to_dict(r)
                    r_pid = r_dict.get("pid")

                    # If this job corresponds to an already added live process, update metadata
                    if r_pid and r_pid in seen_pids:
                        continue

                    # If SQLite says 'running' but the PID is dead, mark terminated/failed
                    db_status = r_dict.get("status", "completed")
                    if db_status == "running":
                        if not is_pid_alive(r_pid):
                            db_status = "terminated"
                            try:
                                conn.execute(
                                    "UPDATE execution_jobs SET status = 'terminated', completed_at = ? WHERE id = ?",
                                    (datetime.now(timezone.utc).isoformat(), r_dict["id"])
                                )
                            except Exception:
                                pass

                    live_instances.append({
                        "instance_id": r_dict["id"],
                        "pid": r_pid,
                        "status": db_status,
                        "mode": "headless",
                        "project_id": r_dict.get("project_id"),
                        "project_name": r_dict.get("project_name") or "unknown",
                        "working_directory": r_dict.get("working_directory", ""),
                        "conversation_id": r_dict.get("result_json", {}).get("conversation_id") if isinstance(r_dict.get("result_json"), dict) else None,
                        "log_file": r_dict.get("log_file"),
                        "started_at": r_dict.get("started_at") or r_dict.get("created_at"),
                        "completed_at": r_dict.get("completed_at"),
                        "duration_seconds": r_dict.get("duration_seconds"),
                        "exit_code": r_dict.get("exit_code"),
                        "command": (r_dict.get("command") or "")[:200],
                        "prompt": (r_dict.get("prompt") or "")[:200],
                        "is_live_process": False
                    })

        # Sort: live running processes first, then by started_at descending
        live_instances.sort(
            key=lambda x: (1 if x.get("is_live_process") and x.get("status") == "running" else 0, x.get("started_at") or ""),
            reverse=True
        )

        return live_instances[:limit]

    # ------------------------------------------------------------------
    # 2. Instance Status & Metadata
    # ------------------------------------------------------------------

    @classmethod
    def get_instance_status(cls, target: Union[str, int]) -> Optional[Dict[str, Any]]:
        """Retrieve detailed status for an Antigravity instance by PID, instance_id, or job_id."""
        target_str = str(target).strip()
        target_pid: Optional[int] = None
        if target_str.isdigit():
            target_pid = int(target_str)

        instances = cls.discover_instances(include_historical=True, limit=50)
        for inst in instances:
            if target_pid and inst.get("pid") == target_pid:
                return inst
            if inst.get("instance_id") == target_str:
                return inst
            if inst.get("conversation_id") == target_str:
                return inst

        # Direct database query fallback
        with db_session() as conn:
            row = conn.execute(
                """
                SELECT j.*, p.name as project_name
                FROM execution_jobs j
                LEFT JOIN projects p ON j.project_id = p.id
                WHERE j.id = ? OR j.pid = ?
                LIMIT 1
                """,
                (target_str, target_pid or -1)
            ).fetchone()
            if row:
                r_dict = row_to_dict(row)
                pid_val = r_dict.get("pid")
                is_alive = is_pid_alive(pid_val)
                st = r_dict.get("status")
                if st == "running" and not is_alive:
                    st = "terminated"
                return {
                    "instance_id": r_dict["id"],
                    "pid": pid_val,
                    "status": st,
                    "project_id": r_dict.get("project_id"),
                    "project_name": r_dict.get("project_name") or "unknown",
                    "working_directory": r_dict.get("working_directory", ""),
                    "log_file": r_dict.get("log_file"),
                    "started_at": r_dict.get("started_at") or r_dict.get("created_at"),
                    "completed_at": r_dict.get("completed_at"),
                    "duration_seconds": r_dict.get("duration_seconds"),
                    "exit_code": r_dict.get("exit_code"),
                    "command": r_dict.get("command"),
                    "prompt": r_dict.get("prompt"),
                    "is_live_process": is_alive
                }

        return None

    # ------------------------------------------------------------------
    # 3. Instance Lifecycle (Start / Stop)
    # ------------------------------------------------------------------

    @classmethod
    def start_instance(
        cls,
        project_id: Optional[str] = None,
        prompt: Optional[str] = None,
        model: Optional[str] = None,
        agent: Optional[str] = None,
        mode: Optional[str] = None,
        conversation_id: Optional[str] = None,
        timeout: Optional[int] = None,
        telegram_chat_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Launch a new Antigravity instance as a detached background process."""
        # 1. Resolve target project
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
        project_root = canonicalize_path(proj["path"])
        if not os.path.isdir(project_root):
            raise PathValidationError(f"Project path '{project_root}' does not exist on disk.")

        # 2. Build argument array strictly as list
        cmd_args = [Config.AGY_BIN_PATH]

        # Conversation continuation
        if conversation_id:
            cmd_args.extend(["--conversation", conversation_id.strip()])

        # Headless prompt mode
        active_prompt = prompt.strip() if prompt and prompt.strip() else ""
        if active_prompt:
            cmd_args.extend(["-p", active_prompt, "--output-format", "json"])
        else:
            # If no prompt, default to non-interactive help/info check or basic print
            cmd_args.extend(["-p", "status", "--output-format", "json"])

        if model:
            cmd_args.extend(["--model", model.strip()])
        elif Config.AGY_DEFAULT_MODEL:
            cmd_args.extend(["--model", Config.AGY_DEFAULT_MODEL])

        if agent:
            cmd_args.extend(["--agent", agent.strip()])

        if mode and mode in ("accept-edits", "auto", "plan"):
            cmd_args.extend(["--mode", mode])

        # Auto-approve permissions for automated operations
        cmd_args.append("--dangerously-skip-permissions")

        timeout_seconds = int(timeout) if timeout and int(timeout) > 0 else Config.AGY_DEFAULT_TIMEOUT
        command_str = " ".join(cmd_args)

        # 3. Prepare logging
        Config.ensure_directories()
        instance_id = f"job_{uuid.uuid4().hex[:12]}"
        log_file_path = Config.JOBS_DIR / f"{instance_id}.log"
        now_iso = datetime.now(timezone.utc).isoformat()

        # 4. Clean environment with critical update suppression
        clean_env = {k: v for k, v in os.environ.items() if k not in STRIPPED_ENV_VARS}
        clean_env["AGY_AUTO_UPDATE"] = "0"  # Strictly suppress interactive update prompts
        if "PATH" not in clean_env:
            clean_env["PATH"] = os.environ.get("PATH", "/data/data/com.termux/files/usr/bin:/bin:/usr/bin")
        clean_env["TERM"] = "dumb"

        # 5. Persist record in execution_jobs table
        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO execution_jobs (
                    id, project_id, action, prompt, model, status,
                    command, working_directory, timeout_seconds, telegram_chat_id,
                    log_file, exit_code, duration_seconds, stdout, stderr,
                    result_json, token_usage, created_at, started_at, error_message
                ) VALUES (?, ?, 'agy_instance', ?, ?, 'running', ?, ?, ?, ?, ?, NULL, NULL, '', '', '{}', '{}', ?, ?, '')
                """,
                (
                    instance_id,
                    resolved_pid,
                    active_prompt or "Antigravity background instance",
                    model or Config.AGY_DEFAULT_MODEL,
                    command_str,
                    project_root,
                    timeout_seconds,
                    str(telegram_chat_id) if telegram_chat_id else None,
                    str(log_file_path),
                    now_iso,
                    now_iso
                )
            )

        # 6. Spawn process with detached session
        log_f = open(log_file_path, "a", encoding="utf-8")
        try:
            proc = subprocess.Popen(
                cmd_args,
                cwd=project_root,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                env=clean_env,
                start_new_session=True  # Process group isolation
            )
        except Exception as e:
            log_f.close()
            with db_session() as conn:
                conn.execute(
                    "UPDATE execution_jobs SET status = 'failed', error_message = ?, completed_at = ? WHERE id = ?",
                    (str(e), datetime.now(timezone.utc).isoformat(), instance_id)
                )
            raise RuntimeError(f"Failed to launch Antigravity instance: {e}")

        pid = proc.pid
        try:
            pgid = os.getpgid(pid)
        except Exception:
            pgid = pid

        with db_session() as conn:
            conn.execute(
                "UPDATE execution_jobs SET pid = ?, pgid = ? WHERE id = ?",
                (pid, pgid, instance_id)
            )

        with cls._lock:
            cls._active_processes[instance_id] = proc
            cls._active_pgids[instance_id] = pgid

        # 7. Start background monitor thread
        monitor_t = threading.Thread(
            target=cls._monitor_instance,
            args=(instance_id, proc, pgid, timeout_seconds, log_file_path, log_f, telegram_chat_id, proj.get("name")),
            name=f"aegis-agy-monitor-{instance_id}",
            daemon=True
        )
        with cls._lock:
            cls._monitor_threads[instance_id] = monitor_t
        monitor_t.start()

        log_audit(
            action="AGY_INSTANCE_STARTED",
            actor=f"tg_{telegram_chat_id}" if telegram_chat_id else "system",
            resource_type="agy_instance",
            resource_id=instance_id,
            details={"project_id": resolved_pid, "pid": pid, "command": command_str}
        )

        return {
            "instance_id": instance_id,
            "pid": pid,
            "status": "running",
            "project_id": resolved_pid,
            "project_name": proj.get("name"),
            "working_directory": project_root,
            "timeout_seconds": timeout_seconds,
            "log_file": str(log_file_path),
            "message": f"Antigravity instance started in background (PID: {pid}, ID: {instance_id})."
        }

    @classmethod
    def _monitor_instance(
        cls,
        instance_id: str,
        proc: subprocess.Popen,
        pgid: int,
        timeout_seconds: int,
        log_file_path: Path,
        log_f: Any,
        telegram_chat_id: Optional[str],
        project_name: Optional[str]
    ) -> None:
        """Background thread monitoring the Antigravity instance until completion or timeout."""
        start_time = time.perf_counter()
        timed_out = False
        poll_interval = 0.5

        try:
            while True:
                ret = proc.poll()
                if ret is not None:
                    break

                elapsed = time.perf_counter() - start_time
                if elapsed > timeout_seconds:
                    timed_out = True
                    logger.warning(f"Antigravity instance '{instance_id}' timed out after {timeout_seconds}s. Terminating PGID {pgid}...")
                    try:
                        os.killpg(pgid, signal.SIGTERM)
                    except Exception:
                        pass
                    time.sleep(1.0)
                    if proc.poll() is None:
                        try:
                            os.killpg(pgid, signal.SIGKILL)
                        except Exception:
                            pass
                    break

                time.sleep(poll_interval)
        finally:
            try:
                log_f.flush()
                log_f.close()
            except Exception:
                pass

        duration = time.perf_counter() - start_time
        exit_code = proc.returncode if not timed_out else -1
        now_iso = datetime.now(timezone.utc).isoformat()

        # Parse log file for structured output and token metrics
        parsed_response = ""
        token_usage = {}
        conversation_id = None
        log_tail = ""

        if log_file_path.exists():
            try:
                with open(log_file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                log_tail = content[-4000:] if len(content) > 4000 else content

                # Attempt to extract JSON output
                idx = content.find("{\"conversation_id\"")
                if idx != -1:
                    json_str = content[idx:].strip()
                    # Find closing brace matching first JSON object
                    end_idx = json_str.rfind("}")
                    if end_idx != -1:
                        try:
                            data = json.loads(json_str[:end_idx + 1])
                            parsed_response = data.get("response", "")
                            token_usage = data.get("usage", {})
                            conversation_id = data.get("conversation_id")
                        except Exception:
                            pass
            except Exception as le:
                logger.debug(f"Error reading instance log file: {le}")

        if timed_out:
            final_status = "timed_out"
            err_msg = f"Instance timed out after {timeout_seconds} seconds."
        elif exit_code == 0:
            final_status = "completed"
            err_msg = ""
        else:
            final_status = "failed"
            err_msg = f"Instance exited with code {exit_code}."

        with db_session() as conn:
            conn.execute(
                """
                UPDATE execution_jobs
                SET status = ?, exit_code = ?, duration_seconds = ?,
                    completed_at = ?, stdout = ?, stderr = ?,
                    result_json = ?, token_usage = ?, error_message = ?
                WHERE id = ?
                """,
                (
                    final_status,
                    exit_code,
                    duration,
                    now_iso,
                    parsed_response or log_tail,
                    err_msg,
                    json.dumps({"response": parsed_response, "conversation_id": conversation_id}),
                    json.dumps(token_usage),
                    err_msg,
                    instance_id
                )
            )

        with cls._lock:
            cls._active_processes.pop(instance_id, None)
            cls._active_pgids.pop(instance_id, None)
            cls._monitor_threads.pop(instance_id, None)

        log_audit(
            action="AGY_INSTANCE_COMPLETED",
            actor="system",
            resource_type="agy_instance",
            resource_id=instance_id,
            details={"status": final_status, "duration": round(duration, 2), "exit_code": exit_code}
        )

        # Send Telegram notification if requested
        if telegram_chat_id:
            try:
                emoji = "✅" if final_status == "completed" else ("⏱️" if final_status == "timed_out" else "❌")
                proj_label = f" for <b>{project_name}</b>" if project_name else ""
                lines = [
                    f"{emoji} <b>Antigravity Task Completed</b>{proj_label}",
                    f"• Status: <code>{final_status.upper()}</code> (Exit: {exit_code})",
                    f"• Duration: {duration:.1f}s",
                    f"• Instance: <code>{instance_id}</code>",
                ]
                if conversation_id:
                    lines.append(f"• Conversation: <code>{conversation_id}</code>")
                if parsed_response:
                    summary = parsed_response.strip().split("\n")[0][:120]
                    lines.append(f"\n<b>Result:</b>\n{summary}...")
                send_telegram_message(telegram_chat_id, "\n".join(lines))
            except Exception as te:
                logger.error(f"Failed to send Telegram notification for instance {instance_id}: {te}")

    @classmethod
    def stop_instance(cls, target: Union[str, int]) -> Dict[str, Any]:
        """Safely terminate an active Antigravity instance process."""
        target_str = str(target).strip()
        target_pid: Optional[int] = None

        if target_str.isdigit():
            target_pid = int(target_str)

        # 1. Look up instance details or check if raw PID is alive
        instance_rec = cls.get_instance_status(target)
        pid_to_stop = (instance_rec.get("pid") if instance_rec else None) or target_pid

        if not pid_to_stop:
            raise ValueError(f"Instance '{target}' not found.")

        cmdline_path = f"/proc/{pid_to_stop}/cmdline"
        if not os.path.exists(cmdline_path):
            if instance_rec:
                return {
                    "instance_id": instance_rec.get("instance_id", target_str),
                    "pid": pid_to_stop,
                    "status": "terminated",
                    "message": f"Process PID {pid_to_stop} is already stopped."
                }
            raise ValueError(f"Instance '{target}' not found (process {pid_to_stop} not running).")

        # 2. Security validation: Verify the PID actually belongs to an agy/antigravity process
        # Never terminate unrelated system processes!
        with open(cmdline_path, "rb") as f:
            cmd_raw = f.read()
        args = [a.decode("utf-8", errors="replace") for a in cmd_raw.split(b"\0") if a]
        is_safe_to_kill = any("agy" in arg or "antigravity" in arg for arg in args)
        if not is_safe_to_kill:
            raise PermissionError(
                f"Security check failed: PID {pid_to_stop} does not belong to an Antigravity process! "
                f"Refusing to terminate non-Agy command: {' '.join(args[:3])}"
            )

        # 3. Terminate process group or PID
        try:
            pgid = os.getpgid(pid_to_stop)
            os.killpg(pgid, signal.SIGTERM)
        except Exception:
            try:
                os.kill(pid_to_stop, signal.SIGTERM)
            except Exception as e:
                logger.warning(f"SIGTERM error on PID {pid_to_stop}: {e}")

        # Wait up to 1.5 seconds for clean exit
        time.sleep(1.0)
        if is_pid_alive(pid_to_stop):
            try:
                pgid = os.getpgid(pid_to_stop)
                os.killpg(pgid, signal.SIGKILL)
            except Exception:
                try:
                    os.kill(pid_to_stop, signal.SIGKILL)
                except Exception:
                    pass

        # 4. Update database record
        job_id = instance_rec.get("instance_id")
        if job_id and job_id.startswith("job_"):
            with db_session() as conn:
                conn.execute(
                    "UPDATE execution_jobs SET status = 'cancelled', completed_at = ? WHERE id = ?",
                    (datetime.now(timezone.utc).isoformat(), job_id)
                )

        log_audit(
            action="AGY_INSTANCE_STOPPED",
            actor="system",
            resource_type="agy_instance",
            resource_id=job_id or str(pid_to_stop),
            details={"pid": pid_to_stop}
        )

        return {
            "instance_id": job_id or f"inst_live_{pid_to_stop}",
            "pid": pid_to_stop,
            "status": "terminated",
            "message": f"Antigravity instance (PID: {pid_to_stop}) terminated successfully."
        }

    # ------------------------------------------------------------------
    # 4. Instance Output & Log Inspection
    # ------------------------------------------------------------------

    @classmethod
    def get_instance_output(
        cls,
        target: Union[str, int],
        lines: int = 50,
        tail: bool = True
    ) -> Dict[str, Any]:
        """Retrieve output log lines from an Antigravity instance."""
        inst = cls.get_instance_status(target)
        if not inst:
            raise ValueError(f"Instance '{target}' not found.")

        log_file_str = inst.get("log_file")
        if not log_file_str or not os.path.exists(log_file_str):
            # Check standard job log directory fallback
            cand = Config.JOBS_DIR / f"{inst.get('instance_id')}.log"
            if cand.exists():
                log_file_str = str(cand)

        if not log_file_str or not os.path.exists(log_file_str):
            # If no log file, return stdout captured in SQLite
            job_stdout = ""
            with db_session() as conn:
                row = conn.execute(
                    "SELECT stdout, stderr FROM execution_jobs WHERE id = ?",
                    (inst.get("instance_id"),)
                ).fetchone()
                if row:
                    job_stdout = row["stdout"] or row["stderr"] or ""

            return {
                "instance_id": inst.get("instance_id"),
                "pid": inst.get("pid"),
                "status": inst.get("status"),
                "lines_requested": lines,
                "tail": tail,
                "output": job_stdout
            }

        try:
            with open(log_file_str, "r", encoding="utf-8", errors="replace") as f:
                all_lines = f.readlines()

            if tail:
                selected = all_lines[-lines:] if len(all_lines) > lines else all_lines
            else:
                selected = all_lines[:lines]

            return {
                "instance_id": inst.get("instance_id"),
                "pid": inst.get("pid"),
                "status": inst.get("status"),
                "lines_requested": lines,
                "tail": tail,
                "log_file": log_file_str,
                "output": "".join(selected)
            }
        except Exception as e:
            raise RuntimeError(f"Failed to read instance log file '{log_file_str}': {e}")

    # ------------------------------------------------------------------
    # 5. Task Orchestration
    # ------------------------------------------------------------------

    @classmethod
    def submit_task(
        cls,
        prompt: str,
        project_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        model: Optional[str] = None,
        agent: Optional[str] = None,
        mode: Optional[str] = None,
        timeout: Optional[int] = None,
        telegram_chat_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit an autonomous development task to Antigravity."""
        if not prompt or not prompt.strip():
            raise ValueError("Task prompt cannot be empty.")

        res = cls.start_instance(
            project_id=project_id,
            prompt=prompt.strip(),
            model=model,
            agent=agent,
            mode=mode,
            conversation_id=conversation_id,
            timeout=timeout,
            telegram_chat_id=telegram_chat_id
        )

        return {
            "task_id": res["instance_id"],
            "pid": res["pid"],
            "status": "running",
            "project_id": res["project_id"],
            "project_name": res["project_name"],
            "conversation_id": conversation_id,
            "message": f"Task submitted to Antigravity as '{res['instance_id']}' (PID: {res['pid']})."
        }

    @classmethod
    def get_task_status(cls, task_id: str) -> Dict[str, Any]:
        """Get the execution status and output of a submitted Antigravity task."""
        inst = cls.get_instance_status(task_id)
        if not inst:
            raise ValueError(f"Task '{task_id}' not found.")

        # If completed, extract response and usage from SQLite
        result_details = {}
        with db_session() as conn:
            row = conn.execute(
                "SELECT result_json, token_usage, exit_code, stdout, error_message FROM execution_jobs WHERE id = ?",
                (inst.get("instance_id"),)
            ).fetchone()
            if row:
                try:
                    result_details = json.loads(row["result_json"]) if row["result_json"] else {}
                except Exception:
                    result_details = {}
                result_details["stdout"] = row["stdout"]
                result_details["exit_code"] = row["exit_code"]
                result_details["error_message"] = row["error_message"]
                try:
                    result_details["token_usage"] = json.loads(row["token_usage"]) if row["token_usage"] else {}
                except Exception:
                    pass

        return {
            "task_id": inst.get("instance_id"),
            "pid": inst.get("pid"),
            "status": inst.get("status"),
            "project_id": inst.get("project_id"),
            "project_name": inst.get("project_name"),
            "started_at": inst.get("started_at"),
            "completed_at": inst.get("completed_at"),
            "duration_seconds": inst.get("duration_seconds"),
            "conversation_id": inst.get("conversation_id"),
            "result": result_details
        }
