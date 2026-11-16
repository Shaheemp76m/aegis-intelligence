# Aegis Intelligence — Delegation Protocol & Contracts

**Governance Version**: 2.5.0  

---

## 1. Assignment Contract Schema

When delegating an objective to a specialist, the CEO (`aegis-orchestrator`) must construct a valid JSON assignment adhering to this specification:

```json
{
  "$schema": "https://aegis.local/schemas/delegation_v1.json",
  "task_id": "tsk_20261114_091b",
  "assigned_agent": "aegis-repair-engineer",
  "project_id": "proj_home_projects_a783bd",
  "objective": "Implement active monitor check in ExecutionManager.get_job() to prevent premature failed status",
  "handoff_source": {
    "agent": "aegis-bug-hunter",
    "artifact_type": "DEFECT_REPORT",
    "reference_id": "DEF-2026-004",
    "uri": "docs/reports/DEF_2026_004.md"
  },
  "constraints": [
    "Do not touch server.py or core/tool_router.py",
    "Must write regression test in tests/test_async_jobs.py",
    "Must preserve existing dictionary keys in get_job() return value",
    "Maximum execution timeout: 60 seconds"
  ],
  "context": {
    "working_directory": "/data/data/com.termux/files/home/aegis-intelligence",
    "key_files": [
      "core/execution_manager.py",
      "tests/test_async_jobs.py"
    ],
    "relevant_memories": ["mem_004"]
  }
}
```

---

## 2. Response Contract Schema

Subordinate agents must return a structured response containing concrete verification evidence:

```json
{
  "$schema": "https://aegis.local/schemas/agent_response_v1.json",
  "task_id": "tsk_20261114_091b",
  "agent": "aegis-repair-engineer",
  "status": "SUCCESS",
  "summary": "Added active monitor thread check in get_job() before declaring an inactive PID failed.",
  "actions_taken": [
    "Analyzed get_job() reconciliation branch at line 438.",
    "Added check for job_id in cls._active_processes or job_id in cls._monitor_threads.",
    "Authored isolated regression test test_04_failed_build."
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

## 3. Delegation Invariants & Safeguards

1. **Iteration Boundary**: No specialist may exceed 3 internal iterations without returning an intermediate status to the CEO.
2. **Context Integrity**: A subordinate agent cannot overwrite or discard context fields provided in the initial contract.
3. **Evidence Requirement**: A status of `SUCCESS` is rejected by the CEO if `verification_results` contains zero tests run or empty log evidence.
4. **Execution Ledger Safeguard**: Every delegation assignment is recorded in the SQLite `execution_ledger`, preventing duplicate execution of identical actions.
