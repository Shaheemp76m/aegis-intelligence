# Aegis Intelligence — Complete Dispatcher Tool Catalog

**Document Version**: 2.0.0  
**Target Unified Endpoint**: `POST /api/v1/tools/dispatch`  
**Total Canonical Actions**: **49**  
**Total Supported Aliases**: **43**  
**Security Standard**: Localhost, Header Authentication (`X-Aegis-Token`), Server-Side Risk Gates

---

## 1. Quick Navigation by Domain

| Domain | Canonical Actions | Description |
|---|---|---|
| **1. Project Management** | `project_register`, `project_list`, `project_get`, `project_update`, `project_delete`, `project_set_active` | Project lifecycle, registry, metadata updates, and unregistering. |
| **2. Inspection & Health** | `project_assessment`, `project_inspect`, `project_context`, `project_compare`, `report_generate`, `development_health`, `system_health` | Diagnostic scans, multi-section assessment, context briefs, and reports. |
| **3. Task Management** | `task_create`, `task_get`, `task_update`, `task_complete`, `task_delete`, `task_list`, `task_summary`, `task_overdue` | Persistent task tracking, transitions, blockers, and overdue alerts. |
| **4. Bug Tracking** | `bug_create`, `bug_get`, `bug_update`, `bug_resolve`, `bug_delete`, `bug_list`, `bug_summary` | Defect tracking, diagnosis records, verification lifecycle. |
| **5. Persistent Memory** | `memory_record`, `memory_get`, `memory_update`, `memory_delete`, `memory_search` | Architectural decisions, lessons, and project knowledge store. |
| **6. Git Operations** | `git_status`, `git_commits`, `git_diff`, `git_contributors` | Working-tree status, recent commits, diff inspection, author stats. |
| **7. Filesystem Operations** | `file_read`, `filesystem_inspect`, `filesystem_recent_files` | Safe file reading, directory tree inspection, recently modified files. |
| **8. Antigravity & Jobs** | `agy_execute`, `job_list`, `job_get` | Local Antigravity CLI job execution, background job monitoring. |
| **9. Model Management** | `agy_models_list`, `agy_model_switch` | CLI model inspection and active model switching. |
| **10. Usage Monitoring** | `agy_usage_summary` | Token usage tracking across local sessions. |
| **11. Approvals & Audit** | `approval_list`, `approval_get`, `approval_decide`, `audit_logs_get` | Approval gate inspection, decision recording, and security audit trail. |

---

## 2. Dispatcher Schema & Calling Convention

### Request Payload
```json
{
  "tool": "string (REQUIRED, canonical action name or alias)",
  "params": {
    "key": "value (OPTIONAL, dictionary of arguments for the tool)"
  },
  "approval_id": "string (OPTIONAL, approval token for re-executing gated actions)"
}
```

### Parameter Fallback Rules
- If `project_id` is omitted for any project-scoped tool, Aegis automatically resolves the currently active project (`is_active = 1`).
- If no project is marked active, Aegis falls back to the most recently updated project.

---

## 3. Tool Specifications by Domain

### Domain 1: Project Management

#### `project_assessment` *(Composite Read-Only Tool)*
- **Aliases**: `assess_project`, `project_assess`, `project_overview`, `project_status_report`
- **Risk Level**: `LOW` (Autonomous)
- **Description**: Single-call comprehensive technical assessment. Replaces 5–7 sequential tool calls to prevent LLM iteration exhaustion. Aggregates metadata, Git status, recent commits, tasks, bugs, memory, recently modified files, and development health.
- **Parameters**:
  - `project_id` (string, optional): Project ID. Defaults to active project.
  - `sections` (array of strings, optional): Subset of sections (`["project", "git", "tasks", "bugs", "memory", "filesystem", "health"]`). Defaults to all.
  - `memory_limit` (integer, optional, default: 15): Max memory items.
  - `recent_files_limit` (integer, optional, default: 10): Max recent files.
  - `commits_count` (integer, optional, default: 5): Max commits.
  - `execute_tests` (boolean, optional, default: false): Run tests during health check.

#### `project_list`
- **Aliases**: `list_projects`
- **Risk Level**: `LOW` (Autonomous)
- **Description**: Lists all registered projects with aggregated task, bug, and memory counts.

#### `project_get`
- **Aliases**: `get_project`, `project_detail`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional).

#### `project_register`
- **Aliases**: `register_project`
- **Risk Level**: `LOW` (Autonomous, validated path)
- **Parameters**: `name` (string, required), `path` (string, required), `description` (string, optional).

#### `project_update`
- **Aliases**: `update_project`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional), `name` (string, optional), `description` (string, optional), `status` (string, optional).

#### `project_delete`
- **Aliases**: `delete_project`
- **Risk Level**: `CRITICAL` (**Approval Required**)
- **Description**: Unregisters project from database. Physical files on disk are strictly preserved.
- **Parameters**: `project_id` (string, required).

#### `project_set_active`
- **Aliases**: `set_active_project`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, required).

---

### Domain 2: Inspection, Diagnostics & Reports

#### `project_inspect`
- **Aliases**: `inspect_project`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional). Updates `last_inspected_at`.

#### `project_context`
- **Aliases**: `project_brief`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional).

