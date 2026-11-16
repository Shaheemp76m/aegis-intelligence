# Changelog

All notable changes to **Aegis Intelligence** will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.6.0] - 2026-11-15

### Added
- **Centralized Skill Library & Intelligent On-Demand Routing System (`skill_system/`)**:
  - **Comprehensive Skill Catalog (`skill_system/skill_catalog.json`)**: Curated and indexed 307 specialized technical skills from `@rmyndharis/antigravity-skills` (v2.0.0) across 9 categories (`development`, `infrastructure`, `data-ai`, `business`, `security`, `workflow`, `architecture`, `testing`, `general`), 6 bundles (`core-dev`, `security-core`, `k8s-core`, `data-core`, `ai-core`, `ops-core`), and 60 canonical aliases.
  - **8-Agent Functional Skill Mapping (`skill_system/agent_skill_mapping.json`)**: Assigned precise primary categories, curated skill sets, and strictly forbidden domains for all eight specialized agents, enforcing role boundaries (e.g. Bug Hunter restricted from modifying code; CISO restricted from business skills).
  - **9-Step CEO Skill Selection Engine (`skill_system/selector.py`)**: Multi-factor evaluation intelligence assessing task relevance (with word-boundary token matching), agent role affinity, project technology compatibility, Termux feasibility, vault readiness, and overlap pruning. Selects the smallest viable set (typically 1–3 targeted skills).
  - **Context-Efficiency & Progressive Disclosure Optimization**: Dynamic selection of 1–3 skills (~400–1,200 tokens) vs. bulk loading all 307 skills (~45,000 tokens) achieves **>97% token savings**, eliminating context window bloat and reasoning latency.
  - **Zero-Trust Security Policy & Static Audit (`skill_system/SKILL_SECURITY_POLICY.md`)**: `SkillSelector.audit_skill_content()` performs automated pre-activation AST-like static analysis detecting and blocking destructive shell commands (`rm -rf /`, `mkfs`), credential exfiltration (`cat api_token`, `curl .env`), and permission override claims.
  - **Vetted Skill Vault (`skill_system/vault/`)**: Pre-populated with 24 vetted core skills (`fastapi-pro`, `python-pro`, `typescript-pro`, `react-modernization`, `debugger`, `devops-troubleshooter`, `security-auditor`, `test-automator`, etc.) ready for non-destructive workspace activation (`.agents/skills/`).
  - **Zero-Hallucination Fallback**: When no matching vetted skill exists or tasks are out-of-scope, the selector returns an empty selection with an explicit `missing_skill` advisory rather than fabricating capabilities.
  - **Preservation of Existing Custom Skills**: Operates in dedicated workspace directories without modifying or overwriting existing user-created skills (`~/.gemini/config/skills/gsd-*`).
- **REST Endpoints & Tool Dispatcher Integration**:
  - Added dispatcher actions and aliases: `skill_search` (`search_skills`), `skill_select` (`select_skills`), `skill_inspect` (`inspect_skill`), `skill_activate` (`activate_skill`).
  - Added REST API routes in `api/routes.py`: `GET /api/v1/skills/search`, `POST /api/v1/skills/search`, `POST /api/v1/skills/select`, `GET /api/v1/skills/inspect/{skill_id}`, `POST /api/v1/skills/activate`.
  - Registered low-risk skill operations in `core/permission_manager.py` (52 total dispatcher actions).
- **Agent Governance Documentation Synchronization**:
  - Added Section 18 ("Skill Library Integration & On-Demand Activation") across all 8 agent definitions in `agent_organization/agents/` (`CEO.md`, `CTO.md`, `BUG_HUNTER.md`, `REPAIR_ENGINEER.md`, `RESEARCH_INTELLIGENCE.md`, `CISO.md`, `DEVOPS_SRE.md`, `QA_RELEASE_MANAGER.md`).
  - Updated `docs/AEGIS_N8N_TOOL_CATALOG.md` with Domain 12 (Centralized Skill System & Intelligent Routing).
  - Updated `docs/n8n_integration.md` with Section 8 detailing n8n agent tool patterns and Telegram natural language mappings.
  - Updated `docs/openapi.json` to version 2.6.0 with 4 new skill endpoints (42 total OpenAPI endpoints).

