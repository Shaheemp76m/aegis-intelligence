# Aegis Intelligence — Corporate Permission & Access Control Matrix

**Governance Version**: 2.5.0  

---

## 1. Role-Based Access Control (RBAC) Matrix

| Domain & Tool Name | CEO | CTO | Bug Hunter | Repair Engineer | Researcher | CISO | DevOps | QA Manager | Risk Level |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|---|
| **`project_list`, `project_get`** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | `LOW` |
| **`project_assessment`** | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | `LOW` |
| **`project_register`, `project_update`** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | `LOW` |
| **`project_delete`** | 🔒 Gate | ❌ | ❌ | ❌ | ❌ | 🔒 Gate | ❌ | ❌ | `CRITICAL` |
| **`task_list`, `task_get`, `task_summary`**| ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | `LOW` |
| **`task_create`, `task_update`** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | `LOW` |
| **`task_delete`** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | `MEDIUM` |
| **`bug_list`, `bug_get`, `bug_summary`** | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | `LOW` |
| **`bug_create`** | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | `LOW` |
| **`bug_update`** | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | `LOW` |
| **`bug_resolve`** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | `LOW` |
| **`bug_delete`** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | `MEDIUM` |
| **`memory_record`, `memory_search`** | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | `LOW` |
| **`git_status`, `git_log`, `git_diff`** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | `LOW` |
| **`git_command` (force push / reset hard)**| 🔒 Gate | ❌ | ❌ | ❌ | ❌ | 🔒 Gate | ❌ | ❌ | `CRITICAL` |
| **`file_read`, `filesystem_inspect`** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | `LOW` |
| **`edit_file`, `create_file`** | ⚠️ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | `LOW` (Project Bound) |
| **`job_start`, `job_get`, `job_logs`** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | `LOW` |
| **`job_cancel`** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | `MEDIUM` |
| **`agy_instance_list`, `agy_instance_status`**| ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | `LOW` |
| **`agy_instance_start`, `agy_instance_stop`** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | `MEDIUM` |
| **`agy_task_submit`, `agy_task_status`** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | `LOW` |
| **`run_tests` (Isolated test harness)** | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ | `LOW` |
| **`approval_list`, `approval_decide`** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | `LOW` / Gated |
| **`audit_logs_get`** | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | `LOW` |

*Legend*:  
- ✅ = Autonomously permitted  
- ⚠️ = Fallback only if specialist unassigned  
- 🔒 Gate = Requires explicit human authorization token (`approval_id`)  
- ❌ = Strictly prohibited  

---

## 2. Risk Level Classifications

1. **`RiskLevel.CRITICAL`**: Actions capable of causing irrecoverable data loss, host sandbox escape, or repository history rewriting. Strictly halted with HTTP 403 `APPROVAL_REQUIRED` until an approval token is verified.
2. **`RiskLevel.HIGH`**: Bulk file deletions, system-level package management (`pkg install`), or untracked directory wipes. Requires approval.
3. **`RiskLevel.MEDIUM`**: Database record deletions (tasks, bugs, memory) or job cancellations. Autonomously permitted but permanently logged in the audit trail.
4. **`RiskLevel.LOW`**: Non-destructive reads, inspections, standard scoped file edits within project roots, and test executions.
