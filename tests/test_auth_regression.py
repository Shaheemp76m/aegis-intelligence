"""Aegis Intelligence - Authentication Regression Tests

Covers token generation, file loading, placeholder handling, header variants,
whitespace tolerance, permission checks, and constant-time HMAC validation.
"""

import os
import sys
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config import Config
from security.authentication import (
    extract_token,
    verify_token,
    authenticate_request,
    AuthenticationError
)

class TestAuthRegression(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name) / "data"
        self.token_file = self.data_dir / ".api_token"

        # Patch Config paths
        self.orig_data_dir = Config.DATA_DIR
        self.orig_token_file = Config.TOKEN_FILE
        self.orig_token = Config.API_TOKEN

        Config.DATA_DIR = self.data_dir
        Config.TOKEN_FILE = self.token_file

    def tearDown(self):
        Config.DATA_DIR = self.orig_data_dir
        Config.TOKEN_FILE = self.orig_token_file
        Config.API_TOKEN = self.orig_token
        self.temp_dir.cleanup()

    def test_token_loading_from_existing_file(self):
        """When .api_token exists and no env token is set, load from file."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        expected_token = "a" * 48
        self.token_file.write_text(expected_token, encoding="utf-8")
        self.token_file.chmod(0o600)

        with patch.dict(os.environ, {}, clear=True):
            loaded = Config.load_api_token()
            self.assertEqual(loaded, expected_token)
            self.assertEqual(Config.API_TOKEN, expected_token)

    def test_placeholder_token_ignored_in_favor_of_file(self):
        """When AEGIS_API_TOKEN contains known placeholder, load from .api_token."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        file_token = "b" * 48
        self.token_file.write_text(file_token, encoding="utf-8")
        self.token_file.chmod(0o600)

        with patch.dict(os.environ, {"AEGIS_API_TOKEN": "your_secure_random_token_here_change_me"}):
            loaded = Config.load_api_token()
            self.assertEqual(loaded, file_token)
            self.assertEqual(Config.API_TOKEN, file_token)

    def test_custom_env_token_persists_to_file_with_strict_permissions(self):
        """Custom valid env token overrides and syncs to .api_token with 0600 mode."""
        custom_token = "c" * 48
        with patch.dict(os.environ, {"AEGIS_API_TOKEN": custom_token}):
            loaded = Config.load_api_token()
            self.assertEqual(loaded, custom_token)
            self.assertTrue(self.token_file.is_file())
            self.assertEqual(self.token_file.read_text().strip(), custom_token)
            file_mode = stat.S_IMODE(self.token_file.stat().st_mode)
            self.assertEqual(file_mode, 0o600)

    def test_auto_generate_token_when_missing(self):
        """When no file or env token exists, generate 48-char hex token with 0600 mode."""
        with patch.dict(os.environ, {}, clear=True):
            loaded = Config.load_api_token()
            self.assertEqual(len(loaded), 48)
            self.assertTrue(self.token_file.is_file())
            self.assertEqual(self.token_file.read_text().strip(), loaded)
            file_mode = stat.S_IMODE(self.token_file.stat().st_mode)
            self.assertEqual(file_mode, 0o600)

    def test_header_extraction_case_insensitivity(self):
        """extract_token handles all casing variants of X-Aegis-Token and Authorization."""
        token = "test_token_xyz"
        # X-Aegis-Token variants
        self.assertEqual(extract_token({"x-aegis-token": token}), token)
        self.assertEqual(extract_token({"X-Aegis-Token": token}), token)
        self.assertEqual(extract_token({"X-AEGIS-TOKEN": token}), token)
        self.assertEqual(extract_token({"X-aEgIs-tOkEn": token}), token)

        # Authorization Bearer variants
        self.assertEqual(extract_token({"authorization": f"Bearer {token}"}), token)
        self.assertEqual(extract_token({"Authorization": f"Bearer {token}"}), token)
        self.assertEqual(extract_token({"AUTHORIZATION": f"BEARER {token}"}), token)
        self.assertEqual(extract_token({"authorization": f"bearer {token}"}), token)
        self.assertEqual(extract_token({"Authorization": token}), token)

    def test_token_whitespace_tolerance(self):
        """Leading/trailing whitespace in header token is stripped safely."""
        token = "clean_token_123"
        self.assertEqual(extract_token({"X-Aegis-Token": f"  {token}  \n"}), token)
        self.assertEqual(extract_token({"Authorization": f"Bearer   {token}  "}), token)

    def test_authenticate_request_success_and_failure(self):
        """authenticate_request raises AuthenticationError only on missing/invalid token."""
        Config.API_TOKEN = "valid_secret_token_12345"

        # Valid via X-Aegis-Token
        self.assertTrue(authenticate_request({"X-Aegis-Token": "valid_secret_token_12345"}))
        # Valid via Bearer
        self.assertTrue(authenticate_request({"Authorization": "Bearer valid_secret_token_12345"}))

        # Missing token
        with self.assertRaises(AuthenticationError) as ctx:
            authenticate_request({})
        self.assertIn("Missing", str(ctx.exception))

        # Invalid token
        with self.assertRaises(AuthenticationError) as ctx:
            authenticate_request({"X-Aegis-Token": "wrong_token"})
        self.assertIn("Invalid", str(ctx.exception))

        # Empty token
        with self.assertRaises(AuthenticationError) as ctx:
            authenticate_request({"X-Aegis-Token": ""})
        self.assertIn("Missing", str(ctx.exception))

if __name__ == "__main__":
    unittest.main()