---

## [2.5.0] - 2026-11-14

### Added
- **Antigravity Instance Control Plane (`core/agy_instance_manager.py`)**:
  - **Live OS Process Discovery via `/proc`**: Ground-truth process inspection scanning active Linux `/proc` tables for running `agy` / `agy.va39` processes without relying exclusively on database records.
  - **Session & Log Correlation**: Inspects process file descriptors to extract active conversation IDs (`presence/<uuid>.lock`) and runtime log files (`log/cli-*.log`). Classifies processes as `interactive` (attached to `/dev/pts/*`) or `headless`.
  - **Detached Instance Spawning**: Launches Antigravity background instances with `start_new_session=True`, operation-specific timeouts, and strict `AGY_AUTO_UPDATE=0` injection to prevent non-interactive stdin update prompt hangs.
  - **Multi-Turn Task Resumption**: Submits tasks with `--conversation <conversation_id>`, preserving multi-turn context natively within the Antigravity CLI.
  - **Safe Process Termination**: `stop_instance` enforces security checks verifying that target PIDs genuinely belong to Antigravity commands before dispatching `os.killpg(pgid, signal.SIGTERM)` / `SIGKILL`, preventing accidental termination of unrelated system processes.
- **Eight-Agent Corporate Governance System**:
  - Expanded organization into an 8-agent AI-operated technology company:
    1. **CEO — Aegis Orchestrator (`agents/aegis-orchestrator.md`)**: Single entry point, strategy, dynamic need-based activation, and user synthesis.
    2. **CTO — Software Engineering Director (`agents/aegis-cto.md`)**: System architecture, ADRs, engineering standards, and code review.
    3. **Bug Hunter — Bug Discovery & Diagnostics (`agents/aegis-bug-hunter.md`)**: Defect reproduction, root-cause isolation, and severity classification. *Strictly does not write code fixes.*
    4. **Repair Engineer — Bug Fixing & Remediation (`agents/aegis-repair-engineer.md`)**: Minimal surgical patches and targeted regression tests. *Never marks its own findings resolved.*
    5. **Research & Intelligence Agent (`agents/aegis-researcher.md`)**: Multi-source technical research across GitHub issues/PRs/releases, official documentation, Stack Overflow, Reddit, and security advisories with zero fabrication.
    6. **CISO — Cybersecurity Director (`agents/aegis-ciso.md`)**: Path sandboxing, secret protection, approval gates, and security veto authority.
    7. **DevOps/SRE — Infrastructure & Operations (`agents/aegis-devops.md`)**: Antigravity instance management, background builds, Termux resources, SQLite WAL, and recovery.
    8. **QA/Release Manager (`agents/aegis-qa.md`)**: Independent full-suite test execution (100% pass rate enforcement) and release gate sign-off.
  - Authored comprehensive governance documentation:
    - [docs/AGENT_ORGANIZATION.md](file:///data/data/com.termux/files/home/aegis-intelligence/docs/AGENT_ORGANIZATION.md)
    - [docs/AGENT_DELEGATION.md](file:///data/data/com.termux/files/home/aegis-intelligence/docs/AGENT_DELEGATION.md)
    - [docs/AGENT_PERMISSION_MATRIX.md](file:///data/data/com.termux/files/home/aegis-intelligence/docs/AGENT_PERMISSION_MATRIX.md)
    - [docs/AGENT_EXECUTION_LIFECYCLE.md](file:///data/data/com.termux/files/home/aegis-intelligence/docs/AGENT_EXECUTION_LIFECYCLE.md)
- **New Dispatcher Actions & REST Endpoints**:
  - `agy_instance_list`: Real-time discovery of live OS instances + historical jobs.
  - `agy_instance_status`: Deep metrics inspection for an instance by PID or ID.
  - `agy_instance_start`: Launch detached Antigravity process in project root.
  - `agy_instance_stop`: Safely terminate running Antigravity instance.
  - `agy_instance_output`: Tail or stream active log files directly from disk.
  - `agy_task_submit`: Autonomous development task submission with conversation continuation.
  - `agy_task_status`: Progress, duration, exit code, and structured response inspection.
  - REST routes: `GET /api/v1/agy/instances`, `GET /api/v1/agy/instances/{instance_id}`, `POST /api/v1/agy/instances/start`, `POST /api/v1/agy/instances/{instance_id}/stop`, `GET /api/v1/agy/instances/{instance_id}/output`, `POST /api/v1/agy/tasks/submit`, `GET /api/v1/agy/tasks/{task_id}` (38 total routes in `docs/openapi.json`).
- **Dedicated Test Suite (`tests/test_agy_instance_manager.py`)**:
  - 7 isolated unit tests verifying instance discovery, starting, log tailing, safe termination, security guardrails, task submission with conversation continuation, and dispatcher routing.
- **n8n Workflow & Natural Language Alignment**:
  - Updated tool description and Gemini AI Agent system prompt in duplicated workflow `voXnSaOmStioMwW6`.
  - Configured agent to immediately call `agy_instance_list` when asked "Is any Agy instance running?" instead of guessing or advising manual commands.
  - Original workflow `7cF5eySAhUvkkrnU` preserved 100% untouched.

---

## [2.4.0] - 2026-11-14

### Added
- **Asynchronous Background Command Execution Engine (`core/execution_manager.py`)**:
  - **Detached Process Spawning**: Spawns long-running shell and build operations in isolated process groups (`subprocess.Popen(..., start_new_session=True)`), returning immediately with a unique `job_id` without holding HTTP sockets or webhook connections open.
  - **Continuous File-Stream Logging**: Streams stdout and stderr directly to disk at `data/jobs/{job_id}.log`, preventing memory bloat on Termux/Android even with high-volume log streams (supports up to 5MB before head/tail truncation).
  - **Operation-Specific Timeouts**: Configurable timeout profiles in `config.py` (`JOB_TIMEOUT_BUILD`: 1800s, `JOB_TIMEOUT_INSTALL`: 1800s, `JOB_TIMEOUT_TEST`: 600s, `JOB_TIMEOUT_DEFAULT`: 300s). Enforces graceful termination (`SIGTERM`) followed by forceful cleanup (`SIGKILL`) across the entire process group.
  - **Daemon Restart & Crash Recovery**: `ExecutionManager.recover_jobs()` invoked during daemon startup (`server.py`) reconciles SQLite state against surviving OS process PIDs and cleans up orphaned entries.
  - **Clean Job Cancellation**: Process group signal termination (`os.killpg`) via `POST /api/v1/jobs/{job_id}/cancel` and `job_cancel` dispatcher action.
- **Independent Telegram Completion Notifications**:
  - `send_telegram_message()` (`integrations/telegram_typing.py`) dispatches asynchronous status alerts (success, failure with exit code, or timeout) directly to the requesting user's Telegram chat upon process termination, fully decoupled from n8n execution lifecycles.
- **Database Schema Migration 4 (`storage/migrations.py`)**:
  - Extended `execution_jobs` table with columns: `command`, `working_directory`, `pid`, `pgid`, `log_file`, `started_at`, `error_message`, `timeout_seconds`, and `telegram_chat_id`.
  - Added database indexes on `status` and `project_id`. Production database `data/aegis.db` migrated to schema version 4.
- **REST Endpoints & Dispatcher Actions**:
  - `POST /api/v1/jobs/start`: Spawns background job (`job_start`, `start_job`, `run_job`, `background_execute`, `bg_execute`).
  - `GET /api/v1/jobs`: Lists jobs with optional `project_id` and `status` filters (`job_list`, `list_jobs`).
  - `GET /api/v1/jobs/{job_id}`: Retrieves job details and real-time status (`job_get`, `get_job`, `job_status`).
  - `GET /api/v1/jobs/{job_id}/logs`: Retrieves tail or head log lines (`job_logs`, `get_job_logs`).
  - `POST /api/v1/jobs/{job_id}/cancel`: Terminates running job process group (`job_cancel`, `cancel_job`).
- **Comprehensive Unit Test Suite (`tests/test_async_jobs.py`)**:
  - 10 test cases covering short jobs, running status, successful builds, failed builds with stderr, cancellation, timeout enforcement, log chunking/slicing, daemon restart recovery, and Telegram completion notification.
  - Full automated test suite expanded to 110 tests passing at 100% (`python3 -B -m unittest discover tests`).
- **Documentation & Workflow Alignment**:
  - Updated `docs/openapi.json` with 3 new paths (31 total OpenAPI endpoints).
  - Updated `docs/AEGIS_N8N_TOOL_CATALOG.md` with Domain 12 (Background Jobs & Execution).
  - Updated `docs/n8n_integration.md` with Section 6 architectural pattern for asynchronous execution.
  - Updated n8n workflow `voXnSaOmStioMwW6` tool definition and system message in `~/.n8n/database.sqlite`. Original workflow `7cF5eySAhUvkkrnU` preserved 100% untouched.

---

## [2.3.0] - 2026-11-14

### Added
- **Native Telegram Typing Indicator Architecture**: Implemented dual-layer typing feedback for the duplicated Aegis workflow (`voXnSaOmStioMwW6`):
  - **Layer 1 (Immediate UI Feedback)**: Built-in n8n Telegram node (`Send Typing Indicator`, `n8n-nodes-base.telegram`, typeVersion 1.2) invoking `sendChatAction: typing` directly between `Check Duplicate` and `AI Agent` (<50ms).
  - **Layer 2 (Background Heartbeat Service)**: `TelegramTypingService` (`integrations/telegram_typing.py`) spawning a non-blocking daemon thread refreshing `sendChatAction: typing` every 4.0 seconds during Gemini AI reasoning and multi-step tool calls.
- **Session Lifecycle Heartbeat Integration**: Automatically started upon valid message receipt in `SessionManager.get_or_create_session()`, cleanly stopped when the final response is delivered in `SessionManager.add_turn()`, and terminated on session exit in `SessionManager.close_session()`.
- **Typing REST Endpoints**:
  - `POST /api/v1/sessions/typing/start`: Manual start of typing heartbeat.
  - `POST /api/v1/sessions/typing/stop`: Immediate termination of typing heartbeat.
- **Secure Token Storage**: Local Telegram Bot token read from `TELEGRAM_BOT_TOKEN` environment variable or `data/.telegram_token` (strictly `0600` permissions, ignored by Git).
- **Isolated Unit Test Suite (`tests/test_telegram_typing.py`)**: 9 comprehensive test cases covering token retrieval, HTTP error handling, heartbeat lifecycle, automatic expiration, and concurrency. Full backend test suite passing at 100% (100/100 tests in 50.15s).
- **Verified Controlled Tests**:
  - Short response (Execution 275): Completed in 10.8s with immediate typing indicator feedback.
  - Long-running multi-tool operation (Execution 276): Completed in 86.5s across 3 dispatcher tool calls (`project_list`, `git_status`, `task_list`) with continuous background typing indicator maintenance and clean shutoff.
  - Original workflow `7cF5eySAhUvkkrnU` preserved 100% untouched.

## [2.2.1] - 2026-11-14

### Fixed
- **n8n AI Agent V3 Infinite Execution Loop Resolved**: Diagnosed and resolved the root cause of the Gemini + Simple Memory 10-iteration loop in workflow `voXnSaOmStioMwW6`.
  - **Tool Name Mapping Collision**: In `@n8n/n8n-nodes-langchain` Tools Agent V3, `resolveToolName()` inspected `tool.action.input?.tool` and replaced the tool's registered name (`aegis_dispatch`) with the nested action value (e.g. `project_list`). On subsequent turns, Gemini attempted to call the nested name directly, which `createEngineRequests()` could not resolve against the parent tool list, resulting in empty engine action sets (`actions: []`) and execution starvation.
  - **Parameter Key Alignment**: Changed the AI-provided parameter key in `aegis_dispatch` body parameters from `"tool"` to `"action"`, which is fully supported by Aegis's dispatcher (`body.get("tool") or body.get("action")`), cleanly bypassing the LangChain `resolveToolName` override.
  - **Tool Node Renaming**: Renamed tool node from `HTTP Request Tool` to `aegis_dispatch`, ensuring exact match with the system prompt and LangChain tool registration.
  - **Prompt Context Exponential Bloat Eliminated**: Removed redundant `"PREVIOUS CONVERSATION CONTEXT:\n" + context_history` string concatenation from the AI Agent `text` parameter. `Simple Memory` now manages multi-turn history natively without recursive double-injection.
  - **Workflow Publication**: Published updated workflow version (`67795e9a-31de-49e5-9455-19312917f36a`) to activate changes for production webhook execution.
- **Controlled Tests Verified**:
  - Single read-only tool call (`List all projects ,only names`): Execution 260 completed successfully in 6.4s with exactly 2 model invocations and 1 tool call.
  - Multi-step tool calls (`git_status` + `task_summary`): Execution 261 completed successfully in 12.5s with exactly 3 model invocations, 2 tool calls, and zero repeated actions.

## [2.2.0] - 2026-11-14

### Added
- **Execution Ledger Subsystem (`core/execution_ledger.py`)**: SQLite-backed ledger tracking agent operations with deterministic SHA256 action signing (`action:parameters:context`), attempt counts, durations, and execution statuses.
- **Database Migration 3 (`storage/migrations.py`)**: Created `execution_ledger` table with indexes on `(execution_id, action_signature)`, `execution_id`, and `session_id`.
- **Duplicate Action Deduplication**: Automated short-circuiting for read-only tools returning cached results immediately within the same execution cycle without re-querying SQLite or Git.
- **In-Flight Concurrency Locks**: Thread-safe duplicate in-flight action locking preventing race conditions and concurrent duplicate tool invocations.
- **Stagnation Detection & Clean Loop Halting**: Proactively interrupts repeated tool loops by returning structured `STAGNATION_DETECTED` reports instructing Gemini to synthesize its final Telegram response.
- **Configurable Execution Limits**: Enforces hard boundaries on total actions (`LEDGER_MAX_TOTAL_ACTIONS: 15`), repeated identical calls (`LEDGER_MAX_REPEATED_ACTIONS: 2`), consecutive failures (`LEDGER_MAX_CONSECUTIVE_FAILURES: 3`), and execution duration (`LEDGER_EXECUTION_TIMEOUT: 60s`).
- **Execution Progress Tool (`execution_progress`)**: Dispatcher tool allowing inspection of execution history, attempt counts, and stagnation status.
- **Automatic n8n Parameter Binding**: Configured duplicated workflow `voXnSaOmStioMwW6` HTTP Request Tool to pass `$execution.id` and `session_id` automatically on every tool call.
- **Dedicated Test Suite (`tests/test_execution_ledger.py`)**: 8 isolated unit test cases covering all anti-loop safeguards, stagnation halts, and limits.

### Changed
- **Tool Dispatch Endpoint (`POST /api/v1/tools/dispatch`)**: Extended to accept `execution_id`, `session_id`, and `objective` via JSON body or request headers (`X-Execution-Id`, `X-Session-Id`).
- **Tool Router (`core/tool_router.py`)**: Integrated `ExecutionLedger` pre-execution checks and post-execution recording across all dispatched tools.
- **Documentation Synchronization**: Updated `docs/openapi.json`, `docs/AEGIS_N8N_TOOL_CATALOG.md`, and `docs/n8n_integration.md`.

---

## [2.0.0] - 2026-11-14

### Added
- **Composite Action `project_assessment`**: Implemented single-call read-only assessment tool aggregating project metadata, Git repository state, pending/overdue/blocked tasks, unresolved bugs, persistent knowledge memory, recently modified files, and development health.
- **REST Endpoint `GET /api/v1/projects/{project_id}/assessment`**: Direct HTTP route for composite assessment with optional query filter `sections`.
- **Three-Agent Governance Architecture**: Formalized the 3 specialized agent roles (`aegis-orchestrator`, `aegis-bug-hunter`, `aegis-specialist`) in `AGENTS.md` and `agents/`.
- **49 Total Dispatcher Actions**: Complete 1:1 coverage of all REST routes and internal domain capabilities through `POST /api/v1/tools/dispatch`.
- **Bidirectional Alias Normalization (`ALIAS_MAP`)**: Added 40+ canonical mappings in `ToolRouter` to support verb-noun (`list_tasks`) and noun-verb (`task_list`) agent calls seamlessly.
- **Isolated Test Harness (`tests/isolated_test_case.py`)**: Guarantees zero pollution of `data/aegis.db` by creating isolated temporary SQLite databases for all unit tests.
- **Dedicated Coverage & Assessment Test Suites**: Added `tests/test_dispatcher_coverage.py` and `tests/test_project_assessment.py` bringing automated test suite to 76 tests with a 100% pass rate.
- **Exhaustive Documentation System**: Added `docs/ARCHITECTURE.md`, `docs/API_REFERENCE.md`, `docs/DATABASE_SCHEMA.md`, `docs/SECURITY_MODEL.md`, `docs/TESTING.md`, `docs/TERMUX_DEPLOYMENT.md`, `docs/AGENT_ORCHESTRATION.md`, `docs/DEVELOPMENT_WORKFLOW.md`, `docs/KNOWN_ISSUES.md`, and `docs/AEGIS_N8N_TOOL_CATALOG.md`.

### Changed
- **Authentication Middleware**: Enhanced `server.py` to transparently authenticate requests using either `X-Aegis-Token` or standard `Authorization: Bearer <token>` headers with constant-time equality validation (`secrets.compare_digest`).
- **OpenAPI Specification**: Updated `docs/openapi.json` to define all 49 dispatcher actions, parameter properties, and new assessment routes.
- **n8n Integration Guide**: Updated `docs/n8n_integration.md` to recommend the single-tool `aegis_dispatch` pattern with composite tool prioritization.

### Fixed
- **Database Pollution**: Audited and purged 34 test-generated records from `data/aegis.db`, preserving the clean production baseline and retaining verified backup `data/backups/aegis_pre_cleanup_backup_20261113_190845.db`.
- **Unknown Tool Exception on Verb-Noun Invocation**: Resolved discrepancy where `PermissionManager` permitted verb-noun actions (e.g. `list_tasks`) but `ToolRouter` raised `ValueError: Unknown tool name`.
- **Gemini Iteration Exhaustion**: Mitigated multi-tool loop limits in n8n by providing the single-call composite `project_assessment` / `project_status_report` tool.

---

## [1.0.0] - 2026-11-13

### Added
- Initial implementation of Aegis Intelligence backend daemon on `127.0.0.1:8765`.
- SQLite storage layer with WAL mode (`storage/database.py`).
- Domain intelligence modules: `ProjectAnalyzer`, `TaskManager`, `BugTracker`, `ProjectMemory`, `ReportGenerator`, `ContextBuilder`, `DevelopmentMonitor`.
- Integrations: `GitIntegration`, `FilesystemIntegration`, `TerminalIntegration`, `ModelManager`, `UsageMonitor`.
- Security layer: token authentication, approval gates, audit logger, and project path sandboxing.
- Initial n8n integration guide and OpenAPI 3.0 specification.
