"""Aegis Intelligence - Bug Tracking Module

Maintains verified bug records, diagnosis histories, resolution lifecycles,
and distinguishes unverified suspicions from confirmed defects.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional
from storage.database import db_session, row_to_dict, rows_to_dict_list

VALID_SEVERITIES = {"low", "medium", "high", "critical"}
VALID_VERIFICATION_STATUSES = {
    "unverified",     # Reported/suspected but not yet confirmed
    "reproducing",    # Confirmed defect actively reproducible
    "diagnosed",      # Root cause identified
    "resolved",       # Code fix applied, pending verification
    "verified_fixed"  # Fully verified fixed through test/inspection
}

class BugTracker:
    """Persistent bug and defect tracker."""

    @classmethod
    def create_bug(
        cls,
        project_id: str,
        title: str,
        severity: str = "medium",
        reproduction_steps: str = "",
        affected_files: Optional[list[str]] = None,
        diagnosis: str = "",
        verification_status: str = "unverified"
    ) -> dict:
        """Create a new bug record."""
        if not title or not title.strip():
            raise ValueError("Bug title is required.")

        severity = severity.lower().strip()
        if severity not in VALID_SEVERITIES:
            raise ValueError(f"Invalid severity '{severity}'. Must be one of: {', '.join(sorted(VALID_SEVERITIES))}")

        verification_status = verification_status.lower().strip()
        if verification_status not in VALID_VERIFICATION_STATUSES:
            raise ValueError(
                f"Invalid verification status '{verification_status}'. "
                f"Must be one of: {', '.join(sorted(VALID_VERIFICATION_STATUSES))}"
            )

        bug_id = f"bug_{uuid.uuid4().hex[:10]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        files_json = json.dumps(affected_files or [])

        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO bugs (
                    id, project_id, title, severity, reproduction_steps,
                    affected_files, diagnosis, resolution, verification_status,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, '', ?, ?, ?)
                """,
                (
                    bug_id, project_id, title.strip(), severity,
                    reproduction_steps.strip(), files_json, diagnosis.strip(),
                    verification_status, now_iso, now_iso
                )
            )

        return cls.get_bug(bug_id)

    @classmethod
    def get_bug(cls, bug_id: str) -> Optional[dict]:
        """Retrieve bug record by ID."""
        with db_session() as conn:
            row = conn.execute("SELECT * FROM bugs WHERE id = ?", (bug_id,)).fetchone()
            if not row:
                return None
            data = row_to_dict(row)
            try:
                data["affected_files"] = json.loads(data.get("affected_files", "[]"))
            except Exception:
                data["affected_files"] = []
            return data

    @classmethod
    def update_bug(cls, bug_id: str, **updates) -> dict:
        """Update fields of an existing bug."""
        current = cls.get_bug(bug_id)
        if not current:
            raise ValueError(f"Bug '{bug_id}' not found.")

        allowed_fields = {
            "title", "severity", "reproduction_steps", "affected_files",
            "diagnosis", "resolution", "verification_status"
        }
        set_clauses = []
        params = []
        now_iso = datetime.now(timezone.utc).isoformat()

        for field, val in updates.items():
            if field not in allowed_fields or val is None:
                continue

            if field == "severity":
                val = val.lower().strip()
                if val not in VALID_SEVERITIES:
                    raise ValueError(f"Invalid severity '{val}'.")

            elif field == "verification_status":
                val = val.lower().strip()
                if val not in VALID_VERIFICATION_STATUSES:
                    raise ValueError(f"Invalid verification status '{val}'.")

            elif field == "affected_files":
                val = json.dumps(val if isinstance(val, list) else [])

            set_clauses.append(f"{field} = ?")
            params.append(val)

        if not set_clauses:
            return current

        set_clauses.append("updated_at = ?")
        params.append(now_iso)
        params.append(bug_id)

        sql = f"UPDATE bugs SET {', '.join(set_clauses)} WHERE id = ?"
        with db_session() as conn:
            conn.execute(sql, params)

        return cls.get_bug(bug_id)

    @classmethod
    def resolve_bug(cls, bug_id: str, resolution: str, verified: bool = False) -> dict:
        """Mark bug as resolved or verified fixed."""
        status = "verified_fixed" if verified else "resolved"
        return cls.update_bug(bug_id, resolution=resolution, verification_status=status)

    @classmethod
    def delete_bug(cls, bug_id: str) -> bool:
        """Delete a bug record."""
        with db_session() as conn:
            cur = conn.execute("DELETE FROM bugs WHERE id = ?", (bug_id,))
            return cur.rowcount > 0

    @classmethod
    def list_bugs(
        cls,
        project_id: Optional[str] = None,
        severity: Optional[str] = None,
        verification_status: Optional[str] = None,
        limit: int = 100
    ) -> list[dict]:
        """List bug records matching filters."""
        sql = "SELECT * FROM bugs WHERE 1=1"
        params = []

        if project_id:
            sql += " AND project_id = ?"
            params.append(project_id)

        if severity:
            sql += " AND severity = ?"
            params.append(severity.lower().strip())

        if verification_status:
            sql += " AND verification_status = ?"
            params.append(verification_status.lower().strip())

        sql += " ORDER BY CASE severity WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 WHEN 'low' THEN 4 END, created_at DESC LIMIT ?"
        params.append(limit)

        with db_session() as conn:
            rows = conn.execute(sql, params).fetchall()
            results = []
            for r in rows_to_dict_list(rows):
                try:
                    r["affected_files"] = json.loads(r.get("affected_files", "[]"))
                except Exception:
                    r["affected_files"] = []
                results.append(r)
            return results

    @classmethod
    def get_summary(cls, project_id: str) -> dict:
        """Generate breakdown of bugs by severity and verification state."""
        bugs = cls.list_bugs(project_id=project_id, limit=500)
        summary = {
            "total": len(bugs),
            "by_severity": {s: 0 for s in VALID_SEVERITIES},
            "by_status": {v: 0 for v in VALID_VERIFICATION_STATUSES},
            "unresolved_critical_high": 0
        }

        for b in bugs:
            sev = b.get("severity", "medium")
            stat = b.get("verification_status", "unverified")
            if sev in summary["by_severity"]:
                summary["by_severity"][sev] += 1
            if stat in summary["by_status"]:
                summary["by_status"][stat] += 1
            if sev in ("critical", "high") and stat not in ("resolved", "verified_fixed"):
                summary["unresolved_critical_high"] += 1

        return summary
