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

### Option A: Unified Dispatcher Tool (Recommended — 48 Actions in 1 Tool)

Instead of manually wiring dozens of HTTP Request nodes, attach a single **Custom Tool (HTTP Request)** connected to the unified dispatch endpoint:

- **Tool Name**: `aegis_dispatch`
- **Tool Description**:
  ```text
  Execute Aegis Intelligence operations on the local Termux development environment.
  Supported tools across 12 domains:
  - Projects: project_assessment (composite one-call project overview), project_list, project_get, project_register, project_update, project_delete, project_inspect, project_context, project_compare, project_set_active
  - Health & Diagnostics: system_health, development_health, report_generate
  - Tasks: task_list, task_get, task_create, task_update, task_complete, task_delete, task_summary, task_overdue
  - Bugs: bug_list, bug_get, bug_create, bug_update, bug_resolve, bug_delete, bug_summary
  - Memory: memory_search, memory_get, memory_record, memory_update, memory_delete
  - Git: git_status, git_commits, git_diff, git_contributors
  - Filesystem: file_read, filesystem_inspect, filesystem_recent_files
  - Antigravity & Jobs: agy_models_list, agy_model_switch, agy_usage_summary, agy_execute, job_list, job_get
  - Approvals & Audit: approval_list, approval_get, approval_decide, audit_logs_get
  ```
- **Method**: `POST`
- **URL**: `http://127.0.0.1:8765/api/v1/tools/dispatch`
- **Authentication**: `Header Auth` (Aegis Token Auth)
- **Headers to Send**:
  - `Content-Type`: `application/json`
- **Send Body**: `true`
- **Body Content Type**: `JSON`
- **Specify Body**: `Using JSON`
  ```json
  {
    "action": "={{ $fromAI('action', 'Exact Aegis action name, e.g. task_list, project_inspect, git_status, project_assessment') }}",
    "params": "={{ $fromAI('params', 'JSON object of parameters for the tool') }}",
    "approval_id": "={{ $fromAI('approval_id', 'Approval ID if re-executing an approved action, otherwise null') }}",
    "execution_id": "={{ $('Get or Create Session HTTP').item.json?.data?.session_id ? ($('Get or Create Session HTTP').item.json.data.session_id + '_' + $execution.id) : $execution.id }}",
    "session_id": "={{ $('Get or Create Session HTTP').item.json?.data?.session_id }}"
  }
  ```
  *(Note: Aegis accepts both `"action"` and `"tool"`. When configuring n8n LangChain Tools Agent V3, use `"action"` as the parameter key to prevent n8n's internal `resolveToolName()` from overriding the tool's registered name with the nested parameter value).*d": "={{ $('Get or Create Session HTTP').item.json?.data?.session_id }}"
  }
  ```

### Anti-Loop Execution Safeguards:
Aegis tracks each tool call using `execution_id` in an SQLite Execution Ledger.
- **Read-Only Cache**: Identical queries within the same turn immediately return cached data without re-querying SQLite or Git.
- **Stagnation Guard**: If the agent repeats an action more than twice, Aegis halts execution with `STAGNATION_DETECTED`, instructing Gemini to synthesize its final Telegram answer immediately.
- **Limits**: Maximum 15 actions, 3 consecutive failures, or 60s per execution.

*(For full per-tool parameter schemas and examples, see `docs/AEGIS_N8N_TOOL_CATALOG.md`)*

---

### Option B: Individual Specialized Tools (Alternative)

If you prefer discrete tool blocks for specific workflows, attach individual **Custom Tool** nodes:

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

---

## 5. Native Telegram Conversation Loop & Typing Indicator

The conversation loop in n8n (`Aegis - Antigravity Agent Loop`) handles native Telegram interactions without external forms or web redirects.

### Dual-Layer Typing Indicator Architecture

To maintain a continuous typing state in the user's Telegram client during Gemini AI reasoning, multi-step tool calls, and long-running Antigravity code tasks, Aegis employs a dual-layer strategy:

1. **Layer 1: Immediate First-Turn UI Feedback (n8n Built-in)**
   - Node: `Send Typing Indicator` (`n8n-nodes-base.telegram`, typeVersion 1.2)
   - Operation: `sendChatAction`
   - Action: `typing`
   - Positioned immediately between `Check Duplicate` (true branch) and `AI Agent` (<50ms execution).

2. **Layer 2: Background Heartbeat Service (`integrations/telegram_typing.py`)**
   - Automatically initiated when `Get or Create Session HTTP` calls `POST /api/v1/sessions/get-or-create`.
   - Runs a non-blocking daemon thread refreshing `sendChatAction: typing` every 4.0 seconds.
   - Automatically terminated when `Save Session Turn HTTP` calls `POST /api/v1/sessions/add-turn` upon response delivery, or when the session is closed via `POST /api/v1/sessions/close`.

### Dedicated Typing Endpoints
- `POST /api/v1/sessions/typing/start` — Start a background heartbeat for a session.
- `POST /api/v1/sessions/typing/stop` — Stop an active typing heartbeat.

### Credentials & Security
- Telegram Bot token is stored locally at `data/.telegram_token` with `0600` permissions, or passed via `TELEGRAM_BOT_TOKEN` environment variable.
- Never committed to Git or exposed over external APIs.

---

## 6. Asynchronous Background Command & Build Execution

Operations such as `npm run build`, `npm install`, `pytest`, or compilation suites can run longer than ordinary HTTP request timeouts (30s-120s). Aegis provides asynchronous detached execution for these tasks:

### Architecture & Agent Interaction Pattern

```
1. [User asks to build/test] ──► [Gemini calls job_start via aegis_dispatch]
                                        │
                                        ▼ (Returns in <200ms)
                               [job_id returned to Gemini]
                                        │
                                        ▼
                   [Gemini sends immediate confirmation with job_id]
                                        │
                                        ▼
                  [n8n execution finishes cleanly; no timeout]
                                        │
             (Meanwhile, process runs in background in its own session)
                                        │
                         [Command exits / times out]
                                        │
                                        ▼
           [Aegis directly dispatches Telegram completion message to user]
