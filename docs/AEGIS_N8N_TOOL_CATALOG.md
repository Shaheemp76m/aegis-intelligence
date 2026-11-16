# Aegis Intelligence — Unified n8n Tool Integration Catalog

**Document Version**: 1.0.0  
**API Protocol**: HTTP/1.1 REST (JSON)  
**Target Unified Endpoint**: `POST /api/v1/tools/dispatch`  
**Daemon URL**: `http://127.0.0.1:8765`  
**Security Standard**: Localhost-only, Bearer / `X-Aegis-Token` Header, 0600 File Permissions  
**Target Consumer**: Google Gemini AI Agent running in n8n (Termux/Linux)

---

## 1. Architectural Overview & Dispatcher Contract

Aegis Intelligence provides a unified tool dispatch endpoint specifically engineered for AI agent integration:

```http
POST /api/v1/tools/dispatch
Content-Type: application/json
X-Aegis-Token: <your_48_char_token>
```

Instead of requiring an AI agent to configure dozens of independent HTTP endpoints with distinct path parameters, verbs, and query strings, the unified dispatcher accepts the tool name and an arbitrary JSON parameter dictionary, validates permissions, canonicalizes paths, enforces approval gates, and returns a uniform JSON response envelope.

```
┌────────────────────────────────────────────────────────┐
│             n8n Gemini AI Agent Node                   │
│         (Reasoning & Autonomous Tool Calling)          │
└──────────────────────────┬─────────────────────────────┘
                           │ POST /api/v1/tools/dispatch
                           │ { "tool": "...", "params": {...} }
                           ▼
┌────────────────────────────────────────────────────────┐
│         Aegis HTTP Server (127.0.0.1:8765)             │
├────────────────────────────────────────────────────────┤
│ 1. Localhost IP Verification (127.0.0.1 / ::1)         │
│ 2. Constant-Time API Token Authentication              │
│ 3. Payload Validation (JSON Schema Guards)             │
│ 4. PermissionManager Risk Classification & Gates       │
│ 5. ToolRouter Dispatch to Intelligence / Integrations  │
│ 6. Standardized Success / Error Envelope Response      │
└────────────────────────────────────────────────────────┘
```

---

### Request Body Schema

