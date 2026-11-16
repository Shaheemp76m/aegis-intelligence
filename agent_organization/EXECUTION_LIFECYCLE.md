# Aegis Intelligence — Corporate Execution Lifecycle

**Governance Version**: 2.5.0  

---

## 1. The Five-Stage Operational Lifecycle

Every user request follows a strict five-stage operational lifecycle designed to guarantee reliability, security, and context persistence:

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
│ Phase 2: Dynamic Role Summoning (CEO)                  │
│ - Evaluates which specialists are required             │
│ - Issues strongly-typed delegation contract            │
│ - Enforces iteration budget and operational boundaries │
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

## 2. Stage Breakdown & Guarantees

### Stage 1: Intake & Session State
- Identifies Telegram user ID and active chat ID.
- Reconciles active session in `session_manager.py` (checking deduplication window to discard duplicated rapid clicks).
- Initiates dual-layer typing feedback.

### Stage 2: Dynamic Summoning
- Applies rules from `SUMMONING_RULES.md`. If the request is a simple query, resolves it immediately.
- Dispatches formal JSON assignment contract to specialists.

### Stage 3: Specialist Execution
- Specialists operate within isolated sandboxes.
- File operations validated with `validate_path_within_project()`.
- Shell commands tokenized with `shell=False`.
- Tests run against temporary isolated databases (`IsolatedTestCase`).

### Stage 4: Verification Gate
- QA Manager executes regression passes using `python3 -B -m unittest discover tests`.
- 100% test pass rate enforced. Unverified patches rejected back to Repair Engineer.

### Stage 5: Synthesis & Delivery
- CEO formats summary with clickable file links and quantitative evidence.
- Persists turn into SQLite (`session_add_turn`).
- Shuts down background typing indicator.
