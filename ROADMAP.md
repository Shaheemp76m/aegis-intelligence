# Aegis Intelligence — Strategic Development Roadmap

**Version**: 2.5.0  
**Status**: Active  
**Execution Platform**: Termux Linux (Android aarch64)  
**Target Milestone**: v2.5 Production Release

---

## Roadmap Overview & Completed Phases

```
┌────────────────────────────────────────────────────────┐
│ Phase 1: Stabilization & Foundation ✅                 │
│ ├── Localhost Auth & Middleware Hardening              │
│ ├── Database Cleanup & Test Harness Isolation          │
│ └── Complete API-to-Dispatcher Parity (49 Tools)       │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ Phase 2: Eight-Agent Corporate Architecture ✅          │
│ ├── CEO, CTO, Bug Hunter, Repair Engineer, Researcher  │
│ ├── CISO, DevOps/SRE, QA/Release Manager Profiles      │
│ └── Formal Inter-Agent Delegation & Handoff Protocols  │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ Phase 3: n8n & Telegram UX & Anti-Loop Safeguards ✅    │
│ ├── Native Telegram Conversation Session Management    │
│ ├── Dual-Layer Native Telegram Typing Indicator        │
│ ├── Tool Name Collision & LangChain V3 Loop Resolved   │
│ └── SQLite Execution Ledger with Stagnation Halts      │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ Phase 4: Asynchronous Background Job Engine ✅         │
│ ├── Detached Process Spawning & Process Group Cleanup  │
│ ├── Continuous File-Stream Logging to data/jobs/       │
│ ├── Operation-Specific Timeouts (Builds, Installs)     │
│ └── Independent Asynchronous Telegram Completion Alerts│
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ Phase 5: Antigravity Instance Control Plane ✅         │
│ ├── Live OS Process Discovery via /proc Scanning       │
│ ├── Conversation ID Resolution via presence/*.lock     │
│ ├── agy_instance_* & agy_task_* Dispatcher Operations   │
│ └── Natural Language Control Plane for Telegram/Gemini │
└────────────────────────────────────────────────────────┘
```

---

## Phase Details & Completion Criteria

### Phase 1: Stabilization & Foundation ✅ (COMPLETED)
- [x] **Audit & Fix Authentication**: Constant-time `secrets.compare_digest` with 0600 token permissions.
- [x] **Zero-Pollution Test Isolation**: Created `tests.isolated_test_case.IsolatedTestCase`.
- [x] **Full API-to-Dispatcher Parity**: Complete coverage across all domain modules.

### Phase 2: Eight-Agent Corporate Architecture ✅ (COMPLETED)
- [x] **Eight Specialized Agent Profiles**:
  - `aegis-orchestrator`: CEO and central coordinator.
  - `aegis-cto`: Technical architecture, code standards, system specs.
  - `aegis-bug-hunter`: Defect discovery, diagnostics, isolated reproduction.
  - `aegis-repair-engineer`: Surgical bug remediation, atomic patches.
  - `aegis-researcher`: Multi-source ecosystem research (GitHub, docs, Reddit, CVEs).
  - `aegis-ciso`: Security governance, path sandboxing, secret protection.
  - `aegis-devops`: Antigravity instance management, background jobs, Termux health.
  - `aegis-qa`: 100% test pass rate enforcement, independent release gate sign-off.
- [x] **Corporate Governance Documentation**: Created `AGENT_ORGANIZATION.md`, `AGENT_DELEGATION.md`, `AGENT_PERMISSION_MATRIX.md`, and `AGENT_EXECUTION_LIFECYCLE.md`.

### Phase 3: n8n, Telegram UX & Anti-Loop Safeguards ✅ (COMPLETED)
- [x] **Native Telegram Conversation Loop**: Replaced web forms with native Telegram session continuation.
- [x] **Dual-Layer Typing Indicator**: Layer 1 immediate feedback (<50ms) + Layer 2 background daemon heartbeat (every 4s).
- [x] **Anti-Loop Execution Ledger**: Deterministic action signing, attempt tracking, stagnation halting.