```json
{
  "action": "string (REQUIRED, case-insensitive, e.g. 'project_list', 'task_create'; alias: 'tool')",
  "params": {
    "key": "value (OPTIONAL, JSON object containing tool-specific arguments)"
  },
  "approval_id": "string (OPTIONAL, approval token ID when re-executing gated operations)",
  "execution_id": "string (OPTIONAL, unique agent run ID for deduplication and loop prevention)",
  "session_id": "string (OPTIONAL, conversation session ID linking turns)",
  "objective": "string (OPTIONAL, task objective or prompt driving this execution)"
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `action` (or `tool`) | `string` | **Yes** | The canonical name of the tool to invoke. Validated as a non-empty string; leading/trailing whitespace is stripped and casing is normalized to lowercase. *(Note: When configuring n8n LangChain Tools Agent, using `"action"` prevents n8n's internal `resolveToolName()` from overriding the parent tool name).* |
| `params` | `object` | No | A JSON dictionary containing arguments for the tool. Defaults to `{}` if omitted. |
| `approval_id` | `string` | No | An approved approval request token (e.g., `appr_50574b4389c0`). Required when executing an operation that previously triggered an `APPROVAL_REQUIRED` gate. |
| `execution_id` | `string` | No | Unique agent run identifier (e.g. n8n `$execution.id`). Enables deterministic deduplication, execution tracking, and automatic loop halting. |
| `session_id` | `string` | No | Conversation session identifier linking multiple turns and maintaining chat context. |
| `objective` | `string` | No | Task objective or prompt driving this execution. |

---

### Response Envelope Structure

All responses return a standardized four-field JSON envelope:

#### Success Response (`HTTP 200` / `HTTP 201`)
```json
{
  "success": true,
  "request_id": "req_8af19ff9aa4e",
  "data": { ... },
  "error": null
}
```

#### Standard Error Response (`HTTP 400`, `HTTP 401`, `HTTP 403`, `HTTP 404`, `HTTP 500`)
```json
{
  "success": false,
  "request_id": "req_5ab3f79b73d2",
  "data": null,
  "error": {
    "code": "BAD_REQUEST",
    "message": "Missing required parameter: title"
  }
}
```

#### Approval Required Gate Response (`HTTP 403`)
When an action requires human approval before proceeding:
```json
{
  "success": false,
  "request_id": "req_04fec1472c2d",
  "data": null,
  "error": {
    "code": "APPROVAL_REQUIRED",
    "message": "Operation requires approval [CRITICAL]: Deleting project directory requires explicit confirmation. (Approval ID: appr_1de25269eff1)"
  }
}
```

---

### Parameter Resolution & Active Project Fallback

For all read, inspection, Git, and execution operations requiring a project context:
1. If `params.project_id` is explicitly supplied, Aegis resolves that specific project.
2. If `params.project_id` is omitted or `null`, Aegis automatically falls back to the currently active project (`is_active = 1`).
3. If no project is registered or active, Aegis returns `HTTP 400` with:
   `{"code": "BAD_REQUEST", "message": "No active project registered."}`.

---

## 2. Complete Verified Tool Catalog

There are **29 verified actions** implemented in `core/tool_router.py`.

```
Catalog Summary (29 Tools):
├── 1. Project Management (4 tools)
├── 2. Project Inspection & Reports (2 tools)
├── 3. Task Management (5 tools)
├── 4. Bug Tracking (4 tools)
├── 5. Persistent Memory (2 tools)
├── 6. Git Operations (3 tools)
├── 7. Filesystem Operations (1 tool)
├── 8. Context & Project Comparison (2 tools)
├── 9. Antigravity Execution (1 tool)
├── 10. Model Management (2 tools)
├── 11. Usage Monitoring (1 tool)
└── 12. Approval & Audit Management (3 tools)
```

---

### Domain 1: Project Management

#### 1. `project_register`
- **Description**: Registers a new local project directory with Aegis. Inspects directory, detects language and technology stack, and records in SQLite.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `name` | `string` | **Yes** | — | Display name of the project. |
  | `path` | `string` | **Yes** | — | Absolute filesystem path (must exist, must be readable, cannot be a forbidden system path). |
  | `description` | `string` | No | `""` | Description of the project purpose. |
  | `project_id` | `string` | No | Auto-generated (`proj_<slug>_<hex>`) | Optional custom project ID prefix. |
- **Example Request**:
  ```json
  {
    "tool": "project_register",
    "params": {
      "name": "Geothermal Control Dashboard",
      "path": "/data/data/com.termux/files/home/projects",
      "description": "Primary renewable energy monitoring frontend"
    }
  }
  ```
- **Example Response Data**:
  ```json
  {
    "id": "proj_home_projects_a783bd",
    "name": "Geothermal Control Dashboard",
    "path": "/data/data/com.termux/files/home/projects",
    "description": "Primary renewable energy monitoring frontend",
    "git_origin": "git@github.com:Shaheemp76m/geothermal-plant.git",
    "git_branch": "main",
    "languages": ["HTML", "JavaScript", "TypeScript"],
    "tech_stack": ["Node.js", "React", "TailwindCSS", "TypeScript", "Vite"],
    "status": "active",
    "is_active": 1,
    "created_at": "2026-11-13T17:43:22.566830+00:00"
  }
  ```

#### 2. `project_list`
- **Description**: Lists all registered projects with aggregated counts of pending tasks, active bugs, and memory records.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: None required (`params: {}`).
- **Example Request**:
  ```json
  {
    "tool": "project_list",
    "params": {}
  }
  ```
- **Example Response Data**:
  ```json
  [
    {
      "id": "proj_home_projects_a783bd",
      "name": "Home Projects",
      "path": "/data/data/com.termux/files/home/projects",
      "is_active": 1,
      "languages": ["HTML", "JavaScript", "TypeScript"],
      "tech_stack": ["Node.js", "React", "TailwindCSS", "TypeScript", "Vite"],
      "counts": {
        "tasks": 2,
        "bugs": 1,
        "memory_items": 1
      }
    }
  ]
  ```

#### 3. `project_inspect`
- **Description**: Runs deep inspection on project: analyzes Git branch, uncommitted files, directory tree, dependencies, and detected framework.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `project_id` | `string` | No | Active project | Project ID to inspect. |
- **Example Request**:
  ```json
  {
    "tool": "project_inspect",
    "params": {
      "project_id": "proj_home_projects_a783bd"
    }
  }
  ```
- **Example Response Data**:
  ```json
  {
    "project": { "id": "proj_home_projects_a783bd", "name": "Home Projects" },
    "git": {
      "is_git": true,
      "branch": "main",
      "modified_count": 0,
      "untracked_count": 0,
      "is_clean": true
    },
    "filesystem": {
      "total_files": 42,
      "total_bytes": 142050,
      "config_files": ["package.json", "tailwind.config.js", "vite.config.ts"]
    },
    "inspected_at": "2026-11-14T05:40:00+00:00"
  }
  ```

#### 4. `project_assessment` *(Composite Read-Only Tool)*
- **Description**: Performs a comprehensive, single-call technical assessment of a registered project. Aggregates project metadata, git repository state, pending/overdue/blocked tasks, unresolved bugs, persistent knowledge memory, recently modified files, and empirical development health without multiple round-trips. Each section is isolated so individual errors never fail the entire assessment. Strictly read-only; never mutates project files, Git, or database records.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `project_id` | `string` | No | Active project | Project ID to assess. Falls back to active project. |
  | `sections` | `array[string]` | No | All (`["project", "git", "tasks", "bugs", "memory", "filesystem", "health"]`) | Optional list of specific sections to include. |
  | `memory_limit` | `integer` | No | 15 | Maximum persistent memory entries to retrieve. |
  | `recent_files_limit` | `integer` | No | 10 | Maximum recently modified files to list. |
  | `commits_count` | `integer` | No | 5 | Number of recent git commits to return. |
  | `execute_tests` | `boolean` | No | `false` | Whether to run automated tests during health check. |
- **Example Request**:
  ```json
  {
    "tool": "project_assessment",
    "params": {
      "project_id": "proj_home_projects_a783bd",
      "sections": ["project", "git", "tasks", "bugs", "health"]
    }
  }
  ```
- **Example Response Data**:
  ```json
  {
    "project_id": "proj_home_projects_a783bd",
    "project_name": "Home Projects",
    "project_path": "/data/data/com.termux/files/home/projects",
    "assessed_at": "2026-11-14T07:50:00+00:00",
    "sections_assessed": ["project", "git", "tasks", "bugs", "health"],
    "section_errors": {},
    "project": {
      "status": "ok",
      "id": "proj_home_projects_a783bd",
      "name": "Home Projects",
      "languages": ["TypeScript", "HTML"],
      "tech_stack": ["React", "Vite", "TailwindCSS"],
      "counts": { "tasks": 2, "bugs": 1, "memory_items": 1 }
    },
    "git": {
      "status": "ok",
      "is_git": true,
      "branch": "main",
      "is_clean": true,
      "ahead": 0,
      "behind": 0,
      "recent_commits": [
        { "hash": "a1b2c3d", "author": "Dev", "message": "feat: init" }
      ]
    },
    "tasks": {
      "status": "ok",
      "summary": { "total": 2, "blocked_count": 0, "overdue_count": 0 },
      "counts": { "total": 2, "pending": 1, "in_progress": 0, "overdue": 0, "blocked": 0 },
      "pending": [ { "id": "task_1", "title": "Implement mobile UI" } ],
      "overdue": [],
      "blocked": []
    },
    "bugs": {
      "status": "ok",
      "summary": { "total": 1, "unresolved_critical_high": 0 },
      "unresolved_count": 1,
      "unresolved": [ { "id": "bug_1", "title": "Cache key collision", "severity": "low" } ]
    },
    "health": {
      "status": "ok",
      "verified_facts": [ "Git repository is clean", "0 high-severity bugs open" ],
      "inferred_conclusions": [ "Development baseline is stable" ],
      "recommended_actions": [ "Proceed with pending backlog tasks" ]
    }
  }
  ```

#### 5. `project_set_active`
- **Description**: Designates a registered project as the primary active workspace for all subsequent operations.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `project_id` | `string` | **Yes** | — | Project ID to activate. |
- **Example Request**:
  ```json
  {
    "tool": "project_set_active",
    "params": { "project_id": "proj_home_projects_a783bd" }
  }
  ```

---

### Domain 2: Project Inspection & Reports

#### 5. `report_generate`
- **Description**: Compiles a comprehensive development report formatted in GitHub Flavored Markdown, tailored for Telegram transmission.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `report_type` | `string` | No | `"status"` | One of: `status`, `daily`, `weekly`, `tasks`, `bugs`, `git`, `health`, `multi_project`. |
  | `project_id` | `string` | No | Active project | Target project ID. |
- **Example Request**:
  ```json
  {
    "tool": "report_generate",
    "params": {
      "project_id": "proj_home_projects_a783bd",
      "report_type": "status"
    }
  }
  ```
- **Example Response Data**:
  ```json
  {
    "report": "## Status Report: Home Projects\n- **Branch**: main (Clean)\n- **Tasks**: 1 Pending, 1 Completed\n- **Bugs**: 1 Unverified\n- **Active Stack**: React 18, Vite, TypeScript"
  }
  ```

---

### Domain 3: Task Management

#### 6. `task_create`
- **Description**: Records a new persistent development task in SQLite.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `project_id` | `string` | **Yes** | — | Project to associate task with. |
  | `title` | `string` | **Yes** | — | Concise task description. |
  | `description` | `string` | No | `""` | Detailed technical notes or acceptance criteria. |
  | `priority` | `string` | No | `"medium"` | Priority: `low`, `medium`, `high`, `critical`. |
  | `status` | `string` | No | `"pending"` | Status: `pending`, `in_progress`, `blocked`, `completed`, `cancelled`. |
  | `due_date` | `string` | No | `null` | ISO 8601 date string (e.g. `2026-11-20`). |
  | `related_files` | `array[str]` | No | `[]` | List of relative file paths relevant to the task. |
  | `notes` | `string` | No | `""` | Blocker notes or delivery links. |
- **Example Request**:
  ```json
  {
    "tool": "task_create",
    "params": {
      "project_id": "proj_home_projects_a783bd",
      "title": "Optimize geothermal sensor polling interval",
      "priority": "high",
      "status": "in_progress",
      "related_files": ["src/sensors/poller.ts"]
    }
  }
  ```

#### 7. `task_update`
- **Description**: Updates fields of an existing task.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `task_id` | `string` | **Yes** | — | Task ID (e.g. `task_0c5ac09b69`). |
  | *(all other fields)* | `any` | No | — | Any field from `task_create` to update (`title`, `status`, `priority`, `notes`, etc.). |
- **Example Request**:
  ```json
  {
    "tool": "task_update",
    "params": {
      "task_id": "task_0c5ac09b69",
      "status": "in_progress",
      "notes": "Work underway in branch feature/mobile-opt"
    }
  }
  ```

#### 8. `task_complete`
- **Description**: Marks a task as `completed`, timestamps `completed_at`, and appends completion notes.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `task_id` | `string` | **Yes** | — | Task ID. |
  | `notes` | `string` | No | `""` | Resolution or delivery summary. |
- **Example Request**:
  ```json
  {
    "tool": "task_complete",
    "params": {
      "task_id": "task_0c5ac09b69",
      "notes": "Verified responsive layout across iOS and Android viewports."
    }
  }
  ```

#### 9. `task_list`
- **Description**: Retrieves tasks filtered by project, status, or priority.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `project_id` | `string` | No | `null` | Filter by project ID. |
  | `status` | `string` | No | `null` | Filter by status (`pending`, `in_progress`, `blocked`, `completed`). |
  | `priority` | `string` | No | `null` | Filter by priority (`critical`, `high`, `medium`, `low`). |
  | `limit` | `integer` | No | `100` | Maximum tasks to return. |
- **Example Request**:
  ```json
  {
    "tool": "task_list",
    "params": {
      "project_id": "proj_home_projects_a783bd",
      "status": "blocked"
    }
  }
  ```

#### 10. `task_summary`
- **Description**: Returns statistical metrics, total task breakdown, blockers list, and completion rate percentage.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `project_id` | `string` | **Yes** | — | Project ID. |
- **Example Request**:
  ```json
  {
    "tool": "task_summary",
    "params": { "project_id": "proj_home_projects_a783bd" }
  }
  ```
- **Example Response Data**:
  ```json
  {
    "total": 3,
    "by_status": { "completed": 1, "in_progress": 1, "blocked": 1 },
    "by_priority": { "critical": 1, "high": 1, "medium": 1 },
    "blocked_count": 1,
    "blockers": [{ "id": "task_xxx", "title": "Awaiting API key", "notes": "Blocked on third-party" }],
    "completion_rate": 33.3
  }
  ```

---

### Domain 4: Bug Tracking

#### 11. `bug_create`
- **Description**: Records a suspected or confirmed defect with reproduction steps and verification state.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `project_id` | `string` | **Yes** | — | Project ID. |
  | `title` | `string` | **Yes** | — | Bug summary. |
  | `severity` | `string` | No | `"medium"` | `low`, `medium`, `high`, `critical`. |
  | `verification_status` | `string` | No | `"unverified"` | `unverified`, `suspected`, `diagnosed`, `fix_in_progress`, `verified_fixed`, `cannot_reproduce`. |
  | `reproduction_steps` | `string` | No | `""` | Step-by-step reproduction instructions. |
  | `affected_files` | `array[str]` | No | `[]` | List of affected source file paths. |
  | `diagnosis` | `string` | No | `""` | Root cause analysis findings. |
- **Example Request**:
  ```json
  {
    "tool": "bug_create",
    "params": {
      "project_id": "proj_home_projects_a783bd",
      "title": "WebSocket disconnects after 60s idle",
      "severity": "high",
      "reproduction_steps": "Leave dashboard open on mobile for 1 minute without interaction.",
      "affected_files": ["src/api/websocket.ts"]
    }
  }
  ```

#### 12. `bug_update`
- **Description**: Updates diagnosis, reproduction steps, severity, or verification state of a bug.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `bug_id` | `string` | **Yes** | — | Bug ID (e.g. `bug_05ac1b64f8`). |
  | *(all other fields)* | `any` | No | — | Fields to update (`diagnosis`, `severity`, `verification_status`, etc.). |

#### 13. `bug_resolve`
- **Description**: Records the final fix and resolution text, updating status to `verified_fixed`.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `bug_id` | `string` | **Yes** | — | Bug ID. |
  | `resolution` | `string` | No | `""` | Explanation of fix delivered. |
  | `verified` | `boolean` | No | `false` | If `true`, status becomes `verified_fixed`; if `false`, `fix_in_progress`. |
- **Example Request**:
  ```json
  {
    "tool": "bug_resolve",
    "params": {
      "bug_id": "bug_05ac1b64f8",
      "resolution": "Configured heartbeat ping/pong keepalive every 25s.",
      "verified": true
    }
  }
  ```

#### 14. `bug_list`
- **Description**: Queries bugs filtered by project, severity, or verification status.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `project_id` | `string` | No | `null` | Filter by project ID. |
  | `severity` | `string` | No | `null` | Filter by severity (`critical`, `high`, `medium`, `low`). |
  | `verification_status` | `string` | No | `null` | Filter by verification status. |
  | `limit` | `integer` | No | `100` | Maximum results. |

---

### Domain 5: Persistent Project Memory

#### 15. `memory_record`
- **Description**: Stores architectural decisions, technical lessons, bug gotchas, and patterns in persistent project memory.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `project_id` | `string` | **Yes** | — | Project ID. |
  | `title` | `string` | **Yes** | — | Memory title. |
  | `content` | `string` | **Yes** | — | Detailed technical explanation or decision rationale. |
  | `category` | `string` | No | `"general"` | One of: `architecture`, `decision`, `pattern`, `gotcha`, `lesson`, `dependency`, `config`, `general`. |
  | `source` | `string` | No | `"user"` | `user`, `agent`, `audit`, `code_review`. |
  | `confidence` | `string` | No | `"verified"` | `suspected`, `tentative`, `verified`, `authoritative`. |
- **Example Request**:
  ```json
  {
    "tool": "memory_record",
    "params": {
      "project_id": "proj_home_projects_a783bd",
      "title": "Vite HMR WebSocket Port",
      "content": "On Android Termux, Vite HMR requires clientPort matching serverPort due to tunnel forwarding.",
      "category": "gotcha",
      "confidence": "verified"
    }
  }
  ```

#### 16. `memory_search`
- **Description**: Performs keyword search and category filtering over the project's persistent knowledge base.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `project_id` | `string` | **Yes** | — | Project ID. |
  | `query` | `string` | No | `null` | Keyword query string (matches title and content). |
  | `category` | `string` | No | `null` | Category filter. |
  | `limit` | `integer` | No | `50` | Maximum memories to return. |
- **Example Request**:
  ```json
  {
    "tool": "memory_search",
    "params": {
      "project_id": "proj_home_projects_a783bd",
      "query": "WebSocket HMR"
    }
  }
  ```

---

### Domain 6: Git Operations

#### 17. `git_status`
- **Description**: Returns detailed Git status: current branch, commit hash, modified files count, untracked files count, and clean flag.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `project_id` | `string` | No | Active project | Target project ID. |
- **Example Request**:
  ```json
  {
    "tool": "git_status",
    "params": { "project_id": "proj_home_projects_a783bd" }
  }
  ```
- **Example Response Data**:
  ```json
  {
    "is_git": true,
    "branch": "main",
    "commit_hash": "a1b2c3d4e5f6",
    "modified_count": 0,
    "untracked_count": 0,
    "has_remote": true,
    "origin_url": "git@github.com:Shaheemp76m/geothermal-plant.git",
    "is_clean": true,
    "status_summary": "clean"
  }
  ```

#### 18. `git_commits`
- **Description**: Returns recent Git commit history with author, date, and commit message.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `project_id` | `string` | No | Active project | Target project ID. |
  | `count` | `integer` | No | `10` | Number of recent commits to retrieve. |

#### 19. `git_diff`
- **Description**: Returns working tree diff or staged diff for the project.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `project_id` | `string` | No | Active project | Target project ID. |
  | `staged` | `boolean` | No | `false` | If `true`, returns `git diff --cached`; if `false`, unstaged diff. |

---

### Domain 7: Filesystem Operations

#### 20. `file_read`
- **Description**: Safely reads file contents strictly within the project directory boundary. Traversal attempts (`../`) are detected and blocked.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `path` | `string` | **Yes** | — | File path relative to project root (e.g. `package.json` or `src/App.tsx`). |
  | `project_id` | `string` | No | Active project | Target project ID. |
- **Example Request**:
  ```json
  {
    "tool": "file_read",
    "params": {
      "project_id": "proj_home_projects_a783bd",
      "path": "package.json"
    }
  }
  ```
- **Example Response Data**:
  ```json
  {
    "content": "{\n  \"name\": \"geothermal-plant\",\n  \"version\": \"1.0.0\" ...\n}"
  }
  ```

---

### Domain 8: Context & Project Comparison

#### 21. `project_context` *(Alias: `project_brief`)*
- **Description**: Generates an optimized, dense Markdown briefing containing active project details, Git status, blockers, recent tasks, and memories — designed directly for AI Agent context injection.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `project_id` | `string` | No | Active project | Target project ID. |
- **Example Request**:
  ```json
  {
    "tool": "project_context",
    "params": { "project_id": "proj_home_projects_a783bd" }
  }
  ```
- **Example Response Data**:
  ```json
  {
    "context": "# Context Briefing: Home Projects\n- **Path**: /data/data/com.termux/files/home/projects\n- **Stack**: Node.js, React, TailwindCSS, TypeScript, Vite\n- **Branch**: main (Clean)\n- **Active Blockers**: 1\n- **Recent Decisions**: SQLite WAL mode enabled"
  }
  ```

#### 22. `project_compare` *(Alias: `projects_compare`)*
- **Description**: Produces side-by-side comparative analytics for multiple projects (tech stack, task counts, blockers, bug count, Git status).
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `project_ids` | `array[str]` | No | All registered projects | List of project IDs to compare. |

---

### Domain 9: Antigravity Execution

#### 23. `agy_execute`
- **Description**: Invokes Antigravity CLI (`agy -p ...`) in the project directory, capturing execution logs, token metrics, and exit status.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `prompt` | `string` | **Yes** | — | Specific development instruction for the AI agent (e.g., "Implement unit test for poller.ts"). |
  | `project_id` | `string` | No | Active project | Target project ID. |
  | `model` | `string` | No | System active model | Override AI model ID (e.g. `gemini-3.8-flash-high`). |
  | `timeout` | `integer` | No | `300` | Process execution timeout in seconds. |
  | `mode` | `string` | No | `null` | Execution mode (e.g. `autonomous`, `plan`). |
  | `action` | `string` | No | `"execute"` | Action classification. |
  | `async` | `boolean` | No | `false` | If `true`, returns immediately with queued `job_id`; if `false`, waits for completion. |
- **Example Request**:
  ```json
  {
    "tool": "agy_execute",
    "params": {
      "project_id": "proj_home_projects_a783bd",
      "prompt": "Run npm test and report any failing suites",
      "timeout": 120
    }
  }
  ```
- **Example Response Data**:
  ```json
  {
    "id": "job_e567a898bd30",
    "project_id": "proj_home_projects_a783bd",
    "action": "execute",
    "prompt": "Run npm test and report any failing suites",
    "model": "gemini-3.8-flash-high",
    "status": "completed",
    "exit_code": 0,
    "duration_seconds": 4.2,
    "stdout": "PASS src/tests/poller.test.ts (2 passed)",
    "stderr": "",
    "token_usage": { "input_tokens": 150, "output_tokens": 45, "total_tokens": 195 }
  }
  ```

---

### Domain 10: Model Management

#### 24. `agy_models_list`
- **Description**: Queries Antigravity CLI for verified available model families and reports the currently active model.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: None required (`params: {}`).
- **Example Response Data**:
  ```json
  {
    "models": [
      { "id": "gemini-3.8-flash-high", "name": "Gemini 3.8 Flash (High)", "family": "Gemini" },
      { "id": "gemini-3.8-flash-medium", "name": "Gemini 3.8 Flash (Medium)", "family": "Gemini" },
      { "id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6 (Thinking)", "family": "Claude" }
    ],
    "active_model": {
      "id": "gemini-3.8-flash-high",
      "name": "Gemini 3.8 Flash (High)",
      "family": "Gemini"
    }
  }
  ```

#### 25. `agy_model_switch`
- **Description**: Switches the active AI model used by Antigravity CLI across subsequent executions.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `model` | `string` | **Yes** | — | Target model ID (e.g. `gemini-3.8-flash-high`). |
- **Example Request**:
  ```json
  {
    "tool": "agy_model_switch",
    "params": { "model": "gemini-3.8-flash-high" }
  }
  ```

---

### Domain 11: Usage Monitoring

#### 26. `agy_usage_summary`
- **Description**: Returns local execution token metrics and reports honest account quota support status.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**: None required (`params: {}`).
- **Example Response Data**:
  ```json
  {
    "local_session_usage": {
      "status": "supported",
      "total_tokens_consumed": 2840,
      "total_execution_jobs": 12
    },
    "account_quota": {
      "status": "unsupported",
      "reason": "Antigravity CLI does not expose account-level cloud billing quota via local CLI."
    }
  }
  ```

---

### Domain 12: Asynchronous Background Job Execution

#### 27. `job_start`
- **Description**: Spawns a long-running command (e.g. `npm run build`, `npm install`, `pytest`, compilation scripts) as an isolated, detached background process and returns immediately with a unique `job_id`. Output is streamed continuously to disk (`data/jobs/{job_id}.log`).
- **Risk Level**: `LOW` (Autonomous for standard dev commands; destructive root commands prohibited)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `command` | `string` or `array[str]` | **Yes** | — | Command to execute (e.g. `"npm run build"`, `["npm", "install"]`). |
  | `project_id` | `string` | No | Active project | Target registered project ID. |
  | `cwd` | `string` | No | Project root | Relative sub-path within project boundaries. |
  | `timeout` | `integer` | No | Auto (30m builds/installs, 10m tests, 5m default) | Process timeout in seconds. |
  | `action` | `string` | No | `"command"` | Semantic classification (`build`, `install`, `test`, `command`). |
  | `telegram_chat_id` | `string` | No | Auto from session | Telegram Chat ID to notify upon background completion. |
- **Example Request**:
  ```json
  {
    "action": "job_start",
    "params": {
      "command": "npm run build",
      "project_id": "proj_home_projects_a783bd",
      "action": "build"
    }
  }
  ```
- **Example Response Data**:
  ```json
  {
    "job_id": "job_9e54c6a1a5f1",
    "status": "running",
    "command": "npm run build",
    "project_id": "proj_home_projects_a783bd",
    "working_directory": "/data/data/com.termux/files/home/projects",
    "started_at": "2026-11-14T12:44:00+00:00",
    "timeout_seconds": 1800,
    "log_file": "/data/data/com.termux/files/home/aegis-intelligence/data/jobs/job_9e54c6a1a5f1.log",
    "message": "Command started in background as job 'job_9e54c6a1a5f1' (PID: 12084)."
  }
  ```

#### 28. `job_get`
- **Description**: Retrieves live status, start/finish timestamps, duration, exit code, and output preview for a specific job ID.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `job_id` | `string` | **Yes** | — | Target job ID (e.g. `job_9e54c6a1a5f1`). |
- **Example Request**:
  ```json
  {
    "action": "job_get",
    "params": { "job_id": "job_9e54c6a1a5f1" }
  }
  ```

#### 29. `job_list`
- **Description**: Lists recent execution jobs with optional filtering by project ID or status.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `project_id` | `string` | No | All projects | Filter by registered project ID. |
  | `status` | `string` | No | All statuses | Filter by status (`queued`, `running`, `completed`, `failed`, `timed_out`, `cancelled`). |
  | `limit` | `integer` | No | `25` | Max number of records to return. |

#### 30. `job_logs`
- **Description**: Extracts trailing or leading stdout/stderr log lines from disk for an active or completed background job.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `job_id` | `string` | **Yes** | — | Target job ID. |
  | `lines` | `integer` | No | `50` | Number of lines to extract. |
  | `tail` | `boolean` | No | `true` | Extract from end (`true`) or beginning (`false`). |

#### 31. `job_cancel`
- **Description**: Cancels a running background job by cleanly terminating its process group (`SIGTERM` -> `SIGKILL`).
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `job_id` | `string` | **Yes** | — | Target job ID to terminate. |

---

### Domain 13: Approval & Audit Management

#### 27. `approval_list`
- **Description**: Lists recent approval requests with current status (`PENDING`, `APPROVED`, `REJECTED`, `CONSUMED`, `EXPIRED`).
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `status` | `string` | No | `null` | Filter by status (`PENDING`, `APPROVED`, `REJECTED`, etc.). |
- **Example Request**:
  ```json
  {
    "tool": "approval_list",
    "params": { "status": "PENDING" }
  }
  ```

#### 28. `approval_decide`
- **Description**: Records a user approval decision (`APPROVED` or `REJECTED`) for a pending gate request.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `approval_id` | `string` | **Yes** | — | Approval ID (e.g. `appr_1de25269eff1`). |
  | `decision` | `string` | **Yes** | — | `"APPROVED"` or `"REJECTED"`. |
  | `reason` | `string` | No | `""` | Optional rationale for the decision. |
  | `actor` | `string` | No | `"telegram_user"` | Identifier of deciding entity. |
- **Example Request**:
  ```json
  {
    "tool": "approval_decide",
    "params": {
      "approval_id": "appr_1de25269eff1",
      "decision": "APPROVED",
      "reason": "Confirmed deletion of test directory via Telegram button"
    }
  }
  ```

#### 29. `audit_logs_get`
- **Description**: Retrieves recent security and audit trail log entries from SQLite.
- **Risk Level**: `LOW` (Autonomous)
- **Parameters**:
  | Parameter | Type | Required | Default | Description |
  |---|---|---|---|---|
  | `limit` | `integer` | No | `50` | Maximum log records to return. |
  | `action` | `string` | No | `null` | Filter by action (e.g. `AUTH_FAILED`, `PROJECT_REGISTERED`, `APPROVAL_REQUESTED`). |
- **Example Request**:
  ```json
  {
    "tool": "audit_logs_get",
    "params": { "limit": 10 }
  }
  ```

---

## 3. Security Verification & Autonomy Architecture

Aegis Intelligence enforces multi-layered defense-in-depth across every dispatched tool call:

```
Tool Dispatch Security Pipeline:
1. Localhost Enforcement  ──► IP check: client must be 127.0.0.1 / ::1
2. Auth Header Check     ──► X-Aegis-Token / Bearer via constant-time hmac.compare_digest
3. Payload Validation    ──► Content-Length max limit + strict JSON schema type guards
4. PermissionManager     ──► Risk classification: LOW (Autonomous) vs CRITICAL (Approval Gate)
5. Path Canonicalization ──► Symlink resolution + validate_path_within_project
6. Single-Use Replay Pre ──► Approval token atomically marked used=1 on verification
7. Audit Trail           ──► Operation logged to SQLite + audit.log with secret redaction
```

### Risk Classification Matrix

| Action Pattern | Risk Level | Autonomy Rule | Gating Rationale |
|---|---|---|---|
| `project_list`, `project_inspect`, `report_generate`, `file_read`, `git_status`, `git_commits`, `git_diff`, `task_list`, `bug_list`, `memory_search`, `agy_models_list`, `agy_usage_summary` | `LOW` | **Autonomous** | Read-only inspection; non-destructive. |
| `task_create`, `task_update`, `task_complete`, `bug_create`, `bug_update`, `bug_resolve`, `memory_record`, `project_set_active`, `agy_model_switch` | `LOW` | **Autonomous** | Standard operational metadata creation within project boundary. |
| `agy_execute` | `LOW` | **Autonomous** | Sandboxed execution through Antigravity CLI in verified project workspace. |
| `bulk_file_delete` (>3 files) | `HIGH` | **Gate Required** | High-volume deletions trigger explicit approval confirmation. |
| `delete_project_dir`, `delete_project_files` | `CRITICAL` | **Gate Required** | Destructive directory removal is strictly gated. |
| `git_command` (`push --force`, `reset --hard`, `clean -fdx`) | `CRITICAL` | **Gate Required** | Destructive Git commands that overwrite remote history or wipe uncommitted files. |
| Out-of-bounds target (`is_out_of_bounds: true`) | `CRITICAL` | **Gate Required** | Attempting to operate outside the registered project root directory. |
| System package installation (`apt_install`, `pkg_install`) | `HIGH` | **Gate Required** | Modifying host OS environment requires human authorization. |
| n8n tampering (`modify_n8n`, `edit_n8n_config`) | `CRITICAL` | **Gate Required** | AI is prohibited from autonomously altering its own workflow automation engine. |

### Security Guarantees
1. **Path Traversal Immunity**: `validate_path_within_project` strictly canonicalizes targets using `os.path.realpath` and verifies that the target path starts with `project_root + os.sep`. Forbidden root paths (`/`, `/proc`, `/sys`, `/data/data/com.termux/files/usr/bin`) are hard-blocked from registration.
2. **Shell Injection Defense**: Process execution in `safe_run_command` uses array argument passing (`["git", "status"]`) with `shell=False`. Metacharacters (`;`, `&&`, `|`, `$()`) are passed as literal strings to `execve` and never evaluated by a shell.
3. **Single-Use Approval Guarantee**: When an approval is consumed, `verify_and_consume_approval` marks `used = 1` in an atomic SQLite transaction. Any attempt to replay the same approval token fails immediately.
4. **Approval Expiration**: Approvals expire after 900 seconds (15 minutes). Expired approvals cannot be approved or consumed.
5. **Secret Redaction**: Regex sanitizers automatically strip API tokens (`AIzaSy...`, `sk-...`, `Bearer ...`) from all audit logs and error messages before output.
6. **Alias Normalization**: `ToolRouter` and `PermissionManager` normalize casing and whitespace (`tool.lower().strip()`). Unauthorized action names cannot bypass the gate because unrecognized actions default to requiring review or trigger a strict 400 rejection.

---

## 4. n8n Integration Specification for Gemini AI Agent

To expose the complete Aegis capability set to your existing Gemini AI Agent in n8n, configure an **HTTP Request Tool** attached to the **AI Agent** node.

### Recommended n8n Node Setup

```
[ Telegram Trigger Node ]
           │
           ▼
