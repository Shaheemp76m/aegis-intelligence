# Aegis Intelligence — System Architecture Specification

**Document Version**: 2.0.0  
**Status**: Active Production Standard  
**Target Environment**: Termux on Android (Linux aarch64)  
**Host Binding**: `127.0.0.1:8765` (Strict Localhost)

---

## 1. High-Level Architectural Topology

Aegis Intelligence is designed as a modular, lightweight Python service operating directly in Termux on Android. It bridges mobile development environments with local AI orchestration engines (Antigravity CLI and n8n Gemini Agents) without requiring root privileges or heavy container virtualization.

```
+-------------------------------------------------------------------------+
|                               USER                                      |
|                 (Telegram Mobile / Desktop Client)                      |
+------------------------------------+------------------------------------+
                                     |
                                     | Webhook (HTTPS)
                                     v
+-------------------------------------------------------------------------+
|                      CLOUDFLARE SECURE TUNNEL                           |
|       (Encrypted ingress to local Termux n8n Node.js process)           |
+------------------------------------+------------------------------------+
                                     |
                                     | Local loopback HTTP
                                     v
+-------------------------------------------------------------------------+
|                     n8n WORKFLOW ENGINE (v2.47.4)                       |
|   - Telegram Trigger Node                                               |
|   - Gemini AI Agent Node (Tools Agent, Google Gemini LLM)               |
|   - aegis_dispatch Custom HTTP Request Tool                             |
|   - Error Trigger Fallback Handler                                      |
+------------------------------------+------------------------------------+
                                     |
                                     | HTTP POST /api/v1/tools/dispatch
                                     | Header: X-Aegis-Token / Bearer
                                     v
+-------------------------------------------------------------------------+
|                 AEGIS INTELLIGENCE DAEMON (127.0.0.1:8765)              |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  | Request Processing & Security Pipeline                            |  |
|  | - IP Guard (Strictly 127.0.0.1 / ::1)                             |  |
|  | - Constant-Time Token Authenticator (secrets.compare_digest)       |  |
|  | - Request Envelope & JSON Schema Validator                        |  |
|  | - PermissionManager Risk Classifier (LOW / MED / HIGH / CRITICAL) |  |
|  | - Approval Gate Enforcement (create, verify, consume tokens)     |  |
|  +---------------------------------+---------------------------------+  |
|                                    |                                    |
|                                    v                                    |
|  +-------------------------------------------------------------------+  |
|  | Central Dispatcher & Alias Engine (core/tool_router.py)           |  |
|  | - Bidirectional Normalization (list_tasks <-> task_list)          |  |
|  | - 49 Canonical Domain Operations                                  |  |
|  | - Composite Assessment Aggregator (project_assessment)            |  |
|  +----+------------------+-------------------+------------------+----+  |
|       |                  |                   |                  |       |
|       v                  v                   v                  v       |
|  +----------+      +------------+      +------------+      +----------+ |
|  | Project  |      | Task & Bug |      | Memory &   |      | Git & FS | |
|  | Analyzer |      | Managers   |      | Reports    |      | Modules  | |
|  +----+-----+      +-----+------+      +-----+------+      +----+-----+ |
|       |                  |                   |                  |       |
|       +------------------+---------+---------+------------------+       |
|                                    |                                    |
|                                    v                                    |
|  +-------------------------------------------------------------------+  |
|  | SQLite Storage & WAL Persistence Layer (data/aegis.db)             |  |
|  | - projects, tasks, bugs, project_memory, approvals, audit_logs     |  |
|  | - PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON;                 |  |
|  +---------------------------------+---------------------------------+  |
|                                    |                                    |
|                                    v                                    |
|  +-------------------------------------------------------------------+  |
|  | Local CLI Agent Execution Engine                                  |  |
|  | - Antigravity CLI (agy v1.5.8) executed via safe_run_command      |  |
|  | - ExecutionManager job tracker & token metrics persistence        |  |
|  +-------------------------------------------------------------------+  |
+-------------------------------------------------------------------------+
```

---

## 2. Directory Layout & Module Responsibilities

The codebase is strictly organized into functional tiers:

