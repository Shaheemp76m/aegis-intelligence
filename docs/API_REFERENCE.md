# Aegis Intelligence — Complete REST API Reference

**Document Version**: 2.0.0  
**Base URL**: `http://127.0.0.1:8765`  
**Protocol**: HTTP/1.1 REST (JSON)  
**Authentication**: Header Auth (`X-Aegis-Token` or `Authorization: Bearer <token>`)

---

## 1. Global Conventions

### Response Envelope
All HTTP endpoints return a consistent four-field JSON envelope:

#### Success (`HTTP 200` / `HTTP 201`)
```json
{
  "success": true,
  "request_id": "req_8af19ff9aa4e",
  "data": { ... },
  "error": null
}
```

#### Error (`HTTP 400`, `HTTP 401`, `HTTP 403`, `HTTP 404`, `HTTP 500`)
```json
{
  "success": false,
  "request_id": "req_8af19ff9aa4e",
  "data": null,
  "error": {
    "code": "NOT_FOUND | BAD_REQUEST | UNAUTHORIZED | FORBIDDEN | APPROVAL_REQUIRED",
    "message": "Human-readable description of error"
  }
}
```

#### Approval Gate Error (`HTTP 403`)
```json
{
  "success": false,
  "request_id": "req_b2e48ea5978e",
  "data": null,
  "error": {
    "code": "APPROVAL_REQUIRED",
    "message": "Operation requires approval [CRITICAL]: Deleting or unregistering a project requires explicit confirmation. (Approval ID: appr_a808bebc4cf1)"
  }
}
```

---

## 2. System Endpoints

### `GET /health`
- **Auth**: None (Public)
- **Description**: Returns daemon status, service version, and SQLite connectivity.
- **Response `200`**:
  ```json
  {
    "status": "healthy",
    "service": "aegis-intelligence",
    "version": "1.0.0",
    "database": "connected",
    "host": "127.0.0.1",
    "port": 8765
  }
  ```

### `GET /openapi.json`
- **Auth**: None (Public)
- **Description**: Returns the OpenAPI 3.0 specification document.

---

## 3. Project Management Endpoints

### `GET /api/v1/projects`
- **Auth**: Required
- **Description**: Lists all registered software projects with aggregated counts.
- **Response `200`**: Array of project objects.

### `POST /api/v1/projects`
- **Auth**: Required
- **Description**: Registers a new project directory after validating path safety.
- **Request Body**:
  ```json
  {
    "name": "Project Name (required)",
    "path": "/absolute/path/to/project (required)",
    "description": "Optional description",
    "project_id": "optional_custom_id"
  }
  ```
- **Response `201`**: Registered project record.

### `POST /api/v1/projects/compare`
- **Auth**: Required
- **Description**: Compares Git state, tech stack, tasks, and bugs across multiple projects.
- **Request Body**: `{"project_ids": ["proj_1", "proj_2"]}` (optional; defaults to all projects).

### `GET /api/v1/projects/{project_id}`
- **Auth**: Required
- **Description**: Retrieves full metadata and aggregate task/bug/memory counts for a specific project.

### `PUT /api/v1/projects/{project_id}`
- **Auth**: Required
- **Description**: Updates display name, description, or status of a project.
- **Request Body**: `{"name": "...", "description": "...", "status": "active|archived"}`.

### `DELETE /api/v1/projects/{project_id}`
- **Auth**: Required (Gated via Dispatcher)
- **Description**: Unregisters project from database. Physical files on disk are strictly preserved.

### `POST /api/v1/projects/{project_id}/activate`
- **Auth**: Required
- **Description**: Sets a project as the currently active project for default parameter fallbacks.

### `POST /api/v1/projects/{project_id}/inspect`
- **Auth**: Required
- **Description**: Runs deep inspection on Git status, commit history, file tree, and stack detection. Updates `last_inspected_at`.

### `GET /api/v1/projects/{project_id}/report`
- **Auth**: Required
- **Query Params**: `type=status|daily|weekly|tasks|bugs|git|health` (default: `status`).
- **Description**: Generates a formatted development report.

### `GET /api/v1/projects/{project_id}/context`
- **Auth**: Required
- **Description**: Generates dense Markdown context briefing designed for LLM prompts.

### `GET /api/v1/projects/{project_id}/assessment`
- **Auth**: Required
- **Query Params**:
  - `sections`: Comma-separated list (`project,git,tasks,bugs,memory,filesystem,health`). Defaults to all.
  - `execute_tests`: `true|false` (default: `false`).
- **Description**: Single-call composite read-only technical assessment.

---

## 4. Task Management Endpoints

### `GET /api/v1/projects/{project_id}/tasks`
- **Auth**: Required
- **Query Params**: `status=pending|in_progress|blocked|completed`, `priority=low|medium|high|critical`, `limit=100`.