[ n8n AI Agent Node ] ◄── (Model: Google Gemini Chat Model)
           │
           ├── Custom Tool: aegis_dispatch (HTTP Request Tool)
           │
           ▼
[ Telegram Send Message Node ]
```

---

### Pattern 1: Unified Single-Tool Configuration (Recommended)

In this pattern, a single flexible tool is exposed to Gemini. Gemini uses its reasoning capability to choose the right action and assemble the parameters.

#### 1. n8n HTTP Request Tool Settings:
- **Tool Name**: `aegis_dispatch`
- **Tool Description**:
  ```text
  Execute Aegis Intelligence operations on the local Termux development environment.
  Supported tools across 12 domains:
  1. Projects:
     - project_assessment: Comprehensive single-call technical assessment (metadata, git, tasks, bugs, memory, files, health). Replaces multiple tool calls. Params: { "project_id": "string", "sections": ["git", "tasks", "bugs"] }
     - project_list: List all registered software projects.
     - project_get: Get full project details by ID. Params: { "project_id": "string" }
     - project_update: Update project metadata. Params: { "project_id": "string", "name": "...", "description": "..." }
     - project_delete: Unregister project from DB (gated, requires approval). Params: { "project_id": "string" }
     - project_register: Register a new project folder. Params: { "name": "string", "path": "string" }
     - project_inspect: Inspect active project Git status, files, and tech stack. Params: { "project_id": "string" }
     - project_context: Get dense markdown briefing for project. Params: { "project_id": "string" }
     - project_compare: Compare 2+ projects side-by-side. Params: { "project_ids": ["..."] }
     - project_set_active: Switch active project. Params: { "project_id": "string" }
  2. Health & Diagnostics:
     - system_health: Check database connectivity and daemon status.
     - development_health: Verified facts vs. inferences project health scan. Params: { "project_id": "string", "execute_tests": false }
     - report_generate: Generate dev reports (status, daily, weekly, tasks, bugs, git, health). Params: { "report_type": "string", "project_id": "string" }
  3. Tasks:
     - task_list: List tasks. Params: { "project_id": "string", "status": "pending|in_progress|blocked|completed", "priority": "high|critical" }
     - task_get: Get single task by ID. Params: { "task_id": "string" }
     - task_create: Create task. Params: { "project_id": "string", "title": "string", "priority": "medium|high|critical" }
     - task_update: Update task. Params: { "task_id": "string", "status": "...", "notes": "..." }
     - task_complete: Complete task. Params: { "task_id": "string", "notes": "..." }
     - task_delete: Delete task by ID. Params: { "task_id": "string" }
     - task_summary: Get task metrics and blockers. Params: { "project_id": "string" }
     - task_overdue: List overdue tasks. Params: { "project_id": "string" }
  4. Bugs:
     - bug_list: List bugs. Params: { "project_id": "string", "severity": "...", "verification_status": "..." }
     - bug_get: Get single bug by ID. Params: { "bug_id": "string" }
     - bug_create: Report bug. Params: { "project_id": "string", "title": "string", "severity": "high", "reproduction_steps": "..." }
     - bug_update: Update bug. Params: { "bug_id": "string", "diagnosis": "...", "severity": "..." }
     - bug_resolve: Mark bug fixed. Params: { "bug_id": "string", "resolution": "...", "verified": true }
     - bug_delete: Delete bug by ID. Params: { "bug_id": "string" }
     - bug_summary: Bug counts and unresolved criticals. Params: { "project_id": "string" }
  5. Persistent Memory:
     - memory_search: Search project knowledge. Params: { "project_id": "string", "query": "string" }
     - memory_get: Get single memory entry by ID. Params: { "memory_id": "string" }
     - memory_record: Save architecture decision. Params: { "project_id": "string", "title": "string", "content": "string", "category": "architecture" }
     - memory_update: Update memory entry. Params: { "memory_id": "string", "content": "...", "confidence": "verified" }
     - memory_delete: Delete memory by ID. Params: { "memory_id": "string" }
  6. Git:
     - git_status: Check git working tree. Params: { "project_id": "string" }
     - git_commits: Recent commits. Params: { "project_id": "string", "count": 10 }
     - git_diff: Working tree diff. Params: { "project_id": "string", "staged": false }
     - git_contributors: List contributors and commit counts. Params: { "project_id": "string" }
  7. Filesystem:
     - file_read: Read file safely within project. Params: { "project_id": "string", "path": "relative/file/path" }
     - filesystem_inspect: Scan directory tree safely. Params: { "project_id": "string", "max_depth": 3 }
     - filesystem_recent_files: Top recently modified files. Params: { "project_id": "string", "limit": 15 }
  8. Background Jobs & Execution:
     - job_start: Launch asynchronous long-running command (build, test, install). Params: { "command": "string", "project_id": "string", "cwd": "string", "timeout": 1800 }
     - job_get: Poll job status, exit code, and duration by ID. Params: { "job_id": "string" }
     - job_list: List execution jobs with optional status filter. Params: { "project_id": "string", "status": "running|completed|failed", "limit": 25 }
     - job_logs: Extract stdout/stderr log lines from disk. Params: { "job_id": "string", "lines": 50, "tail": true }
     - job_cancel: Cancel running job process group. Params: { "job_id": "string" }
     - agy_models_list: List Antigravity AI models.
     - agy_model_switch: Switch model. Params: { "model": "gemini-3.8-flash-high" }
     - agy_usage_summary: Get token usage metrics.
     - agy_execute: Run development coding task in Antigravity CLI. Params: { "project_id": "string", "prompt": "string" }
  9. Approvals & Auditing:
     - approval_list: List pending approvals.
     - approval_get: Get single approval by ID. Params: { "approval_id": "string" }
     - approval_decide: Approve/Reject. Params: { "approval_id": "string", "decision": "APPROVED|REJECTED" }
     - audit_logs_get: Get audit trail. Params: { "limit": 10 }
  ```
- **Method**: `POST`
- **URL**: `http://127.0.0.1:8765/api/v1/tools/dispatch`
- **Authentication**: `Generic Credential Type` -> `Header Auth`
  - **Header Name**: `X-Aegis-Token`
  - **Header Value**: `<token_from_data/.api_token>`
