# Aegis Intelligence — Known Issues & System Limitations

This document catalogs known architectural constraints, platform limitations, operational edge cases, and mitigation strategies for Aegis Intelligence.

---

## 1. Termux & Android Platform Constraints

### 1.1 Absence of Systemd / Process Supervision
- **Issue**: Standard Linux service managers (`systemd`, `supervisord`, `upstart`) are unavailable in native Android userland.
- **Impact**: Daemons killed by the OS or user will not automatically restart unless managed.
- **Mitigation**:
  - For active development, use `tmux` sessions.
  - For headless background execution, use `nohup python3 -B server.py > data/logs/server.log 2>&1 &`.
  - For boot persistence, install the **Termux:Boot** companion app and configure `~/.termux/boot/start-aegis.sh`.

### 1.2 Android Low Memory Killer (LMKD) & Doze Mode
- **Issue**: Android places background processes into deep sleep (Doze) when the display is off and aggressively terminates high-memory processes under memory pressure.
- **Impact**: Unsolicited server termination during large compilations or long-running Antigravity background tasks.
- **Mitigation**:
  - Always acquire a wake-lock: `termux-wake-lock`.
  - Whitelist Termux in Android **Settings** → **Battery** → **Battery Optimization** (set to "Don't optimize" / "Unrestricted").
  - Restrict parallel build concurrency in compilation tasks (e.g. `MAKEFLAGS="-j2"`).

### 1.3 Termux Root and Filesystem Path Prefixes
- **Issue**: Termux does not adhere to the standard Filesystem Hierarchy Standard (FHS). Absolute paths start with `/data/data/com.termux/files/usr` or `/data/data/com.termux/files/home`.
- **Impact**: Hardcoded assumptions of `/tmp`, `/bin/bash`, or `/usr/bin/env` in external scripts will fail.
- **Mitigation**:
  - Use `tempfile.gettempdir()` or `$TMPDIR` in Python instead of hardcoding `/tmp`.
  - In shell scripts, reference `#!/data/data/com.termux/files/usr/bin/sh` or `/data/data/com.termux/files/usr/bin/env`.

---

## 2. Python 3.14 Runtime Considerations

### 2.1 Bytecode Generation (`.pyc` and `__pycache__`)
- **Issue**: Python 3.14 automatically writes compiled bytecode caches upon importing modules. In Termux, this clutters the repository tree and increases flash storage wear.
- **Mitigation**:
  - Always launch Python scripts and test runners with the `-B` flag: `python3 -B server.py` or `python3 -B -m unittest discover tests`.
  - Alternatively, export `export PYTHONDONTWRITEBYTECODE=1` in `~/.bashrc`.

---

## 3. n8n & Gemini AI Agent Integration

### 3.1 Iteration Exhaustion (`maxIterations: 10`)
- **Issue**: In n8n 2.47.4, the AI Agent node using Google Gemini has a hard limit of 10 reasoning/tool execution cycles. When answering broad queries (e.g. "Give me a complete project status"), calling fine-grained tools sequentially (`git_status`, `git_commits`, `task_list`, `bug_list`, `development_health`, etc.) consumes 6–8 tool calls plus intermediate chain-of-thought steps, crashing with an iteration exhaustion error before generating a user response.
- **Mitigation**:
  - Use the composite dispatcher action **`project_assessment`** (or alias **`project_status_report`**).
  - This aggregates project metadata, Git status, recent commits, pending tasks, unresolved bugs, project memory, recent files, and development health in a **single tool call** (1 iteration), leaving 9 iterations available for synthesis.
  - Section-level error isolation ensures partial data is returned even if one subsystem encounters an error.

### 3.2 Tool Parameter Extraction Ambiguity
- **Issue**: LLMs occasionally wrap action parameters inside an extra `parameters` or `params` object, or pass `project_id` under aliases like `projectId` or `id`.
- **Mitigation**:
  - `core/tool_router.py` implements defensive normalization: flattening nested `parameters`/`params` and normalizing `projectId` / `id` to `project_id`.

---

## 4. Antigravity CLI Quota & Session Execution

### 4.1 Token Quotas & Rate Limits
- **Issue**: Antigravity CLI commands interact with Google Gemini models and are subject to upstream rate limits and context window quotas.
- **Mitigation**:
  - Monitor quota consumption using the `agy_usage` tool.
  - Offload narrow, atomic tasks rather than sending overly broad repository scans to subagents.

### 4.2 Subprocess Tracking & Orphan Cleanup
- **Issue**: If the Aegis server is forcefully terminated while an Antigravity CLI job is executing in the background, the child CLI process may remain orphaned.
- **Mitigation**:
  - Antigravity execution tasks are registered in `integrations/antigravity_cli.py` with process handles and execution IDs.
  - Server shutdown hooks attempt graceful SIGTERM to active child processes.

---

## 5. Security & Approval Lifecycle

### 5.1 Single-Use Approval Token Invalidation
- **Issue**: An approval token generated for a destructive operation (Risk Level 2 or 3) is strictly single-use and expires after 15 minutes.
- **Impact**: If an agent retries an operation after a network timeout using the same token, the server rejects it as invalid.
- **Mitigation**:
  - Agents must check the response envelope for `approval_required: true` and request a fresh approval if a previous token expired or was consumed.

### 5.2 Non-Git Registered Projects
- **Issue**: If a project directory registered in Aegis is not a git repository (or `.git` is corrupted), git operations fail.
- **Mitigation**:
  - Git integration methods check for repository presence and return structured error objects rather than throwing unhandled exceptions.
  - In `project_assessment`, the `git` section returns `status: "unavailable"` with reason `"Not a git repository"`, allowing other sections to succeed.
