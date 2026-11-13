# Aegis Intelligence 🛡️
### Antigravity Project Intelligence & Development Control Backend

Aegis Intelligence is a modular, high-reliability Python backend built specifically for Android Termux environments. It acts as the local intelligence and execution bridge connecting **n8n orchestration workflows**, **Telegram Bot interfaces**, and **Gemini reasoning agents** to the installed **Antigravity CLI (`agy`)** and local software projects.

---

## 1. Architecture Overview

Aegis runs as a lightweight localhost-only HTTP service binding strictly to `127.0.0.1:8765`. It maintains an ACID SQLite database for multi-project metadata, persistent memories, tasks, defects, and execution history.

```
                              ┌────────────────────────────────────────┐
                              │           Telegram User                │
                              └───────────────────┬────────────────────┘
                                                  │ Webhook
                                                  ▼
                              ┌────────────────────────────────────────┐
                              │            Cloudflare Tunnel           │
                              └───────────────────┬────────────────────┘
                                                  │
                                                  ▼
                              ┌────────────────────────────────────────┐
                              │         n8n Orchestration Layer        │
                              │             (Port 5678)                │
                              │   Gemini AI Agent + Tool Calling Nodes │
                              └───────────────────┬────────────────────┘
                                                  │ Localhost HTTP
                                                  │ (X-Aegis-Token)
                                                  ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                        AEGIS INTELLIGENCE BACKEND (Port 8765)                          │
├────────────────────────────────┬───────────────────────────────────────────────────────┤
│ API Layer                      │ GET /health, /api/v1/projects, /api/v1/agy/execute... │
│ Security & Autonomy Guard      │ Path traversal validator, HMAC auth, Approval gates   │
│ Multi-Project Intelligence     │ Git inspector, Filesystem scanner, Stack detector     │
│ Project Memory Engine          │ SQLite persistent memory with keyword search ranking  │
│ Task & Bug Tracker             │ Persistent task states, blocker tracker, bug lifecycle│
│ Antigravity Execution Engine   │ Headless 'agy -p' subprocess executor & job tracker   │
│ Report Generator               │ 8 Telegram Markdown reports (facts vs inferences)     │
└────────────────────────────────┴───────────────────────────────────────────────────────┘
                                                  │
                                                  ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               Target Execution Space                                   │
├────────────────────────────────────────────────┬───────────────────────────────────────┤
│ Registered Repositories (~/projects, etc.)     │ Local Antigravity CLI ('agy')         │
└────────────────────────────────────────────────┴───────────────────────────────────────┘
```

---

## 2. Directory Structure

```
aegis-intelligence/
├── server.py                   # Multi-threaded localhost HTTP service
├── config.py                   # Environment configuration & directory resolver
├── requirements.txt            # Zero-dependency specification for Termux
├── README.md                   # Comprehensive system documentation
├── .env.example                # Sample environment template
├── .gitignore                  # Git ignore rules for runtime files
│
├── core/
│   ├── agy_executor.py         # Headless Antigravity CLI subprocess executor
│   ├── tool_router.py          # Unified dispatcher for Gemini/n8n tool calls
│   ├── execution_manager.py    # Background job tracker with token usage logs
│   └── permission_manager.py   # Autonomy boundaries and mandatory approval gates
│
├── intelligence/
│   ├── project_analyzer.py     # Multi-project registry, stack detector, inspector
│   ├── development_monitor.py  # Health evaluator (facts vs inferences vs unknowns)
│   ├── task_manager.py         # Persistent task lifecycle and blocker tracking
│   ├── bug_tracker.py          # Defect lifecycle (unverified to verified fixed)
│   ├── project_memory.py       # Architecture decisions & memory search
│   ├── context_builder.py      # High-signal prompt briefs for Gemini Agent
│   └── report_generator.py     # 8 structured Telegram Markdown reports
│
├── integrations/
│   ├── git.py                  # Working tree, diff, commit log, contributor analyzer
│   ├── filesystem.py           # Safe directory tree crawler, file reader, size stats
│   ├── terminal.py             # Safe argument-array subprocess runner with timeouts
│   ├── model_manager.py        # Verified CLI model discovery and switcher
│   └── usage_monitor.py        # Token usage aggregation and quota capability check
│
├── security/
│   ├── authentication.py       # Constant-time HMAC token comparison
│   ├── approvals.py            # Approval requests, single-use guarantees, expiration
│   ├── audit_log.py            # Structured rotating audit log & secret redactor
│   └── path_validator.py       # Traversal prevention & directory boundary checks
│
├── storage/
│   ├── database.py             # Thread-local SQLite connection pool in WAL mode
│   └── migrations.py           # Schema definition and automatic versioning
│
├── api/
│   ├── routes.py               # Path regex router for all endpoints
│   ├── schemas.py              # Pure Python lightweight request validator
│   └── responses.py            # Standardized API response envelope generator
│
├── data/                       # Persistent runtime data (survives restarts)
│   ├── aegis.db                # SQLite database
│   ├── .api_token              # Generated secure token file (0600 permissions)
│   ├── projects/               # Project-level artifacts
│   ├── memory/                 # Memory cache
│   ├── reports/                # Saved report files
│   └── logs/                   # audit.log and server.log
│
├── docs/
│   ├── openapi.json            # OpenAPI 3.0.3 machine-readable schema
│   ├── n8n_integration.md      # n8n & Telegram integration guide
│   └── termux_startup.md       # Termux background execution instructions
│
└── tests/
    ├── test_api.py             # HTTP status, auth, envelope, 404 tests
    ├── test_security.py        # Path traversal, forbidden root, secret masking
    ├── test_projects.py        # Project CRUD, stack detection, unregistration
    ├── test_memory.py          # Memory search, task lifecycle, bug verification
    ├── test_execution.py       # Injection prevention, timeout, mock agy parsing
    └── test_approvals.py       # Risk classification, approval lifecycle, single-use
```

