"""Aegis Intelligence - Execution Ledger & Agent Loop Safeguards

Provides execution tracking, parameter normalization, deterministic action signing,
duplicate action detection, cached-result short-circuiting for read-only actions,
stagnation detection, and configurable execution limits to prevent infinite loops.
"""

import json
import uuid
import time
import hashlib
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from config import Config
from storage.database import db_session, row_to_dict, rows_to_dict_list
from security.audit_log import log_audit
from api.responses import DateTimeEncoder

class ExecutionLedger:
    """Maintains an execution ledger for agent tasks and prevents repetitive tool loops."""

    # Set of canonical read-only actions that produce deterministic query output
    READ_ONLY_ACTIONS: set[str] = {
        # Projects
        "project_list",
        "project_get",
        "project_inspect",
        "project_assessment",
        "project_context",
        "project_compare",
        # Health & Reports
        "system_health",
        "development_health",
        "report_generate",
        # Tasks
        "task_list",
        "task_get",
        "task_summary",
        "task_overdue",
        # Bugs
        "bug_list",
        "bug_get",
        "bug_summary",
        # Memory
        "memory_search",
        "memory_get",
        # Git
        "git_status",
        "git_commits",
        "git_diff",
        "git_contributors",
        # Filesystem
        "file_read",
        "filesystem_inspect",
        "filesystem_recent_files",
        # Antigravity & Jobs
        "agy_models_list",
        "agy_usage_summary",
        "job_list",
        "job_get",
        # Approvals & Audits
        "approval_list",
        "approval_get",
        "audit_logs_get",
        # Sessions & Ledger
        "session_get",
        "session_list",
        "session_check_dedup",
        "execution_progress",
        "ledger_get"
    }

    # In-memory concurrency tracking for running actions: {(execution_id, action_signature)}
    _in_flight_locks: set[tuple[str, str]] = set()
    _lock = threading.Lock()

    @classmethod
    def is_read_only(cls, action: str) -> bool:
        """Determine whether an action is read-only (deterministic and non-mutating)."""
        return action.lower().strip() in cls.READ_ONLY_ACTIONS

    @classmethod
    def _normalize_val(cls, v: Any) -> Any:
        """Recursively normalize values for deterministic hashing."""
        if isinstance(v, str):
            return v.strip()
        elif isinstance(v, dict):
            return {k.strip(): cls._normalize_val(val) for k, val in sorted(v.items())}
        elif isinstance(v, (list, tuple)):
            return [cls._normalize_val(item) for item in v]
        return v

    @classmethod
    def normalize_parameters(cls, params: Optional[dict]) -> dict:
        """Produce a clean, normalized parameter dictionary ignoring execution metadata."""
        if not params or not isinstance(params, dict):
            return {}
        ignored_keys = {
            "execution_id", "session_id", "objective",
            "approval_id", "approval_token", "_request_id"
        }
        normalized = {}
        for k, v in sorted(params.items()):
            if k in ignored_keys:
                continue
            normalized[k.strip()] = cls._normalize_val(v)
        return normalized

    @classmethod
    def compute_action_signature(
        cls,
        action: str,
        normalized_params: dict,
        context_id: Optional[str] = None
    ) -> str:
        """Generate a deterministic 32-character SHA256 signature for an action invocation."""
        canon_json = json.dumps(normalized_params, sort_keys=True, separators=(",", ":"))
        raw = f"{action.lower().strip()}:{canon_json}:{context_id or ''}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    @classmethod
    def record_action_start(
        cls,
        execution_id: str,
        action: str,
        params: Optional[dict] = None,
        session_id: Optional[str] = None,
        objective: Optional[str] = None,
        max_total_actions: Optional[int] = None,
        max_repeated_actions: Optional[int] = None,
        max_consecutive_failures: Optional[int] = None,
        timeout_seconds: Optional[int] = None
    ) -> tuple[bool, Optional[Any], str]:
        """Evaluate action against limits, concurrency, and deduplication rules.

        Returns:
            (is_allowed, response_payload, reason_code)
            - If is_allowed is True: caller executes the action.
            - If is_allowed is False: caller returns response_payload directly.
        """
        limit_total = max_total_actions or Config.LEDGER_MAX_TOTAL_ACTIONS
        limit_repeated = max_repeated_actions or Config.LEDGER_MAX_REPEATED_ACTIONS
        limit_failures = max_consecutive_failures or Config.LEDGER_MAX_CONSECUTIVE_FAILURES
        limit_timeout = timeout_seconds or Config.LEDGER_EXECUTION_TIMEOUT

        norm_params = cls.normalize_parameters(params)
        action_clean = action.lower().strip()
        signature = cls.compute_action_signature(action_clean, norm_params)
        read_only = cls.is_read_only(action_clean)
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        # 1. Concurrency Check: prevent identical concurrent executions in the same execution
        with cls._lock:
            if (execution_id, signature) in cls._in_flight_locks:
                return (
                    False,
                    {
                        "status": "BLOCKED",
                        "reason": "CONCURRENT_DUPLICATE",
                        "action": action_clean,
                        "execution_id": execution_id,
                        "message": f"Action '{action_clean}' with identical parameters is already executing concurrently in execution '{execution_id}'."
                    },
                    "CONCURRENT_DUPLICATE"
                )

        with db_session() as conn:
            # 2. Execution Timeout Check
            row_first = conn.execute(
                "SELECT created_at FROM execution_ledger WHERE execution_id = ? ORDER BY created_at ASC LIMIT 1",
                (execution_id,)
            ).fetchone()
            if row_first:
                first_dt = datetime.fromisoformat(row_first["created_at"])
                elapsed = (now - first_dt).total_seconds()
                if elapsed > limit_timeout:
                    return (
                        False,
                        {
                            "status": "LIMIT_EXCEEDED",
                            "limit_type": "execution_timeout",
                            "halted": True,
                            "execution_id": execution_id,
                            "elapsed_seconds": round(elapsed, 2),
                            "max_timeout_seconds": limit_timeout,
                            "message": f"Execution exceeded maximum duration timeout of {limit_timeout}s. Halted."
                        },
                        "EXECUTION_TIMEOUT"
                    )

            # 3. Total Actions Limit Check
            total_count = conn.execute(
                "SELECT COUNT(*) FROM execution_ledger WHERE execution_id = ?",
                (execution_id,)
            ).fetchone()[0]
            if total_count >= limit_total:
                return (
                    False,
                    {
                        "status": "LIMIT_EXCEEDED",
                        "limit_type": "max_total_actions",
                        "halted": True,
                        "execution_id": execution_id,
                        "total_actions": total_count,
                        "max_total_actions": limit_total,
                        "message": f"Execution exceeded maximum total actions limit of {limit_total}. Halted to prevent token exhaustion."
                    },
                    "MAX_TOTAL_ACTIONS_EXCEEDED"
                )

            # 4. Consecutive Failures Check
            recent_rows = conn.execute(
                "SELECT execution_status FROM execution_ledger WHERE execution_id = ? ORDER BY created_at DESC LIMIT ?",
                (execution_id, limit_failures)
            ).fetchall()
            if len(recent_rows) >= limit_failures and all(r["execution_status"] == "failed" for r in recent_rows):
                return (
                    False,
                    {
                        "status": "LIMIT_EXCEEDED",
                        "limit_type": "max_consecutive_failures",
                        "halted": True,
                        "execution_id": execution_id,
                        "consecutive_failures": len(recent_rows),
                        "max_consecutive_failures": limit_failures,
                        "message": f"Execution halted due to {len(recent_rows)} consecutive action failures. Review error output before proceeding."
                    },
                    "CONSECUTIVE_FAILURES_EXCEEDED"
                )

            # 5. Check Existing Ledger Entry for this (execution_id, signature)
            existing = conn.execute(
                "SELECT * FROM execution_ledger WHERE execution_id = ? AND action_signature = ?",
                (execution_id, signature)
            ).fetchone()

            if existing:
                existing_status = existing["execution_status"]
                attempt_count = existing["attempt_count"]

                # Case A: Read-only action already succeeded -> short-circuit with cached result or trigger stagnation
                if read_only and existing_status in ("succeeded", "stagnant"):
                    new_attempts = attempt_count + 1
                    if new_attempts > limit_repeated:
                        # Stagnation Threshold Hit!
                        conn.execute(
                            "UPDATE execution_ledger SET attempt_count = ?, execution_status = 'stagnant', updated_at = ? WHERE id = ?",
                            (new_attempts, now_iso, existing["id"])
                        )
                        try:
                            cached_res = json.loads(existing["result_json"])
                        except Exception:
                            cached_res = existing["result_json"]

                        return (
                            False,
                            {
                                "status": "STAGNATION_DETECTED",
                                "halted": True,
                                "limit_type": "max_repeated_actions",
                                "action": action_clean,
                                "execution_id": execution_id,
                                "attempt_count": new_attempts,
                                "message": (
                                    f"Repeated action limit reached (action '{action_clean}' repeated {new_attempts} times). "
                                    f"Execution halted to prevent infinite loop. You have already received this data. "
                                    f"Synthesize your final answer now without invoking further tools."
                                ),
                                "cached_data": cached_res
                            },
                            "STAGNATION_DETECTED"
                        )
                    else:
                        # Return cached result directly
                        conn.execute(
                            "UPDATE execution_ledger SET attempt_count = ?, updated_at = ? WHERE id = ?",
                            (new_attempts, now_iso, existing["id"])
                        )
                        try:
                            cached_res = json.loads(existing["result_json"])
                        except Exception:
                            cached_res = existing["result_json"]

                        return (False, cached_res, "DUPLICATE_READ_CACHED")

                # Case B: Action failed previously -> allow legitimate retry unless attempts excessive
                elif existing_status == "failed":
                    new_attempts = attempt_count + 1
                    conn.execute(
                        "UPDATE execution_ledger SET attempt_count = ?, execution_status = 'running', updated_at = ? WHERE id = ?",
                        (new_attempts, now_iso, existing["id"])
                    )
                    with cls._lock:
                        cls._in_flight_locks.add((execution_id, signature))
                    return (True, None, "ALLOWED")

                # Case C: State-changing action repeated identically
                elif not read_only:
                    new_attempts = attempt_count + 1
                    # Guard against runaway identical state-changing loops (e.g. creating same task 5 times)
                    if new_attempts > (limit_repeated + 1):
                        return (
                            False,
                            {
                                "status": "STAGNATION_DETECTED",
                                "halted": True,
                                "limit_type": "max_repeated_actions",
                                "action": action_clean,
                                "execution_id": execution_id,
                                "attempt_count": new_attempts,
                                "message": f"Identical mutating action '{action_clean}' repeated {new_attempts} times. Execution halted to prevent runaway write loop."
                            },
                            "STAGNATION_DETECTED"
                        )
                    conn.execute(
                        "UPDATE execution_ledger SET attempt_count = ?, execution_status = 'running', updated_at = ? WHERE id = ?",
                        (new_attempts, now_iso, existing["id"])
                    )
                    with cls._lock:
                        cls._in_flight_locks.add((execution_id, signature))
                    return (True, None, "ALLOWED")

            # 6. First-time action for this execution and signature: create new ledger record
            record_id = f"ledg_{uuid.uuid4().hex[:12]}"
            conn.execute(
                """
                INSERT INTO execution_ledger (
                    id, execution_id, session_id, objective, action,
                    normalized_parameters, action_signature, execution_status,
                    result_json, error_message, attempt_count, is_read_only,
                    duration_ms, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'running', '{}', '', 1, ?, 0, ?, ?)
                """,
                (
                    record_id, execution_id, session_id, objective or "",
                    action_clean, json.dumps(norm_params), signature,
                    1 if read_only else 0, now_iso, now_iso
                )
            )

        with cls._lock:
            cls._in_flight_locks.add((execution_id, signature))

        return (True, None, "ALLOWED")

    @classmethod
    def record_action_success(
        cls,
        execution_id: str,
        action: str,
        params: Optional[dict] = None,
        result: Any = None,
        duration_ms: int = 0
    ) -> None:
        """Mark action as succeeded and persist JSON result in SQLite."""
        norm_params = cls.normalize_parameters(params)
        action_clean = action.lower().strip()
        signature = cls.compute_action_signature(action_clean, norm_params)

        with cls._lock:
            cls._in_flight_locks.discard((execution_id, signature))

        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            res_json = json.dumps(result, cls=DateTimeEncoder)
        except Exception:
            res_json = json.dumps(str(result))

        with db_session() as conn:
            conn.execute(
                """
                UPDATE execution_ledger
                SET execution_status = 'succeeded',
                    result_json = ?,
                    duration_ms = ?,
                    updated_at = ?
                WHERE execution_id = ? AND action_signature = ?
                """,
                (res_json, duration_ms, now_iso, execution_id, signature)
            )

    @classmethod
    def record_action_failure(
        cls,
        execution_id: str,
        action: str,
        params: Optional[dict] = None,
        error: str = "",
        duration_ms: int = 0
    ) -> None:
        """Mark action as failed and persist error message in SQLite."""
        norm_params = cls.normalize_parameters(params)
        action_clean = action.lower().strip()
        signature = cls.compute_action_signature(action_clean, norm_params)

        with cls._lock:
            cls._in_flight_locks.discard((execution_id, signature))

        now_iso = datetime.now(timezone.utc).isoformat()
        with db_session() as conn:
            conn.execute(
                """
                UPDATE execution_ledger
                SET execution_status = 'failed',
                    error_message = ?,
                    duration_ms = ?,
                    updated_at = ?
                WHERE execution_id = ? AND action_signature = ?
                """,
                (str(error), duration_ms, now_iso, execution_id, signature)
            )

    @classmethod
    def get_execution_progress(cls, execution_id: str) -> dict:
        """Retrieve progress summary and action history for an execution."""
        with db_session() as conn:
            rows = conn.execute(
                "SELECT * FROM execution_ledger WHERE execution_id = ? ORDER BY created_at ASC",
                (execution_id,)
            ).fetchall()
            entries = rows_to_dict_list(rows)

        total = len(entries)
        succeeded = sum(1 for e in entries if e["execution_status"] == "succeeded")
        failed = sum(1 for e in entries if e["execution_status"] == "failed")
        running = sum(1 for e in entries if e["execution_status"] == "running")
        stagnant = sum(1 for e in entries if e["execution_status"] == "stagnant")
        repeated = sum(e["attempt_count"] - 1 for e in entries if e.get("attempt_count", 1) > 1)

        is_stagnant = stagnant > 0
        stagnation_reason = None
        if is_stagnant:
            stagnant_item = next((e for e in entries if e["execution_status"] == "stagnant"), None)
            if stagnant_item:
                stagnation_reason = f"Action '{stagnant_item['action']}' repeated {stagnant_item['attempt_count']} times."

        return {
            "execution_id": execution_id,
            "total_actions": total,
            "succeeded_actions": succeeded,
            "failed_actions": failed,
            "running_actions": running,
            "stagnant_actions": stagnant,
            "repeated_calls_count": repeated,
            "is_stagnant": is_stagnant,
            "stagnation_reason": stagnation_reason,
            "actions_log": [
                {
                    "action": e["action"],
                    "status": e["execution_status"],
                    "attempts": e["attempt_count"],
                    "is_read_only": bool(e["is_read_only"]),
                    "duration_ms": e["duration_ms"],
                    "timestamp": e["created_at"]
                }
                for e in entries
            ]
        }

    @classmethod
    def get_action_record(cls, execution_id: str, action_signature: str) -> Optional[dict]:
        """Fetch a single ledger entry by signature."""
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM execution_ledger WHERE execution_id = ? AND action_signature = ?",
                (execution_id, action_signature)
            ).fetchone()
            if not row:
                return None
            data = row_to_dict(row)
            try:
                data["normalized_parameters"] = json.loads(data.get("normalized_parameters", "{}"))
                data["result_json"] = json.loads(data.get("result_json", "{}"))
            except Exception:
                pass
            return data

    @classmethod
    def clear_execution(cls, execution_id: str) -> None:
        """Purge ledger records and in-flight locks for an execution."""
        with cls._lock:
            to_remove = [item for item in cls._in_flight_locks if item[0] == execution_id]
            for item in to_remove:
                cls._in_flight_locks.discard(item)

        with db_session() as conn:
            conn.execute("DELETE FROM execution_ledger WHERE execution_id = ?", (execution_id,))
