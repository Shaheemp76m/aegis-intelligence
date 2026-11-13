"""Aegis Intelligence - Approval Gate & Permission Tests"""

import os
import sys
import unittest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from tests.isolated_test_case import IsolatedTestCase
from security.approvals import (
    create_approval_request,
    get_approval,
    decide_approval,
    verify_and_consume_approval,
    list_approvals,
    ApprovalRequiredException
)
from core.permission_manager import PermissionManager, RiskLevel

class TestApprovalsAndPermissions(IsolatedTestCase):
    def setUp(self):
        super().setUp()

    def test_risk_classification(self):
        """Operations are classified accurately into risk categories."""
        # Non-destructive reads are autonomous
        risk, req, _ = PermissionManager.classify_action("read_file")
        self.assertEqual(risk, RiskLevel.LOW)
        self.assertFalse(req)

        # Destructive directory delete is CRITICAL
        risk, req, _ = PermissionManager.classify_action("delete_project_dir")
        self.assertEqual(risk, RiskLevel.CRITICAL)
        self.assertTrue(req)

        # Destructive Git reset --hard is CRITICAL
        risk, req, _ = PermissionManager.classify_action("git_command", {"git_subcommand": "reset", "args": ["--hard"]})
        self.assertEqual(risk, RiskLevel.CRITICAL)
        self.assertTrue(req)

        # Git force push is CRITICAL
        risk, req, _ = PermissionManager.classify_action("git_command", {"git_subcommand": "push", "args": ["--force"]})
        self.assertEqual(risk, RiskLevel.CRITICAL)
        self.assertTrue(req)

    def test_approval_lifecycle_and_single_use_guarantee(self):
        """Approval request -> decision -> consumption -> replay prevention."""
        appr = create_approval_request(
            action="delete_project_dir",
            risk_classification=RiskLevel.CRITICAL,
            reason="User requested deletion",
            project_id="proj_xyz"
        )
        aid = appr["id"]
        self.assertEqual(appr["status"], "PENDING")

        # Try to consume while still PENDING -> must fail
        self.assertFalse(verify_and_consume_approval(aid, "delete_project_dir"))

        # Decide APPROVE
        decided = decide_approval(aid, "APPROVED", reason="Admin confirmed via Telegram")
        self.assertEqual(decided["status"], "APPROVED")

        # First consumption must succeed
        self.assertTrue(verify_and_consume_approval(aid, "delete_project_dir"))

        # Second consumption attempt (replay) MUST fail
        self.assertFalse(verify_and_consume_approval(aid, "delete_project_dir"))

    def test_expired_approval_rejected(self):
        """Expired approvals cannot be consumed."""
        from storage.database import db_session
        appr = create_approval_request(
            action="bulk_file_delete",
            risk_classification=RiskLevel.HIGH,
            reason="Bulk delete test"
        )
        aid = appr["id"]

        # Backdate expiration to the past
        past_iso = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        with db_session() as conn:
            conn.execute("UPDATE approvals SET expires_at = ?, status = 'APPROVED' WHERE id = ?", (past_iso, aid))

        # Check consumption fails due to expiration
        self.assertFalse(verify_and_consume_approval(aid, "bulk_file_delete"))

if __name__ == "__main__":
    unittest.main()
