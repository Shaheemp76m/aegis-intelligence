"""Aegis Intelligence - Database Migrations

Defines initial SQLite schema and migration versioning.
"""

import sqlite3

MIGRATIONS = [
    # Migration 1: Initial Aegis Schema
    """
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY,
        applied_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        path TEXT NOT NULL UNIQUE,
        description TEXT DEFAULT '',
        git_origin TEXT DEFAULT '',
        git_branch TEXT DEFAULT '',
        languages TEXT DEFAULT '[]',
        tech_stack TEXT DEFAULT '[]',
        status TEXT DEFAULT 'active',
        is_active INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_inspected_at TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_projects_active ON projects (is_active);

    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'pending',
        priority TEXT NOT NULL DEFAULT 'medium',
        due_date TEXT,
        related_files TEXT DEFAULT '[]',
        notes TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        completed_at TEXT,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks (project_id);
    CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks (status);
    CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks (priority);

    CREATE TABLE IF NOT EXISTS bugs (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        title TEXT NOT NULL,
        severity TEXT NOT NULL DEFAULT 'medium',
        reproduction_steps TEXT DEFAULT '',
        affected_files TEXT DEFAULT '[]',
        diagnosis TEXT DEFAULT '',
        resolution TEXT DEFAULT '',
        verification_status TEXT NOT NULL DEFAULT 'unverified',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_bugs_project ON bugs (project_id);
    CREATE INDEX IF NOT EXISTS idx_bugs_status ON bugs (verification_status);

    CREATE TABLE IF NOT EXISTS project_memory (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'general',
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'user',
        confidence TEXT NOT NULL DEFAULT 'verified',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_memory_project ON project_memory (project_id);
    CREATE INDEX IF NOT EXISTS idx_memory_category ON project_memory (category);

    CREATE TABLE IF NOT EXISTS execution_jobs (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        action TEXT NOT NULL,
        prompt TEXT NOT NULL,
        model TEXT,
        status TEXT NOT NULL DEFAULT 'queued',
        exit_code INTEGER,
        duration_seconds REAL,
        stdout TEXT DEFAULT '',
        stderr TEXT DEFAULT '',
        result_json TEXT DEFAULT '{}',
        token_usage TEXT DEFAULT '{}',
        created_at TEXT NOT NULL,
        completed_at TEXT,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
    );

    CREATE INDEX IF NOT EXISTS idx_jobs_project ON execution_jobs (project_id);
    CREATE INDEX IF NOT EXISTS idx_jobs_status ON execution_jobs (status);

    CREATE TABLE IF NOT EXISTS approvals (
        id TEXT PRIMARY KEY,
        operation_id TEXT NOT NULL,
        action TEXT NOT NULL,
        project_id TEXT,
        affected_paths TEXT DEFAULT '[]',
        risk_classification TEXT NOT NULL DEFAULT 'MEDIUM',
        status TEXT NOT NULL DEFAULT 'PENDING',
        reason TEXT DEFAULT '',
        decision_reason TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        decided_at TEXT,
        used INTEGER DEFAULT 0
    );

    CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals (status);
    CREATE INDEX IF NOT EXISTS idx_approvals_expires ON approvals (expires_at);

    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        request_id TEXT,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id TEXT,
        details TEXT DEFAULT '{}',
        ip TEXT,
        status TEXT NOT NULL
    );

    CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_logs (timestamp);
    """
]

def apply_migrations(conn: sqlite3.Connection) -> None:
    """Run all pending schema migrations inside a transaction."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        );
    """)
    cursor.execute("SELECT MAX(version) FROM schema_version")
    row = cursor.fetchone()
    current_version = row[0] if row and row[0] is not None else 0

    for idx, migration_sql in enumerate(MIGRATIONS, start=1):
        if idx > current_version:
            cursor.executescript(migration_sql)
            import datetime
            cursor.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (idx, datetime.datetime.now(datetime.timezone.utc).isoformat())
            )
    conn.commit()