```
aegis-intelligence/
├── server.py              # Lightweight HTTP daemon, request routing, security middleware
├── config.py              # Environment configuration, path resolution, defaults
├── requirements.txt       # Minimal dependencies
├── README.md              # Project overview
├── AGENTS.md              # Central agent governance and operating rules
├── PROJECT_CONTEXT.md     # Persistent system handoff context
├── ROADMAP.md             # Development phases and milestones
├── CHANGELOG.md           # Semantic version history
│
├── api/                   # HTTP Presentation Layer
│   ├── routes.py          # 33 REST route definitions and request handlers
│   ├── schemas.py         # JSON schema validation and boundary checks
│   └── responses.py       # Standardized 4-field success and error envelopes
│
├── core/                  # Orchestration & Governance Layer
│   ├── tool_router.py     # Centralized tool registry (49 tools) & alias normalization
│   ├── permission_manager.py # Autonomy boundary, risk classification & approval enforcement
│   ├── execution_manager.py  # Background job lifecycle and execution database tracker
│   └── agy_executor.py    # Process isolation wrapper around Antigravity CLI (`agy`)
│
├── intelligence/          # Domain Intelligence & Business Logic
│   ├── project_analyzer.py   # Multi-project registry, inspect, compare & composite assessment
│   ├── development_monitor.py# Empirical fact vs. inference health checks, test runners
│   ├── task_manager.py       # Persistent task tracking, transitions, blockers, aging
│   ├── bug_tracker.py        # Verified defect lifecycle, diagnosis, severity breakdowns
│   ├── project_memory.py     # Architecture decisions, lessons, relevance ranking
│   ├── context_builder.py    # Dense Markdown context synthesizers for AI agents
│   └── report_generator.py   # Structured development reporting (status, daily, weekly)
│
├── integrations/          # External System & Subprocess Adapters
│   ├── git.py             # Git porcelain status, commits, diffs, contributors
│   ├── filesystem.py      # Directory tree inspection, recent files, safe read, tech detection
│   ├── terminal.py        # safe_run_command with pre-tokenized args and shell=False
│   ├── model_manager.py   # Antigravity CLI model registry and active model switcher
│   └── usage_monitor.py   # Local session token usage and job execution metrics
│
├── security/              # Defense-in-Depth Security Controls
│   ├── authentication.py  # Constant-time token verification, bearer/header resolution
│   ├── approvals.py       # Single-use approval request creation, expiry, atomic consumption
│   ├── audit_log.py       # Tamper-evident structured audit logger with secret redaction
│   └── path_validator.py  # Strict project root validation, symlink traversal prevention
│
├── storage/               # Data Persistence Layer
│   ├── database.py        # Thread-local SQLite connection pool, WAL mode, dict row helpers
│   └── migrations.py      # Idempotent database schema versioning and bootstrap
│
├── data/                  # Persistent Runtime Data (Protected)
│   ├── aegis.db           # Production SQLite database
│   ├── .api_token         # 48-char random secret (0600 permissions)
│   ├── backups/           # Verified database backup archives
│   ├── logs/              # server.log, audit.log
│   ├── memory/            # Optional memory dumps
│   ├── projects/          # Workspace data
│   └── reports/           # Generated report artifacts
│
├── docs/                  # Comprehensive Technical Documentation
└── tests/                 # Isolated Automated Test Suites
    └── isolated_test_case.py # Isolated temporary database test harness
```

---

## 3. Request Lifecycle & Middleware Pipeline

Every HTTP request received by `server.py` passes through the following sequential pipeline:

```
[ Incoming HTTP Request ]
          │
          ▼
1. IP Address Verification
   - Must match 127.0.0.1 or ::1
   - Non-loopback requests rejected immediately (403 Forbidden)
          │
          ▼
2. CORS & Preflight Filter
   - Allows Origin: null, localhost, 127.0.0.1
   - Rejects untrusted origins
          │
          ▼
3. Request ID Generation
   - Generates unique ID: req_xxxxxxxxxxxx
          │
          ▼
4. Route & Path Resolution
   - Resolves method and regex path pattern in api/routes.py
   - Path variables ({project_id}, {task_id}) extracted
          │
          ▼
5. Authentication Guard
   - Public paths (/health, /openapi.json) bypass auth
   - Resolves token from X-Aegis-Token OR Authorization: Bearer <token>
   - Validates using secrets.compare_digest against data/.api_token
   - Missing/invalid tokens return HTTP 401 Unauthorized
          │
          ▼
6. Payload Decoding & Schema Validation
   - Parses application/json body (max 2MB)
   - Validates required fields, types, and strings in api/schemas.py
          │
          ▼
7. Execution & Permission Enforcement
   - If calling /api/v1/tools/dispatch, passes through PermissionManager
   - If action is CRITICAL or HIGH risk, verifies approval_id
   - Unapproved critical actions raise ApprovalRequiredException (HTTP 403)
          │
          ▼
8. Response Packaging
   - Normalizes data into 4-field envelope:
     { "success": true, "request_id": "...", "data": {...}, "error": null }
          │
          ▼
9. Audit Logging
   - Writes structured JSON record to data/logs/audit.log and audit_logs table
   - Automatically redacts API keys, tokens, and passwords
```

