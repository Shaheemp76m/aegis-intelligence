# Aegis Intelligence — Agent Delegation & Communication Protocol

**Framework Version**: 2.5.0  

---

## 1. Structured Delegation Contract

When delegating an initiative or subtask, the CEO (`aegis-orchestrator`) issues a strongly-typed delegation assignment to the designated specialist:

```json
{
  "task_id": "tsk_20261114_081a",
  "assigned_agent": "aegis-repair-engineer",
  "project_id": "proj_home_projects_a783bd",
  "objective": "Fix premature status reconciliation in ExecutionManager.get_job()",
  "handoff_source": {
    "agent": "aegis-bug-hunter",
    "defect_report_id": "DEF-2026-004",
    "defect_file": "docs/reports/DEF_2026_004.md"
  },
  "constraints": [
    "Do not touch core/tool_router.py or server.py",
    "Must preserve existing get_job() return schema",
    "Must write dedicated regression test in tests/test_async_jobs.py",
    "Must execute in under 30s"
  ],
  "context": {
    "key_files": [
      "core/execution_manager.py",
      "tests/test_async_jobs.py"
    ],
    "relevant_memories": ["mem_004"]
  }
}
```

---

## 2. Structured Agent Response Contract

Upon concluding its assigned scope, the subordinate agent must return a standardized response object with empirical verification:

```json
{
  "status": "SUCCESS | FAILED | BLOCKED",
  "task_id": "tsk_20261114_081a",
  "agent": "aegis-repair-engineer",
  "summary": "Added active monitor thread check in get_job() before declaring an inactive PID failed.",
  "actions_taken": [
    "Analyzed get_job() reconciliation branch at line 438.",
    "Added check for job_id in cls._active_processes or job_id in cls._monitor_threads.",
    "Added test case test_04_failed_build_exit_code_preservation in tests/test_async_jobs.py."
  ],
  "files_modified": [
    "core/execution_manager.py",
    "tests/test_async_jobs.py"
  ],
  "artifacts_produced": [
    "docs/patches/PATCH_20261114_004.md"
  ],
  "verification_results": {
    "tests_run": 1,
    "tests_passed": 1,
    "duration_seconds": 1.25,
    "command_executed": "python3 -B -m unittest tests.test_async_jobs.TestAsyncJobs.test_04_failed_build"
  },
  "remaining_risks": [],
  "evidence": "Ran 1 test in 1.250s: OK",
  "recommended_handoff": "aegis-qa"
}
```

---

## 3. Delegation Sequences & Workflows

### Sequence A: Defect Triage & Resolution Pipeline
```
[User Telegram Alert] 
       │
       ▼
[CEO: aegis-orchestrator] (Evaluate & triage)
       │
       ▼ (Contract: task_id, symptoms, stack trace)
[Bug Hunter: aegis-bug-hunter] (Reproduce in isolation & isolate root cause)
       │
       ▼ (Handoff: DEFECT_REPORT)
[Repair Engineer: aegis-repair-engineer] (Minimal atomic fix + regression test)
       │
       ▼ (Handoff: PATCH_PROPOSAL)
[QA Manager: aegis-qa] (Run full test suite 100% pass check)
       │
       ▼ (Sign-off: RELEASE_APPROVED)
[CEO: aegis-orchestrator] (Mark bug resolved & report to user)
```

### Sequence B: Technology Research & Architecture Pipeline
```
[User Natural Language Prompt]
       │
       ▼
[CEO: aegis-orchestrator] (Identify architectural question)
       │
       ▼ (Contract: problem, scope, constraints)
[Researcher: aegis-researcher] (Investigate GitHub, docs, Stack Overflow, Reddit, CVEs)
       │
       ▼ (Handoff: RESEARCH_DOSSIER)
[CTO: aegis-cto] (Evaluate trade-offs & draft ADR / specification)
       │
       ▼ (Review: Threat Model & Sandbox Verification)
[CISO: aegis-ciso] (Verify security boundaries & approval requirements)
       │
       ▼ (Review: Resource Feasibility)
[DevOps: aegis-devops] (Verify Termux/Android memory and runtime feasibility)
       │
       ▼ (Final Plan)
[CEO: aegis-orchestrator] (Synthesize and present proposal to user)
```

---

## 4. Safeguards Against Loop Thrashing

1. **Deterministic Action Deduplication**: `ExecutionLedger` deterministic SHA-256 signing deduplicates identical read-only requests within the same execution turn.
2. **Iteration Budget Caps**: Maximum 3 agent iterations per sub-phase before escalating to the CEO.
3. **No Cross-Talk Without CEO**: Subagents do not independently spawn new subagents without routing through the CEO coordinator.
