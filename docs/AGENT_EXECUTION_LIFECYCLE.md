# Aegis Intelligence — Agent Execution Lifecycle & Governance

**Framework Version**: 2.5.0  

---

## 1. End-to-End Operational Lifecycle

Every interaction in Aegis follows a deterministic, evidence-driven lifecycle across five distinct phases:

```
┌────────────────────────────────────────────────────────┐
│ Phase 1: Intake, Session & Intent Evaluation (CEO)     │
│ - Telegram Webhook -> SessionManager -> Check Dedup    │
│ - Dual-Layer Typing Feedback Initiated                 │
│ - Request Classified (Read-Only / Remediation / Build) │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ Phase 2: Role Selection & Delegation (CEO)             │
│ - Evaluates which agents are required                  │
│ - Issues strongly-typed delegation contract            │
│ - Injects project context, constraints, and boundaries │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ Phase 3: Specialist Execution & Handoff Chain          │
│ - Bug Hunter: Reproduce in isolation -> DEFECT_REPORT  │
│ - Repair Engineer: Surgical patch + regression test    │
│ - DevOps: Manage Antigravity instances & build jobs    │
│ - Researcher: Compile multi-source evidence dossier    │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ Phase 4: Independent Verification Gate (QA & CISO)     │
│ - QA executes full test suite (100% pass rate check)   │
│ - CISO verifies path sandboxing & secret protection    │
│ - Release Gate Decision: APPROVED or REJECTED          │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│ Phase 5: Synthesis, Delivery & Persistence (CEO)       │
│ - CEO marks bug/task resolved in SQLite                │
│ - Audit log entry recorded (`JOB_COMPLETED`)           │
│ - Final user response delivered via Telegram           │
│ - Typing heartbeat cleanly terminated                  │
└────────────────────────────────────────────────────────┘
```

---

## 2. Phase-by-Phase Execution Protocol

### Phase 1: Intake & Session Management
1. Incoming Telegram webhook is received by n8n workflow `voXnSaOmStioMwW6`.
2. `SessionManager.get_or_create_session()` identifies chat ID, verifies deduplication window, and initializes conversation context.
3. Layer 1 typing chat action is dispatched immediately (<50ms). Layer 2 daemon heartbeat thread refreshes typing indicator every 4 seconds.

### Phase 2: Role Selection & Delegation
1. The CEO (`aegis-orchestrator`) evaluates user intent.
2. If the request is a simple status query ("Is any Agy instance running?"), the CEO calls `agy_instance_list` directly without activating subagents.
3. If the request involves a bug fix, the CEO triggers the Defect Remediation Sequence.
4. If the request involves a background build, the CEO delegates process management to DevOps via `job_start` or `agy_task_submit`.

### Phase 3: Specialist Execution & Handoff Chain
1. Specialists execute within their defined boundaries in `agents/`.
2. All file accesses are verified using `validate_path_within_project()`.
3. Shell commands are pre-tokenized and executed with `shell=False`.
4. Defect reproduction and fix validation are conducted using `IsolatedTestCase`.

### Phase 4: Independent Verification Gate
1. The QA/Release Manager executes the regression suite: `python3 -B -m unittest discover tests`.
2. If any test fails, the patch is rejected back to the Repair Engineer with failure diagnostics.
3. Only when all tests pass (100% pass rate) does QA grant `RELEASE_APPROVED`.

### Phase 5: Synthesis, Delivery & Persistence
1. The CEO updates database state (updating bug or task status).
2. The final response is delivered to the user with exact file links and empirical test results.
3. `SessionManager.add_turn()` records the exchange into SQLite and shuts off the typing indicator.

---

## 3. Crash Recovery & Resilience Rules

1. **Daemon Restart Recovery**: When the daemon restarts, `ExecutionManager.recover_jobs()` and `AgyInstanceManager.discover_instances()` automatically reconcile live PIDs against SQLite, recovering active monitor threads for surviving processes and transitioning dead processes to `failed` or `terminated`.
2. **Process Group Signals**: Terminating a job or instance sends `os.killpg(pgid, signal.SIGTERM)` followed by `SIGKILL`, ensuring no orphaned subprocesses linger in Termux.
3. **Database Durability**: SQLite operates strictly in WAL mode (`PRAGMA journal_mode=WAL`), guaranteeing that unexpected process kills do not corrupt database tables.
