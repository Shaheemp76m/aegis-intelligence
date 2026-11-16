# Aegis Intelligence — Database Architecture & Schema Specification

**Engine**: SQLite 3  
**Journaling Mode**: Write-Ahead Logging (WAL)  
**Database File**: `data/aegis.db`  
**Historical Backup**: `data/backups/aegis_pre_cleanup_backup_20261113_190845.db` (Protected)  
**Migration Manager**: `storage/migrations.py`

---

## 1. Engine Configuration & Concurrency

Aegis uses SQLite in Write-Ahead Logging (WAL) mode to support concurrent read and write operations without blocking:

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;
PRAGMA synchronous = NORMAL;
```

### Connection Management
All database access is centralized through `storage/database.py`:
- **Context Manager**: `with db_session() as conn:` handles transaction commits and automatic rollbacks on unhandled exceptions.
- **Thread-Local Connections**: `get_connection()` reuses per-thread connections.
- **Cleanup**: `close_connections()` closes thread-cached connections, used before and after test suites.

---

## 2. Complete Table Dictionaries

### Table: `projects`
Stores metadata and inspection state for registered code repositories.

```sql
CREATE TABLE projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    description TEXT DEFAULT '',
    git_origin TEXT DEFAULT '',
    git_branch TEXT DEFAULT '',
    languages TEXT DEFAULT '[]',       -- JSON array of strings: ["TypeScript", "HTML"]
    tech_stack TEXT DEFAULT '[]',      -- JSON array of strings: ["React", "Vite"]
    status TEXT DEFAULT 'active',      -- active | archived
    is_active INTEGER DEFAULT 0,       -- 1 if currently selected active project, 0 otherwise
    created_at TEXT NOT NULL,          -- ISO 8601 UTC string
    updated_at TEXT NOT NULL,          -- ISO 8601 UTC string
    last_inspected_at TEXT             -- ISO 8601 UTC string
);
```

---

### Table: `tasks`
Stores persistent tasks, blocker states, priority queues, and completion notes.

```sql
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'pending',   -- backlog | pending | in_progress | blocked | completed | cancelled
    priority TEXT NOT NULL DEFAULT 'medium',  -- low | medium | high | critical
    due_date TEXT,                           -- ISO YYYY-MM-DD or NULL
    related_files TEXT DEFAULT '[]',         -- JSON array of relative paths
    notes TEXT DEFAULT '',                   -- Developer / Agent progress notes
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

---

### Table: `bugs`
Tracks confirmed defects, root-cause diagnoses, and verification states.

```sql
CREATE TABLE bugs (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    title TEXT NOT NULL,
    severity TEXT NOT NULL DEFAULT 'medium',         -- low | medium | high | critical
    reproduction_steps TEXT DEFAULT '',
    affected_files TEXT DEFAULT '[]',               -- JSON array of relative paths
    diagnosis TEXT DEFAULT '',                      -- Root cause analysis
    resolution TEXT DEFAULT '',                     -- Patch description
    verification_status TEXT NOT NULL DEFAULT 'unverified', -- unverified | reproducing | diagnosed | resolved | verified_fixed
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

---

### Table: `project_memory`
Long-term semantic and architectural knowledge store.

```sql
CREATE TABLE project_memory (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'general', -- architecture | decision | discussion | feature | issue | milestone | instruction | summary | general
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'user',      -- user | agent | system
    confidence TEXT NOT NULL DEFAULT 'verified', -- verified | inferred | hypothesized
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);
```

---

### Table: `execution_jobs`
Lifecycle tracker for Antigravity CLI and background coding operations.

```sql
CREATE TABLE execution_jobs (
    id TEXT PRIMARY KEY,
    project_id TEXT,
    action TEXT NOT NULL,                     -- execute | review | test
    prompt TEXT NOT NULL,
    model TEXT,                               -- gemini-3.8-flash-high, etc.
    status TEXT NOT NULL DEFAULT 'queued',    -- queued | running | completed | failed | timeout
    exit_code INTEGER,
    duration_seconds REAL,
    stdout TEXT DEFAULT '',
    stderr TEXT DEFAULT '',
    result_json TEXT DEFAULT '{}',            -- JSON object with parsed metrics
    token_usage TEXT DEFAULT '{}',            -- JSON object: {input_tokens, output_tokens, total_tokens}
    created_at TEXT NOT NULL,
    completed_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
);
```

---

### Table: `approvals`
Single-use approval tokens for sensitive, destructive, or out-of-bounds actions.

```sql
CREATE TABLE approvals (
    id TEXT PRIMARY KEY,                      -- appr_xxxxxxxxxxxx
    operation_id TEXT NOT NULL,               -- op_xxxxxxxxxx
    action TEXT NOT NULL,                     -- project_delete, delete_project_dir, etc.
    project_id TEXT,
    affected_paths TEXT DEFAULT '[]',         -- JSON array of paths impacted
    risk_classification TEXT NOT NULL DEFAULT 'MEDIUM', -- LOW | MEDIUM | HIGH | CRITICAL
    status TEXT NOT NULL DEFAULT 'PENDING',   -- PENDING | APPROVED | REJECTED | EXPIRED
    reason TEXT DEFAULT '',                   -- Reason authorization was required
    decision_reason TEXT DEFAULT '',          -- Reason provided by approving user
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,                 -- Exactly created_at + 900s (15 min)
    decided_at TEXT,
    used INTEGER DEFAULT 0                    -- 1 upon consumption; replay attempts fail
);
```

---

### Table: `audit_logs`
Structured security audit trail with automated secret redaction.

```sql
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    request_id TEXT,
    actor TEXT NOT NULL,                      -- system | telegram_user | anonymous
    action TEXT NOT NULL,                     -- PROJECT_REGISTERED | AUTH_FAILED | etc.
    resource_type TEXT NOT NULL,              -- project | task | bug | approval | api
    resource_id TEXT,
    details TEXT DEFAULT '{}',                -- JSON payload of metadata
    ip TEXT,                                  -- 127.0.0.1
    status TEXT NOT NULL                      -- SUCCESS | FAILED | REJECTED
);
```

---

### Table: `schema_version`
Tracks applied database migrations.

```sql
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);
```

---

## 3. Database Protection Rules

1. **Never Delete Production Data Without Human Approval**: `DELETE FROM projects` is strictly gated.
2. **Never Touch `data/backups/`**: Verified baseline backups (e.g., `aegis_pre_cleanup_backup_20261113_190845.db`) must never be modified or overwritten.
3. **Automated Online Backups**:
   ```python
   # SQLite online backup API ensures consistent copy without locking WAL
   source = sqlite3.connect("data/aegis.db")
   target = sqlite3.connect(backup_path)
   source.backup(target)
   ```
4. **Parameterized Queries Only**: Never format raw strings into SQL queries. Always use `?` parameter placeholders.
