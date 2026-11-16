# Aegis Intelligence — Agent Orchestration Architecture

This document specifies the multi-agent coordination topology, runtime execution patterns, task handoff protocols, and safety gates governing Aegis Intelligence.

---

## 1. Multi-Agent Topology & Hierarchy

Aegis Intelligence operates a specialized three-tier agent structure. Rather than relying on a single monolithic prompt, responsibilities are partitioned according to clear operational boundaries:

```
                          ┌──────────────────────────┐
                          │     Telegram User /      │
                          │   Development Engineer   │
                          └─────────────┬────────────┘
                                        │ (Webhook / Command)
                                        ▼
                          ┌──────────────────────────┐
                          │   n8n Workflow Engine    │
                          │   (Gemini AI Agent)      │
                          └─────────────┬────────────┘
                                        │ (POST /api/v1/tools/dispatch)
                                        ▼
    ┌───────────────────────────────────────────────────────────────────────┐
    │                         AEGIS ORCHESTRATOR                            │
    │  - High-level project state analysis (project_assessment)             │
    │  - Plan formulation & task decomposition                              │
    │  - Delegation routing to Bug Hunter or Specialist                     │
    │  - Human approval gating (Risk Level 2 / Level 3 operations)           │
    └──────────────────┬─────────────────────────────────┬──────────────────┘
                       │                                 │
         (Bug / Defect │                                 │ (Architecture /
          Investigation)                                 │  Ecosystem Study)
                       ▼                                 ▼
         ┌───────────────────────────┐     ┌───────────────────────────┐
         │     AEGIS BUG HUNTER      │     │     AEGIS SPECIALIST      │
         │ - Defect reproduction     │     │ - Technical research      │
         │ - Root cause diagnosis    │     │ - Architecture design     │
         │ - Minimal patch creation  │     │ - Dependency analysis     │
         │ - Verification & regression│    │ - Documentation generation│
         └─────────────┬─────────────┘     └─────────────┬─────────────┘
                       │                                 │
                       └────────────────┬────────────────┘
                                        │
                                        ▼
                      ┌───────────────────────────────────┐
                      │    Antigravity CLI Subagents      │
                      │  (Isolated Execution Workspaces)  │
                      └───────────────────────────────────┘
```

---

## 2. Agent Profiles & Functional Boundaries

