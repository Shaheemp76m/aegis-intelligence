"""Aegis Intelligence - Audit Logging & Secret Redaction

Records all security-relevant operations, execution requests, and approvals
while sanitizing tokens, keys, and confidential environment data.
"""

import re
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from config import Config
from storage.database import db_session, rows_to_dict_list

# Regex patterns for redacting secrets from logs
REDACTION_PATTERNS = [
    (re.compile(r'(?i)(token|key|secret|password|auth|bearer|credential)["\']?\s*[:=]\s*["\']?([^"\'\s,;]+)'), r'\1: [REDACTED]'),
    (re.compile(r'AIza[0-9A-Za-z-_]{35}'), '[REDACTED_GEMINI_KEY]'),
    (re.compile(r'sk-[a-zA-Z0-9]{32,}'), '[REDACTED_API_KEY]'),
]

# Set up dedicated audit logger
_logger = logging.getLogger("aegis.audit")
_logger.setLevel(logging.INFO)

def _init_audit_file_logger():
    if not _logger.handlers:
        Config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_file = Config.LOGS_DIR / "audit.log"
        handler = logging.FileHandler(str(log_file), encoding="utf-8")
        formatter = logging.Formatter('{"time":"%(asctime)s", "level":"%(levelname)s", "msg":%(message)s}')
        handler.setFormatter(formatter)
        _logger.addHandler(handler)

_init_audit_file_logger()

def redact_secrets(text: str) -> str:
    """Mask any discovered tokens or credentials in string."""
    if not isinstance(text, str):
        return text
    redacted = text
    for pattern, replacement in REDACTION_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted

def log_audit(
    action: str,
    actor: str,
    resource_type: str,
    resource_id: str = None,
    status: str = "SUCCESS",
    details: dict = None,
    request_id: str = None,
    ip: str = "127.0.0.1"
) -> None:
    """Record an audit entry into SQLite and audit.log file."""
    now_iso = datetime.now(timezone.utc).isoformat()
    clean_details = details or {}
    
    # Sanitize details
    try:
        details_str = json.dumps(clean_details)
        details_str = redact_secrets(details_str)
        clean_details = json.loads(details_str)
    except Exception:
        details_str = "{}"

    # Log to file
    try:
        log_entry = {
            "timestamp": now_iso,
            "request_id": request_id,
            "actor": actor,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "status": status,
            "details": clean_details,
            "ip": ip
        }
        _logger.info(json.dumps(log_entry))
    except Exception:
        pass

    # Record to SQLite
    try:
        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO audit_logs (
                    timestamp, request_id, actor, action, resource_type,
                    resource_id, details, ip, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now_iso, request_id, actor, action, resource_type,
                    resource_id, details_str, ip, status
                )
            )
    except Exception as e:
        _logger.error(f"Failed to write audit log to database: {e}")

def get_recent_audit_logs(limit: int = 50, action: str = None) -> list[dict]:
    """Retrieve recent audit logs from SQLite."""
    with db_session() as conn:
        if action:
            rows = conn.execute(
                "SELECT * FROM audit_logs WHERE action = ? ORDER BY id DESC LIMIT ?",
                (action, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM audit_logs ORDER BY id DESC LIMIT ?",
                (limit,)
            ).fetchall()
        
        result = []
        for r in rows_to_dict_list(rows):
            try:
                r["details"] = json.loads(r.get("details", "{}"))
            except Exception:
                pass
            result.append(r)
        return result