---

## 4. Dispatcher & Alias Resolution Architecture

The dispatcher (`core/tool_router.py`) acts as the single entry point for AI tool calling. To support varied LLM phrasing without brittle routing failures, Aegis uses a two-phase dispatch pattern:

```
                  LLM Request: { "tool": "list_tasks", ... }
                                     │
                                     ▼
1. Case & Whitespace Normalization:  tool_raw = "list_tasks"
                                     │
                                     ▼
2. Alias Map Lookup:                tool = ALIAS_MAP.get("list_tasks") -> "task_list"
                                     │
                                     ▼
3. Permission Enforcement:          PermissionManager.enforce_permission("task_list")
                                     │
                                     ▼
4. Domain Handler Execution:        TaskManager.list_tasks(...)
                                     │
                                     ▼
5. Envelope Response:               { "success": true, "data": [...] }
```

### Supported Aliases
- **Projects**: `list_projects` ➔ `project_list`, `inspect_project` ➔ `project_inspect`, `assess_project` / `project_status_report` ➔ `project_assessment`, `get_project` ➔ `project_get`, `delete_project` ➔ `project_delete`.
- **Tasks**: `list_tasks` ➔ `task_list`, `create_task` ➔ `task_create`, `get_task` ➔ `task_get`, `complete_task` ➔ `task_complete`, `delete_task` ➔ `task_delete`.
- **Bugs**: `list_bugs` ➔ `bug_list`, `create_bug` ➔ `bug_create`, `get_bug` ➔ `bug_get`, `resolve_bug` ➔ `bug_resolve`, `delete_bug` ➔ `bug_delete`.
- **Memory**: `list_memory` / `memory_list` ➔ `memory_search`, `create_memory` ➔ `memory_record`, `get_memory` ➔ `memory_get`.
- **Filesystem**: `read_file` ➔ `file_read`, `inspect_filesystem` ➔ `filesystem_inspect`, `recent_files` ➔ `filesystem_recent_files`.
- **Diagnostics**: `health_check` / `health` ➔ `system_health`.

---

## 5. Composite Action Architecture (`project_assessment`)

When Gemini interacts with n8n, sequential tool calls frequently exhaust n8n's 10-iteration limit. To solve this, `ProjectAnalyzer.assess_project` implements a composite read-only pipeline:

```
                              project_assessment
                                      │
        ┌──────────────┬──────────────┼──────────────┬──────────────┐
        ▼              ▼              ▼              ▼              ▼
   [ project ]      [ git ]        [ tasks ]      [ bugs ]      [ health ]
    Metadata &      Status &       Pending &      Summary &     Empirical
    Tech Stack      Commits        Blockers       Unresolved    Facts vs.
                                                                Inferences
        │              │              │              │              │
        └──────────────┴──────────────┼──────────────┴──────────────┘
                                      │
                                      ▼
                        [ Isolated Section Try/Catch ]
                        - Status: "ok" | "unavailable" | "error"
                        - Errors recorded in section_errors{}
                        - Does NOT abort other sections
                                      │
                                      ▼
                        [ Composite JSON Response ]
```

---

## 6. Antigravity CLI (`agy`) Subprocess Integration

When Aegis delegates code modifications, bug fixing, or automated reviews, it uses `AgyExecutor` (`core/agy_executor.py`):
1. **Subprocess Isolation**: Commands are invoked using Python `subprocess.Popen` with pre-tokenized argument arrays:
   ```python
   cmd = ["agy", "-p", prompt]
   ```
2. **Directory Binding**: The process `cwd` is pinned strictly to the validated project directory.
3. **Timeout Guards**: Configurable execution timeouts (default 120s) kill runaway processes safely.
4. **Output Capture**: Stdout and stderr streams are buffered and parsed for token metrics and result summaries.
5. **Database Job Persistence**: Every execution creates a record in `execution_jobs` tracking duration, exit code, and token usage.