Detailed profile specifications are located in the [`agents/`](file:///data/data/com.termux/files/home/aegis-intelligence/agents/) directory:

1. **[Aegis Orchestrator](file:///data/data/com.termux/files/home/aegis-intelligence/agents/aegis-orchestrator.md)**:
   - **Role**: Operational command, triage, planning, and task synthesis.
   - **Authority**: High-level task dispatch, project queries, approval gate evaluation, memory recording.
   - **Constraint**: Must never attempt complex multi-file bug investigations or manual large-scale edits directly in a single context window. Delegates deep work.

2. **[Aegis Bug Hunter](file:///data/data/com.termux/files/home/aegis-intelligence/agents/aegis-bug-hunter.md)**:
   - **Role**: Rigorous, scientific diagnosis, reproduction, patch synthesis, and test verification.
   - **Authority**: File reads, targeted file edits, test suite execution, bug state transitions.
   - **Constraint**: Minimal patch rule (no opportunistic refactoring), mandatory regression verification (`python3 -B -m unittest discover tests`).

3. **[Aegis Specialist](file:///data/data/com.termux/files/home/aegis-intelligence/agents/aegis-specialist.md)**:
   - **Role**: Technical architecture, design specifications, technology evaluations, documentation consistency.
   - **Authority**: Read-only codebase mapping, architecture review, documentation authoring.
   - **Constraint**: Strictly evidence-based; explicitly separates verified code facts from inferences.

---

## 3. Communication & Tool Dispatch Contracts

All agent actions execute through the unified HTTP dispatcher:

```http
POST /api/v1/tools/dispatch
Authorization: Bearer <API_TOKEN>
Content-Type: application/json

{
  "action": "<action_name>",
  "parameters": {
    "project_id": "<project_id>",
    ...
  },
  "approval_token": "<token_if_required>"
}
```

### Deterministic Response Envelopes
Every tool invocation returns a uniform, structured envelope:

```json
{
  "status": "success",
  "action": "project_assessment",
  "result": { ... },
  "execution_time_ms": 142.5
}
```

If an error occurs or approval is required:
```json
{
  "status": "error",
  "action": "git_push",
  "error": "Operation requires human approval (Risk Level 2). Approval token missing or expired.",
  "approval_required": true,
  "approval_request_id": "appr_7c8d9e0f1a2b",
  "risk_level": 2
}
```

---

## 4. Context Retention & State Handoff

To maintain continuity across stateless API requests, n8n webhook sessions, and Antigravity execution resets, Aegis uses persistent state primitives:

| State Layer | Storage Target | Access Action / Tool | Use Case |
|---|---|---|---|
| **System Context** | `PROJECT_CONTEXT.md` | Direct file read / write | High-level environment handoff, known limitations, active diagnostics. |
| **Project Memory** | `project_memory` table | `memory_store`, `memory_search`, `memory_list` | Architectural decisions, key configurations, bug postmortems, user preferences. |
| **Task State** | `tasks` table | `task_create`, `task_update`, `task_list` | Multi-step workflows, blocked status tracking, assigned agents. |
| **Bug Registry** | `bugs` table | `bug_create`, `bug_update`, `bug_list` | Unresolved defects, reproduction steps, severity, verified fixes. |
| **Audit Trails** | `data/logs/audit.log` & SQLite `execution_logs` | Direct log inspect / `usage_summary` | Security verifications, tool invocation histories, risk gate audits. |

---

## 5. Preventing Iteration Exhaustion

A major operational constraint when using Gemini through n8n is the hard ceiling of 10 tool iterations per invocation (`maxIterations: 10`).

### The Anti-Pattern (Fine-Grained Tool Chaining)
```
Gemini Iteration 1: git_status
Gemini Iteration 2: git_commits
Gemini Iteration 3: task_list
Gemini Iteration 4: bug_list
Gemini Iteration 5: development_health
Gemini Iteration 6: project_memory_search
Gemini Iteration 7: Reasoning...
==> Iteration limit reached! Premature termination without user response.
```

### The Solution: The Composite Assessment Engine
The Orchestrator invokes **`project_assessment`** (or alias `project_status_report`):
- Single tool call (1 iteration).
- Gathers Git state, recent commits, pending tasks, open bugs, persistent memory, recent files, and health status in a single pass.
- Returns isolated section results (`status: "ok"` or `status: "error"` per section) without failing the whole assessment.
- Frees remaining 9 iterations for intelligent synthesis, planning, or targeted execution.

---

## 6. Execution Safety Gates & Approvals

Aegis enforces a strict 3-tier risk classification:

| Risk Level | Operations | Dispatch Behavior |
|---|---|---|
| **Level 0 (Read-Only)** | `project_assessment`, `git_status`, `task_list`, `bug_list`, `file_read`, etc. | Executed immediately without prompt. |
| **Level 1 (Low-Risk Writes)** | `task_create`, `task_update`, `bug_create`, `memory_store`. | Executed immediately; logged to audit trail. |
| **Level 2 (Destructive Local Ops)** | `git_commit`, `file_write`, `approval_reject`, `agy_execute`. | Requires explicit single-use approval token. |
| **Level 3 (Remote / Irreversible)** | `git_push`, project deletion, token rotation. | Mandatory human approval via Telegram/REST with 15-minute TTL. |

### Approval Lifecycle Flow:
1. Agent dispatches Level 2/3 action without approval token.
2. Aegis rejects with `status: "error"`, returns `approval_request_id`.
3. Notification dispatched to human engineer via Telegram.
4. Engineer reviews diff/command and approves via Telegram inline button or API call.
5. Aegis generates single-use `approval_token`.
6. Agent retries dispatch supplying `approval_token`, which is consumed and invalidated upon execution.