- **Headers to Send**:
  - `Content-Type`: `application/json`
- **Send Body**: `true`
- **Body Content Type**: `JSON`
- **Specify Body**: `Using JSON`
  ```json
  {
    "tool": "={{ $fromAI('tool', 'The Aegis tool name, e.g., task_list, project_inspect, git_status') }}",
    "params": "={{ $fromAI('params', 'A valid JSON object of parameters for the tool') }}",
    "approval_id": "={{ $fromAI('approval_id', 'Approval ID if re-executing an approved action, otherwise null') }}"
  }
  ```

---

### Telegram Interactive Approval Gate Workflow in n8n

When a tool call requires explicit approval, Aegis returns `HTTP 403` with code `APPROVAL_REQUIRED`.

```
                  ┌───────────────────────────────┐
                  │ 1. AI Agent executes tool     │
                  └───────────────┬───────────────┘
                                  │ POST /api/v1/tools/dispatch
                                  ▼
                  ┌───────────────────────────────┐
                  │ 2. Aegis returns HTTP 403     │
                  │    code: APPROVAL_REQUIRED    │
                  │    approval_id: appr_xxx      │
                  └───────────────┬───────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. n8n sends interactive Telegram message with Inline Keyboard: │
│                                                                 │
│    ⚠️ Approval Required [CRITICAL]                             │
│    Action: project_delete                                       │
│    Reason: Deleting or unregistering a project requires approval│
│                                                                 │
│    [ ✅ Approve (appr_xxx) ]    [ ❌ Reject (appr_xxx) ]         │
└─────────────────────────────────┬───────────────────────────────┘
                                  │ User taps button
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. Telegram Webhook Trigger in n8n receives callback query      │
│    Calls POST /api/v1/approvals/appr_xxx/decision               │
│    { "decision": "APPROVED", "reason": "Confirmed via Telegram" }│
└─────────────────────────────────┬───────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. n8n re-dispatches original tool with approval token:         │
│    POST /api/v1/tools/dispatch                                  │
│    { "tool": "project_delete", "approval_id": "appr_xxx" }      │
│    ──► Aegis consumes approval (used=1) and executes cleanly!   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Coverage Status & Completed Implementation

All previously identified gaps between `api/routes.py`, underlying intelligence modules, and `core/tool_router.py` have been resolved:

| Capability | Action Name | Risk Level | Status |
|---|---|:---:|:---:|
| **Get Project by ID** | `project_get` | `LOW` | **IMPLEMENTED** ✅ |
| **Update Project Metadata** | `project_update` | `LOW` | **IMPLEMENTED** ✅ |
| **Delete / Unregister Project** | `project_delete` | `CRITICAL` (Gated) | **IMPLEMENTED** ✅ |
| **Get Task by ID** | `task_get` | `LOW` | **IMPLEMENTED** ✅ |
| **Delete Task** | `task_delete` | `MEDIUM` | **IMPLEMENTED** ✅ |
| **Overdue Tasks Query** | `task_overdue` | `LOW` | **IMPLEMENTED** ✅ |
| **Get Bug by ID** | `bug_get` | `LOW` | **IMPLEMENTED** ✅ |
| **Delete Bug Record** | `bug_delete` | `MEDIUM` | **IMPLEMENTED** ✅ |
| **Bug Statistical Summary** | `bug_summary` | `LOW` | **IMPLEMENTED** ✅ |
| **Get Memory Entry** | `memory_get` | `LOW` | **IMPLEMENTED** ✅ |
| **Update Memory Entry** | `memory_update` | `LOW` | **IMPLEMENTED** ✅ |
| **Delete Memory Entry** | `memory_delete` | `MEDIUM` | **IMPLEMENTED** ✅ |
| **List Execution Jobs** | `job_list` | `LOW` | **IMPLEMENTED** ✅ |
| **Get Job Detail** | `job_get` | `LOW` | **IMPLEMENTED** ✅ |
| **Single Approval Detail** | `approval_get` | `LOW` | **IMPLEMENTED** ✅ |
| **Directory Tree Inspection** | `filesystem_inspect` | `LOW` | **IMPLEMENTED** ✅ |
| **Recently Modified Files** | `filesystem_recent_files` | `LOW` | **IMPLEMENTED** ✅ |
| **Git Contributors Breakdown** | `git_contributors` | `LOW` | **IMPLEMENTED** ✅ |
| **Empirical Health Scan** | `development_health` | `LOW` | **IMPLEMENTED** ✅ |
| **System Diagnostics** | `system_health` | `LOW` | **IMPLEMENTED** ✅ |
| **List Antigravity Instances** | `agy_instance_list` | `LOW` | **IMPLEMENTED** ✅ |
| **Get Instance Status** | `agy_instance_status` | `LOW` | **IMPLEMENTED** ✅ |
| **Start Antigravity Instance** | `agy_instance_start` | `LOW` | **IMPLEMENTED** ✅ |
| **Stop Antigravity Instance** | `agy_instance_stop` | `MEDIUM` | **IMPLEMENTED** ✅ |
| **Get Instance Output** | `agy_instance_output` | `LOW` | **IMPLEMENTED** ✅ |
| **Submit Antigravity Task** | `agy_task_submit` | `LOW` | **IMPLEMENTED** ✅ |
| **Get Task Status** | `agy_task_status` | `LOW` | **IMPLEMENTED** ✅ |
| **Alias Normalization** | `ALIAS_MAP` (50+ aliases) | `LOW` | **IMPLEMENTED** ✅ |

---

## 6. Verification and Guarantees

- **100% REST-to-Dispatcher Parity**: Every viable REST endpoint (and all underlying domain capabilities) can be called via `POST /api/v1/tools/dispatch`.
- **Zero Bypass of Security Boundaries**: Mandatory approval gates apply uniformly whether operations are invoked via REST or dispatcher.
- **Bidirectional Alias Resilience**: Agents can call `task_list` or `list_tasks`, `inspect_project` or `project_inspect`, with zero routing failures.

---

## 7. Execution Ledger & Agent Loop Safeguards

To prevent infinite tool execution loops, duplicate token consumption, and agent stalls (such as calling `project_list` 10 consecutive times), Aegis implements an automated **Execution Ledger** directly in SQLite:

### Architectural Features:
1. **Deterministic Action Signing**: Every tool invocation is hashed using SHA256 over its canonical action name and normalized parameter dictionary.
2. **Read-Only Short-Circuiting**: If an identical read-only action has already completed successfully within the same `execution_id`, Aegis immediately returns the cached result without querying the database or filesystem again.
3. **Stagnation Break**: If an agent repeats an identical action more than `LEDGER_MAX_REPEATED_ACTIONS` (default: 2) times, Aegis halts the tool execution cleanly and returns:
   ```json
   {
     "status": "STAGNATION_DETECTED",
     "halted": true,
     "limit_type": "max_repeated_actions",
     "action": "project_list",
     "execution_id": "...",
     "attempt_count": 3,
     "message": "Repeated action limit reached (action 'project_list' repeated 3 times). Execution halted to prevent infinite loop. Synthesize your final answer now without invoking further tools.",
     "cached_data": [...]
   }
   ```
4. **Configurable Execution Limits**:
   - `LEDGER_MAX_TOTAL_ACTIONS`: Default 15 total tool actions per execution.
   - `LEDGER_MAX_CONSECUTIVE_FAILURES`: Default 3 consecutive failures before halting.
   - `LEDGER_EXECUTION_TIMEOUT`: Default 60 seconds per execution cycle.
5. **Execution Progress Tool**: Agents and orchestrators can check progress anytime via `execution_progress`:
   ```json
   {
     "tool": "execution_progress",
     "params": { "execution_id": "sess_xxx_123" }
   }
   ```

---

## 12. Centralized Skill System Tools

Aegis provides on-demand skill discovery, intelligent multi-factor selection, and workspace activation across the 307-skill library:

### 12.1 `skill_search`
Search lightweight catalog metadata by keywords, categories, or target agent.
- **Parameters**:
  - `query` (string, required): Search query or keywords.
  - `category` (string, optional): Filter by category (e.g. `development`, `security`, `testing`, `architecture`).
  - `agent_id` (string, optional): Filter or boost by target agent (e.g. `aegis-ciso`, `aegis-repair-engineer`).
  - `limit` (integer, optional, default: 10): Maximum results to return.

### 12.2 `skill_select`
Intelligently evaluate and select the smallest useful set of skills (1–3 skills) for a task and agent using the 7 selection criteria (task relevance, agent affinity, tech stack compatibility, Termux feasibility, overlap pruning).
- **Parameters**:
  - `task` (string, required): Task description or developer request.
  - `agent_id` (string, optional, default: `'aegis-orchestrator'`): Target agent executing the task.
  - `tech_stack` (list of strings, optional): Project languages and frameworks (e.g. `["FastAPI", "Python"]`).
  - `max_skills` (integer, optional, default: 3): Upper bound on selected skills.

### 12.3 `skill_inspect`
Inspect full metadata, vaulted instructions preview, and security audit report for a specific skill.
- **Parameters**:
  - `skill_id` (string, required): Unique skill identifier (e.g. `'fastapi-pro'`, `'security-auditor'`).

### 12.4 `skill_activate`
Activate a vetted skill for a project workspace by creating `.agents/skills/<skill_id>/SKILL.md`.
- **Parameters**:
  - `skill_id` (string, required): Unique skill identifier to activate.
  - `project_id` or `workspace_path` (string, required): Target registered project or directory.