### Phase 4: Asynchronous Background Job Execution ✅ (COMPLETED)
- [x] **Detached Process Spawning**: `subprocess.Popen(..., start_new_session=True)`.
- [x] **Continuous File-Stream Logging**: `data/jobs/{job_id}.log` preventing Termux memory bloat.
- [x] **Operation-Specific Timeouts**: 1800s for builds/installs, 600s for tests, 300s default.
- [x] **Independent Telegram Status Alerts**: Direct Telegram API alerts on job completion.

### Phase 5: Antigravity Instance Control Plane ✅ (COMPLETED)
- [x] **Live /proc Process Discovery**: Ground-truth detection of active `agy` instances, PIDs, cwd, and session locks.
- [x] **Instance Lifecycle Operations**: `agy_instance_start`, `agy_instance_stop`, `agy_instance_status`, `agy_instance_output`.
- [x] **Task Orchestration**: `agy_task_submit` with `--conversation <id>` context resumption, `agy_task_status`.
- [x] **Natural Language Tool Orchestration**: Full alignment of Gemini AI Agent in n8n.

**Completion Criteria**: All 3 agent profiles committed with explicit input/output schemas and verified delegation rules.

---

### Phase 3: n8n & Telegram Reliability 🎯 (HIGH PRIORITY)
- [x] **Mitigate Gemini Iteration Exhaustion**: Implement composite read-only action `project_assessment` (alias: `project_status_report`) to fulfill complex overview requests in exactly **1 tool iteration**.
- [ ] **System Prompt Optimization in n8n**: Update Gemini Tools Agent prompt in n8n to instruct the model to prefer `project_assessment` over sequential granular calls when asked for status or summaries.
- [ ] **Two-Layer Failure Notification Architecture**:
  - **Layer A (Agent-Level)**: Format clear, non-technical failure explanations on tool exceptions and propose next actionable steps instead of looping.
  - **Layer B (Workflow-Level)**: Construct dedicated n8n Error Trigger workflow (`Error Trigger` ➔ `Telegram Send Message`) to catch uncaught workflow crashes or tunnel disconnections.
- [ ] **Model Quota & Timeout Handling**: Detect Gemini rate limits and Antigravity timeout conditions with graceful fallback responses.

**Completion Criteria**: Multi-domain project status requests over Telegram succeed in a single iteration without exhausting the 10-iteration limit.

---

### Phase 4: Intelligence & Context Layer Enhancements 📋
- [ ] **Empirical Fact vs. Inference Separation**: Standardize all reporting endpoints to clearly distinguish hard verified facts (Git clean status, test exit codes) from heuristic conclusions.
- [ ] **Enhanced Memory Retrieval**: Implement keyword scoring and tag-based memory retrieval across `architecture`, `decision`, and `instruction` categories.
- [ ] **Automated Task Aging & Blocker Alerts**: Scheduled or on-demand alerts for overdue tasks or unassigned critical bugs.
- [ ] **Multi-Project Matrix Comparison**: Expand `project_compare` to support side-by-side dependency drift and Git branch synchronization checks.

**Completion Criteria**: Intelligence modules provide deterministic, reproducible reports with zero hallucinations.

---

### Phase 5: Advanced DevOps & Execution Orchestration 🚀
- [ ] **Antigravity CLI Background Job Streaming**: Real-time polling and stdout/stderr capture for long-running `agy` coding jobs.
- [ ] **Git Pre-Flight Safeguards**: Automated safety checks before staging or committing (checking for secrets, `.env` files, or unstaged critical changes).
- [ ] **Interactive Telegram Approval Gates**: Full inline button workflow in Telegram for approving gated actions (`project_delete`, force git push).
- [ ] **Automated SQLite Backup Rotation**: Scheduled, atomic database snapshot rotation in `data/backups/`.

**Completion Criteria**: Safe, non-destructive execution of remote development operations via Telegram with complete audit logging.