### `POST /api/v1/projects/{project_id}/tasks`
- **Auth**: Required
- **Request Body**:
  ```json
  {
    "title": "Task title (required)",
    "description": "Optional details",
    "status": "pending (default)",
    "priority": "medium (default)",
    "due_date": "YYYY-MM-DD",
    "related_files": ["file.py"],
    "notes": "Optional notes"
  }
  ```

### `PUT /api/v1/projects/{project_id}/tasks/{task_id}`
- **Auth**: Required
- **Request Body**: Updatable fields (`title`, `description`, `status`, `priority`, `due_date`, `notes`, `related_files`).

### `DELETE /api/v1/projects/{project_id}/tasks/{task_id}`
- **Auth**: Required
- **Description**: Deletes task record from database.

---

## 5. Bug Tracking Endpoints

### `GET /api/v1/projects/{project_id}/bugs`
- **Auth**: Required
- **Query Params**: `severity=low|medium|high|critical`, `verification_status=unverified|reproducing|diagnosed|resolved|verified_fixed`.

### `POST /api/v1/projects/{project_id}/bugs`
- **Auth**: Required
- **Request Body**:
  ```json
  {
    "title": "Bug title (required)",
    "severity": "medium",
    "reproduction_steps": "Steps to reproduce",
    "affected_files": ["file.py"],
    "diagnosis": "Root cause notes",
    "verification_status": "unverified"
  }
  ```

### `PUT /api/v1/projects/{project_id}/bugs/{bug_id}`
- **Auth**: Required
- **Request Body**: Updatable defect fields (`title`, `severity`, `diagnosis`, `resolution`, `verification_status`).

---

## 6. Persistent Project Memory Endpoints

### `GET /api/v1/projects/{project_id}/memory`
- **Auth**: Required
- **Query Params**: `query=search+keywords`, `category=architecture|decision|general`, `limit=50`.

### `POST /api/v1/projects/{project_id}/memory`
- **Auth**: Required
- **Request Body**:
  ```json
  {
    "title": "Memory title (required)",
    "content": "Knowledge content (required)",
    "category": "architecture|decision|discussion|feature|issue|milestone|instruction|general",
    "source": "user|agent",
    "confidence": "verified|inferred|hypothesized"
  }
  ```

### `DELETE /api/v1/projects/{project_id}/memory/{memory_id}`
- **Auth**: Required
- **Description**: Deletes persistent memory entry.

---

## 7. Antigravity & Execution Endpoints

### `POST /api/v1/agy/execute`
- **Auth**: Required
- **Request Body**:
  ```json
  {
    "prompt": "Coding task instructions for Antigravity (required)",
    "project_id": "proj_xxxx (optional, defaults to active)",
    "model": "gemini-3.8-flash-high",
    "timeout": 120,
    "action": "execute|review|test",
    "async": false
  }
  ```

### `GET /api/v1/agy/models`
- **Auth**: Required
- **Description**: Lists supported models and active model.

### `POST /api/v1/agy/model/switch`
- **Auth**: Required
- **Request Body**: `{"model": "gemini-3.8-flash-high"}`.

### `GET /api/v1/agy/usage`
- **Auth**: Required
- **Description**: Returns token metrics for completed jobs and local session stats.

### `GET /api/v1/jobs`
- **Auth**: Required
- **Query Params**: `project_id=proj_xxxx`, `limit=25`.

### `GET /api/v1/jobs/{job_id}`
- **Auth**: Required
- **Description**: Returns execution output, stdout, stderr, exit code, and token metrics.

---

## 8. Approvals & Audit Endpoints

### `GET /api/v1/approvals`
- **Auth**: Required
- **Query Params**: `status=PENDING|APPROVED|REJECTED|EXPIRED`.

### `POST /api/v1/approvals/{approval_id}/decision`
- **Auth**: Required
- **Request Body**:
  ```json
  {
    "decision": "APPROVED | REJECTED",
    "reason": "Authorized via Telegram button",
    "actor": "telegram_user"
  }
  ```

### `GET /api/v1/audit/logs`
- **Auth**: Required
- **Query Params**: `limit=50`, `action=PROJECT_REGISTERED|AUTH_FAILED|...`.

---

## 9. Unified Tool Dispatcher Endpoint

### `POST /api/v1/tools/dispatch`
- **Auth**: Required
- **Description**: Single-entry tool dispatcher for AI Agents (n8n / Gemini / Antigravity). Exposes all 49 actions with automatic alias normalization and server-side safety checks.
- **Request Body**:
  ```json
  {
    "tool": "task_list",
    "params": {
      "project_id": "proj_home_projects_a783bd",
      "status": "pending"
    },
    "approval_id": null
  }
  ```