```

### Supported Job Actions via `aegis_dispatch`:
- **`job_start`**: Spawn detached background process. Params: `{"command": "npm run build", "project_id": "...", "cwd": "...", "timeout": 1800}`.
- **`job_get`**: Query status, exit code, and duration by ID. Params: `{"job_id": "..."}`.
- **`job_list`**: List recent jobs with optional status filter. Params: `{"status": "running|completed|failed"}`.
- **`job_logs`**: Retrieve disk log slices. Params: `{"job_id": "...", "lines": 50, "tail": true}`.
- **`job_cancel`**: Cancel running background process group. Params: `{"job_id": "..."}`.

### Telegram Notification Delivery
Upon process exit or timeout, Aegis uses `send_telegram_message()` to deliver an independent completion card to the user containing the exit code, duration, and output preview, without keeping n8n executions or HTTP sockets open indefinitely.

---

## 7. Antigravity Instance Control Plane & Natural Language Orchestration

Aegis acts as the intelligent control plane for local Antigravity CLI instances. Users can query, start, inspect, submit tasks to, and terminate Antigravity instances through natural language in Telegram.

### Natural Language Request Mapping
| User Request | Dispatcher Action | Parameters | Expected Behavior |
|---|---|---|---|
| *"Is any Agy instance running?"* | `agy_instance_list` | `{"include_historical": true}` | Scans `/proc` for live `agy`/`agy.va39` processes. Reports active instances with PID, project, and start time; explicitly reports none if empty. Never guesses or tells user to run `ps`. |
| *"Show me all active instances"* | `agy_instance_list` | `{"include_historical": false}` | Returns only currently active processes running on the host. |
| *"Start a new Agy instance for Home Projects"* | `agy_instance_start` | `{"project_id": "proj_..."}` | Launches detached background process with `AGY_AUTO_UPDATE=0`. Returns immediately with `instance_id` and PID. |
| *"What is instance 2 currently doing? / Show output"* | `agy_instance_output` | `{"instance_id": "..." or "pid": ..., "lines": 50}` | Tails live log file from disk and returns recent terminal output. |
| *"Stop the instance working on the frontend"* | `agy_instance_stop` | `{"instance_id": "..." or "pid": ...}` | Verifies target is an Agy process and safely terminates its process group (`SIGTERM`/`SIGKILL`). |
| *"Tell the running instance to fix the frontend"* | `agy_task_submit` | `{"prompt": "Fix frontend ...", "conversation_id": "..."}` | Resumes the conversation via `--conversation <id>` to preserve context across turns. |
| *"Has the task completed?"* | `agy_task_status` | `{"task_id": "job_..."}` | Returns current status, duration, exit code, and structured response text. |

---

## 8. Centralized Skill System & On-Demand Routing

Aegis incorporates a centralized library of **307 specialized technical skills** derived from `@rmyndharis/antigravity-skills` (v2.0.0), organized across 9 functional categories (`development`, `infrastructure`, `data-ai`, `business`, `security`, `workflow`, `architecture`, `testing`, `general`) and 6 core bundles.

### 8.1 Progressive Disclosure Architecture
Blindly injecting all 307 skills into the Gemini AI Agent context would consume over **45,000 tokens** per turn, causing context exhaustion and severe reasoning latency. 

Aegis solves this with **Intelligent On-Demand Routing**:
1. **Lightweight Indexing**: Only lightweight skill metadata (~12KB JSON) is indexed locally.
2. **7-Factor Intelligent Selection**: The CEO evaluates the task using 7 scoring criteria (task relevance, agent role affinity, project technology compatibility, Termux feasibility, security score, and overlap pruning) to select the smallest viable set (typically 1–3 skills, consuming only 400–1,200 tokens).
3. **Context Efficiency**: Yields a **>97% token reduction** compared to monolithic bulk-loading.
4. **Targeted Workspace Activation**: Selected skills are copied on demand into the project workspace (`.agents/skills/<skill_id>/SKILL.md`) without mutating existing user-created skills (`~/.gemini/config/skills/gsd-*`).

### 8.2 Security Guardrails & Static Audit
- **Zero-Trust Third-Party Policy**: All external skills are treated as untrusted input.
- **Pre-Activation Static Analysis**: `SkillSelector.audit_skill_content()` inspects skill instructions for destructive shell commands (`rm -rf /`, formatting), token exfiltration attempts, and approval gate bypasses.
- **Immutable Governance**: Skills cannot override Aegis core boundaries, file sandboxing, or human approval gates.

### 8.3 Dispatcher Actions & Natural Language Mapping

The Gemini AI Agent can use the following dispatcher actions via `aegis_dispatch`:

| User Request | Dispatcher Action | Parameters | Expected Behavior |
|---|---|---|---|
| *"Find skills for FastAPI or React"* | `skill_search` | `{"query": "fastapi react", "limit": 5}` | Searches the 307-skill catalog by keyword, aliases, and tags. Returns matching metadata and compatibility info. |
| *"What skills should the repair engineer use to fix a Node build error?"* | `skill_select` | `{"task": "fix node build error", "agent_id": "aegis-repair-engineer", "tech_stack": ["node"]}` | Evaluates task relevance and agent boundaries; selects 1–3 vetted skills (e.g. `devops-troubleshooter`). |
| *"Inspect the test-automator skill before using it"* | `skill_inspect` | `{"skill_id": "test-automator"}` | Loads instruction preview and runs static security audit verifying safe execution. |
| *"Activate the python-pro skill for this project"* | `skill_activate` | `{"skill_id": "python-pro", "project_id": "proj_..."}` | Copies pre-audited instructions from vault into `.agents/skills/python-pro/SKILL.md`. |

### 8.4 REST Endpoints
For direct integration outside of the tool dispatcher:
- `GET/POST /api/v1/skills/search`: Search catalog by query, category, and target agent.
- `POST /api/v1/skills/select`: Multi-factor selection returning selected skills and context token savings.
- `GET /api/v1/skills/inspect/{skill_id}`: Preview instructions and static security audit verdict.
- `POST /api/v1/skills/activate`: Copy skill instructions into target project workspace.



