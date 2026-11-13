"""Aegis Intelligence - Approval Gate Management

Manages explicit approval workflows for high-risk, destructive, or out-of-boundary operations.
"""

import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from config import Config
from storage.database import db_session, row_to_dict, rows_to_dict_list
from security.audit_log import log_audit

class ApprovalRequiredException(Exception):
    """Raised when an operation requires explicit user/admin approval before execution."""
    def __init__(self, approval_id: str, action: str, risk: str, reason: str):
        super().__init__(f"Operation requires approval [{risk}]: {reason} (Approval ID: {approval_id})")
        self.approval_id = approval_id
        self.action = action
        self.risk = risk
        self.reason = reason

def is_expired(expires_at_iso: str) -> bool:
    """Check if an ISO timestamp has passed."""
    try:
        exp_dt = datetime.fromisoformat(expires_at_iso)
        if exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > exp_dt
    except Exception:
        return True

def create_approval_request(
    action: str,
    risk_classification: str,
    reason: str,
    project_id: Optional[str] = None,
    affected_paths: Optional[list[str]] = None,
    operation_id: Optional[str] = None
) -> dict:
    """Create a new pending approval gate record in SQLite."""
    approval_id = f"appr_{uuid.uuid4().hex[:12]}"
    op_id = operation_id or f"op_{uuid.uuid4().hex[:10]}"
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=Config.APPROVAL_EXPIRY_SECONDS)
    paths_json = json.dumps(affected_paths or [])

    with db_session() as conn:
        conn.execute(
            """
            INSERT INTO approvals (
                id, operation_id, action, project_id, affected_paths,
                risk_classification, status, reason, created_at, expires_at, used
            ) VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?, ?, ?, 0)
            """,
            (
                approval_id, op_id, action, project_id, paths_json,
                risk_classification, reason, now.isoformat(), expires_at.isoformat()
            )
        )

    log_audit(
        action="APPROVAL_REQUESTED",
        actor="system",
        resource_type="approval",
        resource_id=approval_id,
        details={
            "action": action,
            "risk": risk_classification,
            "reason": reason,
            "paths": affected_paths
        }
    )

    return get_approval(approval_id)

def get_approval(approval_id: str) -> Optional[dict]:
    """Retrieve an approval record by ID with automatic expiration checking."""
    with db_session() as conn:
        row = conn.execute("SELECT * FROM approvals WHERE id = ?", (approval_id,)).fetchone()
        if not row:
            return None
        data = row_to_dict(row)
        try:
            data["affected_paths"] = json.loads(data.get("affected_paths", "[]"))
        except Exception:
            data["affected_paths"] = []

        # Auto-update status if expired while still pending
        if data["status"] == "PENDING" and is_expired(data["expires_at"]):
            data["status"] = "EXPIRED"
            conn.execute("UPDATE approvals SET status = 'EXPIRED' WHERE id = ?", (approval_id,))

        return data

def decide_approval(approval_id: str, decision: str, reason: str = "", actor: str = "telegram_user") -> dict:
    """Record APPROVE or REJECT decision on a pending approval."""
    decision = decision.upper().strip()
    if decision not in ("APPROVE", "REJECT", "APPROVED", "REJECTED"):
        raise ValueError(f"Invalid approval decision '{decision}'. Expected APPROVED or REJECTED.")

    norm_decision = "APPROVED" if decision in ("APPROVE", "APPROVED") else "REJECTED"

    approval = get_approval(approval_id)
    if not approval:
        raise ValueError(f"Approval ID '{approval_id}' not found.")

    if approval["status"] != "PENDING":
        raise ValueError(f"Approval '{approval_id}' is already {approval['status']} and cannot be modified.")

    now_iso = datetime.now(timezone.utc).isoformat()
    with db_session() as conn:
        conn.execute(
            """
            UPDATE approvals
            SET status = ?, decision_reason = ?, decided_at = ?
            WHERE id = ?
            """,
            (norm_decision, reason, now_iso, approval_id)
        )

    log_audit(
        action=f"APPROVAL_{norm_decision}",
        actor=actor,
        resource_type="approval",
        resource_id=approval_id,
        details={"decision": norm_decision, "reason": reason}
    )

    return get_approval(approval_id)

def verify_and_consume_approval(approval_id: str, expected_action: str) -> bool:
    """Validate that an approval is APPROVED, not expired, matches action, and consume it.
    
    Enforces the single-use guarantee: once consumed, it cannot be reused.
    """
    approval = get_approval(approval_id)
    if not approval:
        return False

    if approval["status"] != "APPROVED":
        return False

    if is_expired(approval["expires_at"]):
        return False

    if approval.get("used", 0) == 1:
        # Prevent replay attacks
        return False

    if approval.get("action") != expected_action:
        return False

    # Mark as consumed immediately
    with db_session() as conn:
        conn.execute("UPDATE approvals SET used = 1 WHERE id = ?", (approval_id,))

    log_audit(
        action="APPROVAL_CONSUMED",
        actor="system",
        resource_type="approval",
        resource_id=approval_id,
        details={"action": expected_action}
    )
    return True

def list_approvals(status: Optional[str] = None, limit: int = 50) -> list[dict]:
    """List recent approval gates."""
    with db_session() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM approvals WHERE status = ? ORDER BY created_at DESC LIMIT ?",
                (status.upper(), limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM approvals ORDER BY created_at DESC LIMIT ?",
                (limit,)
            ).fetchall()

        results = []
        for r in rows_to_dict_list(rows):
            try:
                r["affected_paths"] = json.loads(r.get("affected_paths", "[]"))
            except Exception:
                r["affected_paths"] = []
            if r["status"] == "PENDING" and is_expired(r["expires_at"]):
                r["status"] = "EXPIRED"
            results.append(r)
        return results