#### `project_compare`
- **Aliases**: `projects_compare`, `compare_projects`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_ids` (array of strings, optional).

#### `development_health`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional), `execute_tests` (boolean, optional).

#### `system_health`
- **Aliases**: `health_check`, `health`, `check_health`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: None. Returns database connectivity, version, and status.

#### `report_generate`
- **Aliases**: `generate_report`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional), `report_type` (string, optional: `status`, `daily`, `weekly`, `tasks`, `bugs`, `git`, `health`).

---

### Domain 3: Task Management

#### `task_create`
- **Aliases**: `create_task`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, required), `title` (string, required), `description` (string, optional), `status` (string, optional), `priority` (string, optional: `low`, `medium`, `high`, `critical`), `due_date` (string, optional: `YYYY-MM-DD`).

#### `task_get`
- **Aliases**: `get_task`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `task_id` (string, required).

#### `task_update`
- **Aliases**: `update_task`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `task_id` (string, required), updatable task fields.

#### `task_complete`
- **Aliases**: `complete_task`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `task_id` (string, required), `notes` (string, optional).

#### `task_delete`
- **Aliases**: `delete_task`
- **Risk Level**: `MEDIUM` (Autonomous)
- **Parameters**: `task_id` (string, required).

#### `task_list`
- **Aliases**: `list_tasks`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional), `status` (string, optional), `priority` (string, optional), `limit` (integer, optional).

#### `task_summary`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional).

#### `task_overdue`
- **Aliases**: `overdue_tasks`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional).

---

### Domain 4: Bug Tracking

#### `bug_create`
- **Aliases**: `create_bug`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, required), `title` (string, required), `severity` (string, optional: `low`, `medium`, `high`, `critical`), `reproduction_steps` (string, optional), `diagnosis` (string, optional).

#### `bug_get`
- **Aliases**: `get_bug`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `bug_id` (string, required).

#### `bug_update`
- **Aliases**: `update_bug`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `bug_id` (string, required), updatable defect fields.

#### `bug_resolve`
- **Aliases**: `resolve_bug`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `bug_id` (string, required), `resolution` (string, optional), `verified` (boolean, optional).

#### `bug_delete`
- **Aliases**: `delete_bug`
- **Risk Level**: `MEDIUM` (Autonomous)
- **Parameters**: `bug_id` (string, required).

#### `bug_list`
- **Aliases**: `list_bugs`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional), `severity` (string, optional), `verification_status` (string, optional).

#### `bug_summary`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional).

---

### Domain 5: Persistent Project Memory

#### `memory_record`
- **Aliases**: `create_memory`, `record_memory`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, required), `title` (string, required), `content` (string, required), `category` (string, optional: `architecture`, `decision`, `instruction`, `general`), `confidence` (string, optional: `verified`, `inferred`).

#### `memory_get`
- **Aliases**: `get_memory`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `memory_id` (string, required).

#### `memory_update`
- **Aliases**: `update_memory`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `memory_id` (string, required), updatable fields.

#### `memory_delete`
- **Aliases**: `delete_memory`
- **Risk Level**: `MEDIUM` (Autonomous)
- **Parameters**: `memory_id` (string, required).

#### `memory_search`
- **Aliases**: `list_memory`, `memory_list`, `search_memory`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, required), `query` (string, optional), `category` (string, optional).

---

### Domain 6: Git Operations

#### `git_status`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional).

#### `git_commits`
- **Aliases**: `git_log`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional), `count` (integer, optional, default: 10).

#### `git_diff`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional), `staged` (boolean, optional, default: false).

#### `git_contributors`
- **Aliases**: `get_contributors`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional).

---

### Domain 7: Filesystem Operations

#### `file_read`
- **Aliases**: `read_file`
- **Risk Level**: `LOW` (Autonomous, strictly bounded)
- **Parameters**: `project_id` (string, optional), `path` (string, required: relative path inside project).

#### `filesystem_inspect`
- **Aliases**: `inspect_filesystem`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional), `max_depth` (integer, optional, default: 3), `max_files` (integer, optional, default: 200).

#### `filesystem_recent_files`
- **Aliases**: `recent_files`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional), `limit` (integer, optional, default: 15).

---

### Domain 8: Antigravity Execution & Jobs

#### `agy_execute`
- **Aliases**: `agy_execute_query`, `execute_agy`
- **Risk Level**: `LOW` (Sandboxed CLI execution)
- **Parameters**: `prompt` (string, required), `project_id` (string, optional), `model` (string, optional), `timeout` (integer, optional).

#### `job_list`
- **Aliases**: `list_jobs`, `get_jobs`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `project_id` (string, optional), `limit` (integer, optional, default: 25).

#### `job_get`
- **Aliases**: `get_job`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `job_id` (string, required).

---

### Domain 9: Approvals & Audit

#### `approval_list`
- **Aliases**: `list_approvals`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `status` (string, optional: `PENDING`, `APPROVED`, `REJECTED`, `EXPIRED`).

#### `approval_get`
- **Aliases**: `get_approval`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `approval_id` (string, required).

#### `approval_decide`
- **Aliases**: `decide_approval`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `approval_id` (string, required), `decision` (string: `APPROVED` or `REJECTED`), `reason` (string, optional).

#### `audit_logs_get`
- **Aliases**: `get_audit_logs`
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: `limit` (integer, optional, default: 50), `action` (string, optional).
