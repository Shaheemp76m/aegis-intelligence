# Aegis Intelligence — Persistent Project Context & Handoff

**Document Version**: 2.5.0  
**Last Updated**: 2026-11-14  
**Status**: Active Production Development  
**Execution Environment**: Termux on Android (OnePlus 9R, aarch64)  
**Python Runtime**: Python 3.14.10  
**Daemon Binding**: `http://127.0.0.1:8765`  
**Database**: SQLite 3 WAL mode (`data/aegis.db`, Schema Version 4)  
**n8n Version**: 2.47.4 (running on `http://127.0.0.1:5678`, accessed via Cloudflare Tunnel)  
**Primary AI Engine**: Google Gemini via n8n Tools Agent & Antigravity CLI (`agy` v1.5.8 Standalone)  
**Governance Model**: Eight-Agent Autonomous Technology Company (CEO, CTO, Bug Hunter, Repair Engineer, Researcher, CISO, DevOps, QA)

---

## 1. Project Purpose & Core Vision

Aegis Intelligence is a purpose-built, local development operations platform and intelligent control plane running natively in Termux on Android. Rather than operating as a passive conversational chatbot or simple wrapper around shell scripts, Aegis functions as an autonomous technology company and control plane for Antigravity CLI instances. It inspects and analyzes registered software repositories, monitors Git activity, tracks defects and persistent task backlogs, manages long-term architectural memory, orchestrates live Antigravity instances and background builds, and interfaces seamlessly with the developer through Telegram via an n8n workflow.

---

## 2. Verified Current Environment & Stack

| Component | Verified Specification | Notes |
|---|---|---|
| **Operating System** | Android 13/14 Linux Kernel (Termux) | Environment prefix `/data/data/com.termux/files` |
| **Hardware** | OnePlus 9R (Qualcomm Snapdragon 870, aarch64) | 8-core ARM64 CPU |
| **Python** | 3.14.10 | Standard library HTTP server, sqlite3 with WAL support |
| **Database** | SQLite 3 (`data/aegis.db`) | WAL mode, foreign keys enabled, busy timeout 5000ms, Schema Version 4 |
| **API Server** | Custom lightweight regex HTTP router (`server.py`) | Threading HTTPServer, Bearer & `X-Aegis-Token` authentication |
| **CLI Agent Engine** | Antigravity CLI (`agy` v1.5.8 Standalone) | Managed via `/proc` discovery, detached process sessions, and task resumption |
| **Workflow Engine** | n8n v2.47.4 | Local Termux Node.js instance on port 5678, remote tunnel for Telegram webhooks |
| **AI Model in n8n** | Google Gemini (Gemini 2.5 Flash / Gemini Pro) | Connected via n8n AI Agent Node (Tools Agent) |

---

## 3. Existing Capabilities & Dispatcher Catalog

The Aegis backend exposes **56 canonical actions** (plus 50+ bidirectional aliases) through the single unified endpoint `POST /api/v1/tools/dispatch`:

