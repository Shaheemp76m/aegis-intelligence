# Aegis Intelligence — n8n & Telegram Agent Integration Guide

**Document Version**: 2.0.0  
**n8n Target Version**: 2.47.4  
**Local n8n Address**: `http://127.0.0.1:5678`  
**Aegis Dispatcher**: `http://127.0.0.1:8765/api/v1/tools/dispatch`  
**Authentication**: Header Auth (`X-Aegis-Token`)

---

## 1. Architectural Architecture

```
[ Telegram User ]
       │
       ▼ (Webhook over HTTPS)
[ Cloudflare Tunnel Ingress ]
       │
       ▼ (Forwarded to local Node.js process)
[ n8n Instance on http://127.0.0.1:5678 ]
       │
       ├─► 1. Telegram Trigger Node
       ├─► 2. User ID Whitelist Filter (Security Check)
       ├─► 3. AI Agent Node (Tools Agent, Google Gemini LLM)
       │         │
       │         └── Tool: aegis_dispatch (HTTP Request Tool)
       │                  │
       │                  ▼ POST http://127.0.0.1:8765/api/v1/tools/dispatch
       │             [ Aegis Daemon ]
       │
       └─► 4. Telegram Send Message Node (Markdown Response)
```

---

## 2. Authentication Setup in n8n

1. In n8n, navigate to **Credentials** ➔ **New Credential**.
2. Select **Header Auth**.
3. Name: `Aegis Token Auth`.
4. Header Name: `X-Aegis-Token`.
5. Value: Your 48-character token from `~/aegis-intelligence/data/.api_token`.
6. Save the credential.

---

## 3. Configuring the Unified Dispatcher Tool (`aegis_dispatch`)

Instead of creating dozens of individual HTTP Request nodes, configure a single flexible **Custom Tool (HTTP Request)** attached to the **AI Agent** node:

- **Tool Name**: `aegis_dispatch`
- **Tool Description**:
  ```text
  Execute Aegis Intelligence operations on the local Termux development environment.
  Supported tools across 12 domains:
  1. Projects:
     - project_assessment: Comprehensive single-call technical assessment (metadata, git, tasks, bugs, memory, files, health). PREFER THIS when the user asks for a general project overview or status update. Params: { "project_id": "string", "sections": ["git", "tasks", "bugs"] }
     - project_list: List all registered software projects.
     - project_get: Get full project details by ID. Params: { "project_id": "string" }
     - project_update: Update project metadata. Params: { "project_id": "string", "name": "...", "description": "..." }
     - project_delete: Unregister project from DB (gated, requires approval). Params: { "project_id": "string" }
     - project_inspect: Deep inspect Git, tree, and stack. Params: { "project_id": "string" }
     - project_context: Get dense markdown briefing for project. Params: { "project_id": "string" }
     - project_compare: Compare 2+ projects side-by-side. Params: { "project_ids": ["..."] }
     - project_set_active: Switch active project. Params: { "project_id": "string" }
  2. Tasks:
     - task_list: List tasks. Params: { "project_id": "string", "status": "pending|in_progress|blocked|completed", "priority": "high|critical" }
     - task_get: Get single task by ID. Params: { "task_id": "string" }
     - task_create: Create task. Params: { "project_id": "string", "title": "string", "priority": "medium|high|critical" }
     - task_update: Update task. Params: { "task_id": "string", "status": "...", "notes": "..." }
     - task_complete: Complete task. Params: { "task_id": "string", "notes": "..." }
     - task_delete: Delete task by ID. Params: { "task_id": "string" }
     - task_summary: Get task metrics and blockers. Params: { "project_id": "string" }
     - task_overdue: List overdue tasks. Params: { "project_id": "string" }
  3. Bugs:
     - bug_list: List bugs. Params: { "project_id": "string", "severity": "...", "verification_status": "..." }
     - bug_get: Get single bug by ID. Params: { "bug_id": "string" }
     - bug_create: Report bug. Params: { "project_id": "string", "title": "string", "severity": "high", "reproduction_steps": "..." }
     - bug_update: Update bug. Params: { "bug_id": "string", "diagnosis": "...", "severity": "..." }
     - bug_resolve: Mark bug fixed. Params: { "bug_id": "string", "resolution": "...", "verified": true }
     - bug_delete: Delete bug by ID. Params: { "bug_id": "string" }
     - bug_summary: Bug counts and unresolved criticals. Params: { "project_id": "string" }
  4. Persistent Memory:
     - memory_search: Search project knowledge. Params: { "project_id": "string", "query": "string" }
     - memory_get: Get single memory entry by ID. Params: { "memory_id": "string" }
     - memory_record: Save architecture decision. Params: { "project_id": "string", "title": "string", "content": "string", "category": "architecture" }
     - memory_update: Update memory entry. Params: { "memory_id": "string", "content": "..." }
     - memory_delete: Delete memory by ID. Params: { "memory_id": "string" }
  5. Git:
     - git_status: Check git working tree. Params: { "project_id": "string" }
     - git_commits: Recent commits. Params: { "project_id": "string", "count": 10 }
     - git_diff: Working tree diff. Params: { "project_id": "string", "staged": false }
     - git_contributors: List contributors and commit counts. Params: { "project_id": "string" }
  6. Filesystem:
     - file_read: Read file safely within project. Params: { "project_id": "string", "path": "relative/file/path" }
     - filesystem_inspect: Scan directory tree safely. Params: { "project_id": "string", "max_depth": 3 }
     - filesystem_recent_files: Top recently modified files. Params: { "project_id": "string", "limit": 15 }
  7. Antigravity & Jobs:
     - agy_execute: Run development coding task in Antigravity CLI. Params: { "project_id": "string", "prompt": "string" }
     - job_list: List execution jobs. Params: { "project_id": "string", "limit": 25 }
     - job_get: Poll job status/output by ID. Params: { "job_id": "string" }
  8. Health & Reports:
     - system_health: Check database connectivity and daemon status.
     - development_health: Verified facts vs. inferences project health scan. Params: { "project_id": "string" }
     - report_generate: Generate dev reports (status, daily, weekly, tasks, bugs, git, health). Params: { "report_type": "string", "project_id": "string" }
  ```