---

## 3. Verified Antigravity CLI Capabilities

| Capability | Status | Implementation Details |
| :--- | :---: | :--- |
| **Print / Headless Execution** | ✅ Verified | Tested via `agy -p "<prompt>" --output-format json`. Returns `conversation_id`, `status`, `response`, `duration_seconds`, and `usage` object. |
| **Model Discovery** | ✅ Verified | Tested via `agy models`. Parsed and cataloged (`gemini-3.8-flash-high`, `gemini-3.8-flash-medium`, `gemini-3.8-flash-low`, `claude-sonnet-4-6`, `claude-opus-4-6-thinking`, `gpt-oss-120b-medium`). |
| **Model Selection** | ✅ Verified | Supported via `--model <id>` CLI parameter and active configuration in `~/.gemini/antigravity-cli/settings.json`. |
| **Working Directory Isolation** | ✅ Verified | Handled by executing subprocesses with `cwd` bound to registered project path. |
| **Execution Token Tracking** | ✅ Verified | Per-job token usage (`input_tokens`, `output_tokens`, `thinking_tokens`, `total_tokens`) extracted and aggregated in `aegis.db`. |
| **Account-Level Quota Limits** | ⚠️ Unsupported | The CLI does not provide `usage` or `quota` subcommands. Explicitly returned as `status: "unsupported"`. No fabricated estimates. |

---

## 4. Setup & Running in Termux

### Prerequisites
- Python 3.10+ (Tested on Python 3.14 on Termux AArch64)
- Git
- Antigravity CLI (`agy`) installed and authenticated
- n8n running on `http://127.0.0.1:5678`

### Quick Start
```bash
# 1. Navigate to project
cd ~/aegis-intelligence

# 2. (Optional) Customize environment
cp .env.example .env

# 3. Start the backend service
python3 server.py
```

### Background Execution
```bash
nohup python3 server.py > data/logs/server.log 2>&1 &
```

### Checking Health
```bash
curl -s http://127.0.0.1:8765/health | jq
```

---

## 5. Authentication

All requests to `/api/v1/*` must include the API authentication token:

**Via Header:**
```http
X-Aegis-Token: <token>
```
*or*
```http
Authorization: Bearer <token>
```

Your token is automatically generated upon initial startup and saved securely to `data/.api_token` (or configured via `AEGIS_API_TOKEN` in `.env`).

---

## 6. HTTP API Reference

All responses conform strictly to the standardized envelope:
```json
{
  "success": true,
  "request_id": "req_1234567890ab",
  "data": { ... },
  "error": null
}
```

### Endpoints Table