```
Aegis Tool Domains:
├── 1. Project Management
│   ├── project_register, project_list, project_get, project_update,
│   │   project_delete (Gated), project_set_active
├── 2. Inspection, Assessment & Health
│   ├── project_assessment (Composite 1-call overview), project_inspect,
│   │   project_context, project_compare, report_generate,
│   │   development_health, system_health
├── 3. Task Management
│   ├── task_create, task_get, task_update, task_complete,
│   │   task_delete, task_list, task_summary, task_overdue
├── 4. Bug Tracking
│   ├── bug_create, bug_get, bug_update, bug_resolve,
│   │   bug_delete, bug_list, bug_summary
├── 5. Persistent Memory
│   ├── memory_record, memory_get, memory_update,
│   │   memory_delete, memory_search
├── 6. Git Operations
│   ├── git_status, git_commits, git_diff, git_contributors
├── 7. Filesystem Operations
│   ├── file_read, filesystem_inspect, filesystem_recent_files
├── 8. AI Model Management
│   ├── agy_models_list, agy_model_switch
├── 9. Usage Monitoring
│   └── agy_usage_summary
├── 10. Security, Approvals & Auditing
│   ├── approval_list, approval_get, approval_decide, audit_logs_get
├── 11. Telegram Sessions & Anti-Loop Safeguards
│   ├── session_get_or_create, session_add_turn, session_close,
│   │   session_check_dedup, execution_progress
├── 12. Asynchronous Jobs & Builds
│   ├── job_start, job_get, job_list, job_logs, job_cancel
└── 13. Antigravity Instance Control Plane & Task Orchestration
    ├── agy_instance_list, agy_instance_status, agy_instance_start,
    │   agy_instance_stop, agy_instance_output, agy_task_submit, agy_task_status

### Composite Assessment Action (`project_assessment`)
To eliminate multi-roundtrip tool loops and prevent Gemini agent iteration exhaustion in n8n, `project_assessment` (alias: `project_status_report`) collects:
- Project metadata and technology stack
- Git working-tree status and recent commits
- Pending, overdue, and blocked tasks
- Unresolved bugs and severity metrics
- Persistent project memory
- Recently modified files
- Empirical development health (verified facts vs. inferences)

Each section runs with independent error isolation: failure in one section never aborts the overall assessment.

---

## 4. Production Database State (`data/aegis.db`)

The active SQLite database has been verified and contains clean, unpolluted data:

| Table | Count | Verified Records |
|---|:---:|---|
| **`projects`** | **1** | `proj_home_projects_a783bd` ("Home Projects", path: `/data/data/com.termux/files/home/projects`, Git: `git@github.com:Shaheemp76m/geothermal-plant.git`, branch: `main`, stack: Node.js, React, TailwindCSS, TypeScript, Vite) |
| **`tasks`** | **2** | 1 pending high-priority task ("Implement mobile responsiveness optimization"), 1 completed task |
| **`bugs`** | **1** | `bug_05ac1b64f8` (severity: `low`, status: `unverified`) |
| **`project_memory`** | **1** | `mem_204b5c6be6` ("Technology Stack", category: `architecture`) |
| **`approvals`** | **1** | `appr_ff026b348b03` (`delete_project_dir`, status: `REJECTED`) |
| **`backups`** | **1** | Verified historical backup retained in `data/backups/aegis_pre_cleanup_backup_20261113_190845.db` |

---

## 5. Integrations & Security Boundaries

1. **Localhost Network Boundary**:
   - `server.py` binds exclusively to `127.0.0.1:8765`.
   - Incoming request IP checking immediately drops non-loopback connections.
   - Remote access to the system occurs only via the authenticated n8n webhook through Cloudflare Tunnel.
2. **Authentication**:
   - Token stored in `data/.api_token` with `0600` permissions.
   - Supported headers: `X-Aegis-Token: <token>` and `Authorization: Bearer <token>`.
   - Validated using constant-time `secrets.compare_digest`.
3. **Mandatory Approval Workflow**:
   - Destructive operations (`project_delete`, `delete_project_dir`, Git force push, Git hard reset) are classified as `CRITICAL`.
   - Without an approval token, requests trigger HTTP 403 `APPROVAL_REQUIRED` with an approval request ID (`appr_xxxx`).
   - Tokens expire in 15 minutes (900s) and are consumed atomically (`used = 1`).
4. **Filesystem Traversal Guard**:
   - All filesystem operations are verified with `validate_path_within_project(project_root, rel_path)`.
   - Traversal escapes (`../`) and unauthorized root accesses (`/proc`, `/sys`, etc.) throw `PathValidationError`.

---

## 6. Development History & Major Milestones

1. **Milestone 1 — Authentication & Environment Repair**:
   - Diagnosed token resolution discrepancy in Termux; repaired middleware to validate both `X-Aegis-Token` and `Authorization: Bearer`.
   - Hardened `data/.api_token` with 0600 file permissions and constant-time validation.
2. **Milestone 2 — Production Database Cleanup & Isolation**:
   - Audited 35 registered projects, identified 34 test-generated temporary records created by earlier automated test runs.
   - Created verified SQLite backup in `data/backups/`.
   - Cleaned test artifacts and instituted `IsolatedTestCase` in `tests/isolated_test_case.py` ensuring all future test runs use isolated temporary databases.
3. **Milestone 3 — Complete API Dispatcher Coverage Expansion**:
   - Audited all 32 REST endpoints and intelligence module public methods.
   - Expanded `core/tool_router.py` from 29 to 48 actions.
   - Implemented bidirectional `ALIAS_MAP` (normalizing verb-noun calls like `list_tasks` to canonical `task_list`).
   - Updated OpenAPI schema and compiled 1,000+ line n8n tool catalog.
4. **Milestone 4 — Composite Assessment Implementation**:
   - Implemented `project_assessment` (alias: `project_status_report`), aggregating 7 domains in a single read-only call with section error isolation.
   - Added REST endpoint `GET /api/v1/projects/{project_id}/assessment`.
   - Test suite expanded to 76 tests with 100% pass rate.

---

## 7. Known Issues & Active Diagnostic Findings

### Issue: Gemini AI Agent Iteration Exhaustion in n8n
- **Context**: In n8n 2.47.4, the Gemini AI Agent has a configured limit of 10 iterations (`maxIterations: 10`).
- **Observed Symptom**:
  - Simple requests (e.g., *"List my projects"*) complete in 1 iteration and succeed.
  - Complex multi-part requests (e.g., *"Give me a status report including Git status, recent commits, pending tasks, and bugs"*) exhaust all 10 iterations without returning a final response.
- **Root Cause Analysis**:
  - When asked for multiple domain metrics simultaneously, the Gemini agent attempts to call individual fine-grained tools sequentially (`git_status` ➔ `git_commits` ➔ `task_list` ➔ `bug_list` ➔ `development_health`).
  - Between each tool invocation, Gemini emits intermediate reasoning steps and sometimes makes redundant or re-checking calls, hitting the 10-iteration ceiling before synthesizing the final Telegram output.
- **Architectural Solution**:
  - Route complex overview/status queries to the composite `project_assessment` (or `project_status_report`) action, fulfilling the entire request in exactly **1 tool iteration**.
  - Update Gemini system prompt in n8n to prioritize `project_assessment` when multi-domain overview information is requested.

---

## 8. Current Development Priorities

1. **Establish 3-Agent Governance & Instruction System**:
   - Formalize `aegis-orchestrator`, `aegis-bug-hunter`, and `aegis-specialist` roles, delegation protocols, and instruction files.
2. **Two-Layer Telegram Failure Notification System**:
   - Layer A: Agent-level structured error responses (explaining what failed without unneeded retries).
   - Layer B: Dedicated n8n Error Trigger workflow (`Error Trigger` ➔ `Telegram Send Message`).
3. **Comprehensive Documentation Architecture**:
   - Provide exhaustive guides in `docs/` covering architecture, security, database schema, testing, and deployment.
4. **Continuous Quality & Test Isolation**:
   - Maintain 100% test pass rate using `IsolatedTestCase` on all future changes.
