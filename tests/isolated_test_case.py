"""Aegis Intelligence - Isolated Test Case Base

Provides clean per-test-suite isolated temporary data directory,
isolated SQLite database, isolated token file, and automatic cleanup.
Guarantees that automated tests NEVER access or modify production data/aegis.db.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from config import Config
from storage.database import init_db, close_connections

class IsolatedTestCase(unittest.TestCase):
    """Base test class guaranteeing total database and directory isolation."""

    _temp_dir = None
    _temp_data_dir = None
    _temp_db_path = None

    @classmethod
    def setUpClass(cls):
        # 1. Clear any cached thread-local SQLite connections
        close_connections()

        # 2. Save original config attributes
        cls._orig_env_db = os.environ.get("AEGIS_DB_PATH")
        cls._orig_env_token = os.environ.get("AEGIS_API_TOKEN")
        cls._orig_data_dir = Config.DATA_DIR
        cls._orig_db_path = Config.DB_PATH
        cls._orig_token_file = Config.TOKEN_FILE
        cls._orig_logs_dir = Config.LOGS_DIR
        cls._orig_reports_dir = Config.REPORTS_DIR
        cls._orig_memory_dir = Config.MEMORY_DIR
        cls._orig_projects_dir = Config.PROJECTS_DIR
        cls._orig_jobs_dir = Config.JOBS_DIR
        cls._orig_token = Config.API_TOKEN

        # 3. Create unique isolated temporary directory for this test class
        cls._temp_dir = tempfile.mkdtemp(prefix=f"aegis_test_{cls.__name__}_")
        cls._temp_data_dir = Path(cls._temp_dir) / "data"
        cls._temp_data_dir.mkdir(parents=True, exist_ok=True)
        cls._temp_db_path = cls._temp_data_dir / "aegis_test.db"

        # 4. Point Config to isolated temp directories
        Config.DATA_DIR = cls._temp_data_dir
        Config.DB_PATH = cls._temp_db_path
        Config.TOKEN_FILE = cls._temp_data_dir / ".api_token"
        Config.LOGS_DIR = cls._temp_data_dir / "logs"
        Config.REPORTS_DIR = cls._temp_data_dir / "reports"
        Config.MEMORY_DIR = cls._temp_data_dir / "memory"
        Config.PROJECTS_DIR = cls._temp_data_dir / "projects"
        Config.JOBS_DIR = cls._temp_data_dir / "jobs"
        Config.API_TOKEN = "aegis_test_isolated_token_secret_0987654321"

        # Update environment variable so any subroutines re-checking env see the isolated DB
        os.environ["AEGIS_DB_PATH"] = str(cls._temp_db_path)

        Config.ensure_directories()

        # Write test token file with 0600 mode
        Config.TOKEN_FILE.write_text(Config.API_TOKEN, encoding="utf-8")
        Config.TOKEN_FILE.chmod(0o600)

        # 5. Initialize clean isolated database schema
        init_db(str(cls._temp_db_path))

    @classmethod
    def tearDownClass(cls):
        # 1. Close all connections to release SQLite file handles
        close_connections()

        # 2. Restore environment variables
        if cls._orig_env_db is not None:
            os.environ["AEGIS_DB_PATH"] = cls._orig_env_db
        else:
            os.environ.pop("AEGIS_DB_PATH", None)

        if cls._orig_env_token is not None:
            os.environ["AEGIS_API_TOKEN"] = cls._orig_env_token
        else:
            os.environ.pop("AEGIS_API_TOKEN", None)

        # 3. Restore Config attributes
        Config.DATA_DIR = cls._orig_data_dir
        Config.DB_PATH = cls._orig_db_path
        Config.TOKEN_FILE = cls._orig_token_file
        Config.LOGS_DIR = cls._orig_logs_dir
        Config.REPORTS_DIR = cls._orig_reports_dir
        Config.MEMORY_DIR = cls._orig_memory_dir
        Config.PROJECTS_DIR = cls._orig_projects_dir
        Config.JOBS_DIR = cls._orig_jobs_dir
        Config.API_TOKEN = cls._orig_token

        # 4. Delete the temporary directory completely
        if cls._temp_dir and os.path.exists(cls._temp_dir):
            shutil.rmtree(cls._temp_dir, ignore_errors=True)
