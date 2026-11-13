# Aegis Intelligence - n8n & Telegram Integration Guide

This guide describes how to connect **Aegis Intelligence** to **n8n** running locally on Termux and control your software projects through a Telegram Bot powered by the **Gemini AI Agent**.

---

## 1. Architectural Architecture

```
[ Telegram User ]
       │
       ▼ (Webhook)
[ Cloudflare Tunnel / Termux ]
       │
       ▼
[ n8n Workflow on http://127.0.0.1:5678 ]
       │
       ├─► 1. Telegram Trigger Node
       ├─► 2. Telegram User ID Whitelist / Auth Switch
       ├─► 3. AI Agent Node (Reasoning: Google Gemini)
       │         │
       │         ├── Tool 1: Aegis Project List (HTTP Request)
       │         ├── Tool 2: Aegis Project Inspect (HTTP Request)
       │         ├── Tool 3: Aegis Task Manager (HTTP Request)
       │         ├── Tool 4: Aegis Memory Search (HTTP Request)
       │         ├── Tool 5: Aegis Development Reports (HTTP Request)
       │         ├── Tool 6: Aegis Antigravity Execute (HTTP Request)
       │         └── Tool 7: Aegis Approval Decision (HTTP Request)
       │
       ▼
[ Aegis Intelligence Daemon on http://127.0.0.1:8765 ]
       │
       ├─► SQLite Storage (~/aegis-intelligence/data/aegis.db)
       ├─► Git Repositories
       └─► Antigravity CLI ("agy -p ...")
```

---

## 2. Authentication Setup in n8n

Aegis Intelligence runs locally on `127.0.0.1:8765` and requires a Bearer token or `X-Aegis-Token` header.

### Create Credential in n8n:
1. In n8n, navigate to **Credentials** -> **New Credential**.
2. Select **Header Auth**.
3. Name: `Aegis Token Auth`.
4. Header Name: `X-Aegis-Token`.
5. Value: Your token from `~/aegis-intelligence/data/.api_token` (or configured in `AEGIS_API_TOKEN`).

---

## 3. Configuring n8n AI Agent Tools

In n8n, add an **AI Agent** node (set to *Tools Agent*) using the **Google Gemini Chat Model** sub-node.

Then attach **Custom Tool** nodes (using the **HTTP Request** tool):

### Tool 1: `aegis_inspect_project`
- **Description**: "Inspects a registered project's Git status, working tree changes, recent commits, and directory structure."
- **Method**: `POST`
- **URL**: `http://127.0.0.1:8765/api/v1/projects/{{ $fromAI("project_id", "The ID of the project to inspect") }}/inspect`
- **Authentication**: `Header Auth` (Aegis Token Auth)

### Tool 2: `aegis_generate_report`
- **Description**: "Generates a structured development report for Telegram. Types: status, daily, weekly, tasks, bugs, git, health, multi_project."
- **Method**: `GET`
- **URL**: `http://127.0.0.1:8765/api/v1/projects/{{ $fromAI("project_id", "Project ID") }}/report?type={{ $fromAI("report_type", "Report type: status, daily, weekly, tasks, bugs, git, health") }}`
- **Authentication**: `Header Auth` (Aegis Token Auth)

### Tool 3: `aegis_task_manager`
- **Description**: "Creates, updates, or lists persistent tasks for a project."
- **Method**: `POST`
- **URL**: `http://127.0.0.1:8765/api/v1/tools/dispatch`
- **Authentication**: `Header Auth` (Aegis Token Auth)
- **Body Parameters**:
  ```json
  {
    "tool": "task_create",
    "params": {
      "project_id": "={{ $fromAI('project_id') }}",
      "title": "={{ $fromAI('title') }}",
      "priority": "={{ $fromAI('priority', 'medium') }}",
      "status": "pending"
    }
  }
  ```

### Tool 4: `aegis_search_memory`
- **Description**: "Retrieves persistent project knowledge, architectural decisions, and previous execution summaries."
- **Method**: `GET`
- **URL**: `http://127.0.0.1:8765/api/v1/projects/{{ $fromAI("project_id") }}/memory?query={{ $fromAI("query") }}`
- **Authentication**: `Header Auth` (Aegis Token Auth)

### Tool 5: `aegis_execute_development`
- **Description**: "Delegates development, code changes, testing, or review work to the Antigravity CLI. Runs within the registered project directory."
- **Method**: `POST`
- **URL**: `http://127.0.0.1:8765/api/v1/agy/execute`
- **Authentication**: `Header Auth` (Aegis Token Auth)
- **Body Parameters**:
  ```json
  {
    "prompt": "={{ $fromAI('prompt', 'Specific development instructions for Antigravity') }}",
    "project_id": "={{ $fromAI('project_id', 'Registered project ID') }}",
    "model": "={{ $fromAI('model', 'gemini-3.8-flash-high') }}"
  }
  ```

---

## 4. The Telegram Approval Gate Flow

When an operation requires explicit approval (e.g., deleting directories, Git reset, force pushing):
1. Aegis rejects the initial execution with HTTP `403` and returns:
   ```json
   {
     "success": false,
     "error": {
       "code": "APPROVAL_REQUIRED",
       "message": "Operation requires approval [CRITICAL]: Git reset --hard destroys uncommitted changes. (Approval ID: appr_xxx)"
     }
   }
   ```
2. The Gemini Agent recognizes the `APPROVAL_REQUIRED` code and sends an interactive Telegram message with inline buttons:
   - `[ ✅ Approve appr_xxx ]`
   - `[ ❌ Reject appr_xxx ]`
3. When the user taps **Approve**:
   - Telegram sends callback query to n8n webhook.
   - n8n calls:
     ```http
     POST /api/v1/approvals/appr_xxx/decision
     Content-Type: application/json
     X-Aegis-Token: <token>

     {
       "decision": "APPROVED",
       "reason": "Authorized via Telegram button",
       "actor": "user_id_12345"
     }
     ```
   - Aegis marks the approval `APPROVED` with a 15-minute expiration.
   - The action is then re-executed with `"approval_id": "appr_xxx"`.
   - Aegis consumes the approval (single-use guarantee).
