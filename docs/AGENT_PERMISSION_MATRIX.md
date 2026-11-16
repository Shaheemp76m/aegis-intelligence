# Aegis Intelligence — Agent Permission Matrix & Access Control

**Framework Version**: 2.5.0  

---

## 1. Tool Permission Matrix by Agent Role

| Action / Capability | CEO | CTO | Bug Hunter | Repair Engineer | Researcher | CISO | DevOps | QA Manager |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **Read Project Files / Inspect Repo** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **`project_assessment` / Overview** | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ |
| **Manage Tasks (`task_*`)** | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Create / Triage Bugs (`bug_create`, `bug_get`)** | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Resolve Bugs in Database (`bug_resolve`)** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Edit Production Source Files (`edit_file`)** | ⚠️ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Author Tests in `tests/`** | ❌ | ❌ | ✅ (Repro) | ✅ (Regress) | ❌ | ❌ | ❌ | ✅ (Verify) |
| **Run Automated Tests (`run_tests`)** | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ | ✅ |
| **Execute Full Test Suite (`IsolatedTestCase`)**| ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Web Search & Documentation Scraping** | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Manage Knowledge Memory (`memory_*`)** | ✅ | ✅ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Antigravity Instance Discovery (`agy_instance_list`)**| ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Antigravity Instance Controls (`agy_instance_*`)** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Background Jobs (`job_*`)** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ |
| **Review Audit Logs (`audit_logs_get`)** | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| **Enforce Path Sandbox (`validate_path`)** | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| **Evaluate Approvals (`approval_decide`)** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Destructive Actions (Git Force / Reset)** | 🔒 Gate | ❌ | ❌ | ❌ | ❌ | 🔒 Gate | ❌ | ❌ |

*Legend*:  
- ✅ = Permitted autonomously  
- ⚠️ = Permitted only as fallback if no specialist active  
- 🔒 Gate = Requires explicit human approval token (`approval_id`)  
- ❌ = Prohibited for this role  

---

## 2. Risk Level Classifications

### RiskLevel.CRITICAL (Mandatory Human Approval Required)
- `delete_project`, `project_delete`, `delete_project_dir`
- Git force push (`git push -f`, `--force-with-lease`)
- Git hard reset (`git reset --hard`)
- File modification outside validated project root (`PathValidationError`)
- Direct modification of n8n server files or configs

### RiskLevel.HIGH (Mandatory Human Approval Required)
- System package installation (`pkg install`, `apt install`)
- Bulk file deletion (>3 files in a single turn)
- Git untracked clean (`git clean -fdx`)

### RiskLevel.MEDIUM (Autonomous with Audit Logging)
- Task deletion (`task_delete`)
- Bug deletion (`bug_delete`)
- Memory deletion (`memory_delete`)
- Background job cancellation (`job_cancel`, `agy_instance_stop`)

### RiskLevel.LOW (Autonomous Read, Inspection & Standard Development)
- All read-only queries (`project_list`, `project_assessment`, `git_status`, `git_log`, `agy_instance_list`, `task_list`, `bug_list`, `memory_search`)
- Standard development file edits within validated project boundaries (`create_file`, `edit_file`)
- Standard background job launches (`job_start`, `agy_task_submit`)
- Automated test runs (`run_tests`)
