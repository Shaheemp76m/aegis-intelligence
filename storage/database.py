"""Aegis Intelligence - Database Storage Layer

Provides SQLite connection management, thread-safe access, and transaction handling.
"""

import sqlite3
import threading
from contextlib import contextmanager
from typing import Generator
from config import Config
from storage.migrations import apply_migrations

# Thread-local storage for sqlite connections
_local = threading.local()

def get_connection(db_path: str = None) -> sqlite3.Connection:
    """Get or create thread-local database connection."""
    target_path = db_path or str(Config.DB_PATH)
    if not hasattr(_local, "connections"):
        _local.connections = {}

    if target_path not in _local.connections:
        conn = sqlite3.connect(target_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        # Enable WAL mode for high concurrency in Termux
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        _local.connections[target_path] = conn

    return _local.connections[target_path]

@contextmanager
def db_session(db_path: str = None) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database transactions."""
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise

def init_db(db_path: str = None) -> None:
    """Initialize database schema and apply pending migrations."""
    target_path = db_path or str(Config.DB_PATH)
    conn = get_connection(target_path)
    apply_migrations(conn)

def row_to_dict(row: sqlite3.Row) -> dict:
    """Convert an sqlite3.Row into a Python dictionary."""
    if row is None:
        return {}
    return {k: row[k] for k in row.keys()}

def rows_to_dict_list(rows: list) -> list[dict]:
    """Convert a list of sqlite3.Row objects into a list of dictionaries."""
    return [row_to_dict(r) for r in rows]