- **Method**: `POST`
- **URL**: `http://127.0.0.1:8765/api/v1/tools/dispatch`
- **Authentication**: `Aegis Token Auth` (Header Auth)
- **Headers to Send**:
  - `Content-Type`: `application/json`
- **Send Body**: `true`
- **Body Content Type**: `JSON`
- **Specify Body**: `Using JSON`
  ```json
  {
    "tool": "={{ $fromAI('tool', 'The tool name, e.g. project_assessment, task_list, git_status') }}",
    "params": "={{ $fromAI('params', 'JSON object of parameters for the tool') }}",
    "approval_id": "={{ $fromAI('approval_id', 'Approval ID if re-executing an approved action, otherwise null') }}"
  }
  ```

---

## 4. Solving Gemini AI Agent Iteration Exhaustion

### The Problem
When users ask multi-part questions like:
> *"Give me a status update on Home Projects with Git status, recent commits, pending tasks, and bugs."*

By default, Gemini invokes tools sequentially:
`git_status` (iter 1) ➔ `git_commits` (iter 2) ➔ `task_list` (iter 3) ➔ `bug_list` (iter 4) ➔ intermediate reasoning loops ➔ iteration exhaustion at limit 10!

### The Solution: `project_assessment`
Instruct Gemini in the AI Agent node prompt:
```text
CRITICAL EFFICIENCY RULE:
When the user asks for a project status, overview, health check, or multi-domain review (Git + tasks + bugs), DO NOT make multiple individual tool calls.
Instead, make EXACTLY ONE tool call:
Tool: "project_assessment" (or "project_status_report")
Params: { "project_id": "<project_id>" }
This returns all domains in a single response envelope.
```

---

## 5. Two-Layer Failure Notification System

Aegis implements two distinct layers of error handling to prevent silent workflow crashes:

```
                  [ Execution Event ]
                           │
             ┌─────────────┴─────────────┐
             ▼                           ▼
    [ Normal Tool Error ]       [ Workflow Crash / Exception ]
    (e.g. 404, 400, 403)        (e.g. timeout, network drop)
             │                           │
             ▼                           ▼
       [ Layer A ]                 [ Layer B ]
   Agent-Level Handling       n8n Error Trigger Workflow
   - Gemini receives error     - Error Trigger node catches
   - Synthesizes user advice   - Sends immediate Telegram alert
   - Halts retry loops         - Contains workflow ID & stack
```

### Layer A: Agent-Level Error Handling
When a tool returns an error code (e.g., `APPROVAL_REQUIRED`, `NOT_FOUND`), the HTTP tool returns the JSON error envelope. The AI Agent is prompted to:
1. Stop retrying failed operations with the same parameters.
2. Translate the technical error into clear, non-jargon language for Telegram.
3. If `APPROVAL_REQUIRED`, present the approval ID and prompt the user to approve or reject.

### Layer B: Workflow-Level Error Handling (n8n Error Trigger)
Create a dedicated separate workflow in n8n:
1. **Trigger**: `Error Trigger` node (fires whenever any workflow execution fails).
2. **Action**: `Telegram Send Message` node:
   ```text
   🚨 *Aegis Workflow Failure Alert*
   *Workflow*: {{ $json.workflow.name }} (ID: {{ $json.workflow.id }})
   *Error*: {{ $json.execution.error.message }}
   *Timestamp*: {{ $now.toISO() }}
   ```
3. In the Main Aegis Workflow settings, select this Error Workflow under **Error Workflow**.

---

## 6. Telegram Interactive Approval Gate Workflow

```
[ User triggers gated action ] ➔ [ Dispatcher returns HTTP 403 APPROVAL_REQUIRED with appr_xxxx ]
                                       │
                                       ▼
                     [ Telegram Interactive Message with Inline Buttons ]
                     "⚠️ Operation requires approval [CRITICAL]: project_delete"
                     [ ✅ Approve (appr_xxxx) ]    [ ❌ Reject (appr_xxxx) ]
                                       │
                                       ▼ (User taps button)
                     [ n8n Telegram Callback Webhook ]
                                       │
                                       ▼
        POST /api/v1/approvals/appr_xxxx/decision {"decision": "APPROVED"}
                                       │
                                       ▼
     POST /api/v1/tools/dispatch {"tool": "project_delete", "approval_id": "appr_xxxx"}
                                       │
                                       ▼
                     [ Aegis consumes token and executes cleanly ]
```
