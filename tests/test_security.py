"""Aegis Intelligence - Security & Path Validation Tests"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from security.path_validator import (
    is_safe_project_directory,
    validate_path_within_project,
    PathValidationError
)
from security.authentication import verify_token
from security.audit_log import redact_secrets
from config import Config

class TestSecurityControls(unittest.TestCase):
    def setUp(self):
        Config.API_TOKEN = "secure_aegis_test_token_987654321"

    def test_constant_time_token_verification(self):
        """Token verification matches correct token and rejects invalid."""
        self.assertTrue(verify_token("secure_aegis_test_token_987654321"))
        self.assertFalse(verify_token("wrong_token"))
        self.assertFalse(verify_token(""))
        self.assertFalse(verify_token("secure_aegis_test_token_987654320"))

    def test_forbidden_system_paths_rejected(self):
        """Root, system, and Termux bin directories must be rejected from registration."""
        for forbidden in ["/", "/proc", "/sys", "/dev", "/data/data/com.termux/files/usr"]:
            is_safe, msg = is_safe_project_directory(forbidden)
            self.assertFalse(is_safe, f"Path {forbidden} should have been rejected")

    def test_nonexistent_directory_rejected(self):
        """Non-existent directory path cannot be registered."""
        is_safe, msg = is_safe_project_directory("/non/existent/path/for/sure/12345")
        self.assertFalse(is_safe)
        self.assertIn("does not exist", msg)

    def test_path_traversal_detection(self):
        """Path traversal attacks (../) must raise PathValidationError."""
        with tempfile.TemporaryDirectory() as tmp_root:
            # Valid subpath
            subfile = os.path.join(tmp_root, "nested", "file.txt")
            os.makedirs(os.path.dirname(subfile), exist_ok=True)
            with open(subfile, "w") as f:
                f.write("hello")

            valid_resolved = validate_path_within_project(tmp_root, "nested/file.txt")
            self.assertEqual(valid_resolved, os.path.realpath(subfile))

            # Directory traversal attempt
            with self.assertRaises(PathValidationError):
                validate_path_within_project(tmp_root, "../../etc/passwd")

            with self.assertRaises(PathValidationError):
                validate_path_within_project(tmp_root, "../")

    def test_secret_redaction(self):
        """Audit logging secret redaction hides sensitive tokens."""
        raw_text = "Here is my secret token: AIzaSyD1234567890abcdef1234567890abc and password='super_secret_pass'"
        redacted = redact_secrets(raw_text)
        self.assertNotIn("AIzaSyD1234567890abcdef1234567890abc", redacted)
        self.assertNotIn("super_secret_pass", redacted)
        self.assertIn("[REDACTED", redacted)

if __name__ == "__main__":
    unittest.main()