| Method | Endpoint | Description | Auth Required |
| :--- | :--- | :--- | :---: |
| `GET` | `/health` | Health check & database connectivity probe | No |
| `GET` | `/openapi.json` | Full OpenAPI 3.0.3 specification | No |
| `GET` | `/api/v1/projects` | List all registered projects with task/bug/memory counts | Yes |
| `POST` | `/api/v1/projects` | Register a new project directory | Yes |
| `GET` | `/api/v1/projects/{id}` | Retrieve project details | Yes |
| `PUT` | `/api/v1/projects/{id}` | Update project metadata (name, description, status) | Yes |
| `DELETE` | `/api/v1/projects/{id}` | Unregister project without deleting physical files | Yes |
| `POST` | `/api/v1/projects/{id}/activate` | Set active project for context | Yes |
| `POST` | `/api/v1/projects/{id}/inspect` | Run deep Git, directory, and stack inspection | Yes |
| `GET` | `/api/v1/projects/{id}/report` | Generate Markdown report (`?type=status\|daily\|weekly...`) | Yes |
| `GET` | `/api/v1/projects/{id}/context`| Generate cohesive Markdown context brief for Gemini agent | Yes |
| `POST` | `/api/v1/projects/compare` | Compare development metrics across multiple projects | Yes |
| `GET` | `/api/v1/projects/{id}/tasks` | List tasks (`?status=...&priority=...`) | Yes |
| `POST` | `/api/v1/projects/{id}/tasks` | Create a persistent task | Yes |
| `PUT` | `/api/v1/projects/{id}/tasks/{tid}`| Update task status, priority, or notes | Yes |
| `DELETE` | `/api/v1/projects/{id}/tasks/{tid}`| Delete a task | Yes |
| `GET` | `/api/v1/projects/{id}/bugs` | List bugs (`?severity=...&verification_status=...`) | Yes |
| `POST` | `/api/v1/projects/{id}/bugs` | Log a defect or suspicion | Yes |
| `PUT` | `/api/v1/projects/{id}/bugs/{bid}` | Update bug diagnosis, resolution, or status | Yes |
| `GET` | `/api/v1/projects/{id}/memory` | Search project memory (`?query=...&category=...`) | Yes |
| `POST` | `/api/v1/projects/{id}/memory` | Record architectural decision or milestone note | Yes |
| `DELETE`| `/api/v1/projects/{id}/memory/{mid}`| Delete a memory record | Yes |
| `POST` | `/api/v1/agy/execute` | Execute development work via Antigravity CLI | Yes |
| `GET` | `/api/v1/agy/models` | List verified AI models and active model | Yes |
| `POST` | `/api/v1/agy/model/switch` | Switch default model in configuration | Yes |
| `GET` | `/api/v1/agy/usage` | Aggregated session token usage and quota status | Yes |
| `GET` | `/api/v1/jobs` | List recent execution jobs | Yes |
| `GET` | `/api/v1/jobs/{job_id}` | Retrieve status and output of background job | Yes |
| `GET` | `/api/v1/approvals` | List pending and past approval gates | Yes |
| `POST` | `/api/v1/approvals/{id}/decision`| Approve or reject a gated operation | Yes |
| `POST` | `/api/v1/tools/dispatch` | Single dispatch endpoint for n8n AI Agent tools | Yes |

---

## 7. Autonomy and Permission System

Aegis implements an intelligent autonomy model:

### Autonomous Operations (No Approval Needed)
- Reading source code files within registered project paths.
- Running Git status, commit log, and diff inspections.
- Creating, updating, and completing tasks and bugs.
- Searching and recording project memory.
- Running non-destructive test suites within project directory.
- Standard non-destructive development edits.

### Mandatory Approval Gates (Blocked Until Approved)
- Deleting project directories (`delete_project_dir`).
- Bulk file deletions (`bulk_file_delete`).
- Destructive Git operations (`git reset --hard`, `git clean -fdx`, `git checkout --force`).
- Git force pushing (`git push --force`).
- Installing system-wide packages (`pkg install`, `apt install`).
- Modifying Termux or Android system configurations.
- Modifying n8n infrastructure or credentials.
- Any operation targeting paths outside registered project roots.

When a gated operation is initiated without an approval token, Aegis blocks the request, logs an audit entry, and generates an `appr_...` request record with a 15-minute expiration time. Once approved by the administrator, the approval can be consumed exactly once (single-use guarantee).

---

## 8. Automated Testing

The complete test suite runs in under 30 seconds:

```bash
cd ~/aegis-intelligence
python3 -m unittest discover -s tests -v
```

All 45 automated test cases cover:
- Health check and unauthenticated probing.
- API authentication and constant-time HMAC comparison.
- Path traversal rejection (`../`, forbidden system paths).
- Project registration, stack detection, inspection, and safe unregistration.
- SQLite persistent memory search with keyword ranking.
- Task lifecycle, blocker identification, and overdue detection.
- Bug verification states (unverified suspicion vs diagnosed vs verified fixed).
- Safe subprocess argument arrays and command injection prevention.
- Mocked Antigravity CLI output parsing and token extraction.
- Single-use approval lifecycle and expiration verification.
- Explicit unsupported status for account quota endpoints.

---

## 9. Backup and Restore

All persistent state is stored in SQLite:
`~/aegis-intelligence/data/aegis.db`

### Backup
```bash
sqlite3 ~/aegis-intelligence/data/aegis.db ".backup '~/aegis-intelligence/data/aegis-backup.db'"
```

### Restore
```bash
cp ~/aegis-intelligence/data/aegis-backup.db ~/aegis-intelligence/data/aegis.db
```
