# Aegis Intelligence — Development Workflow & Contribution Guide

This guide establishes the engineering standards, test isolation practices, git hygiene, and verification workflows for developers and AI agents contributing to Aegis Intelligence.

---

## 1. Core Engineering Principles

1. **Non-Destructive Development**: Never treat Aegis as a greenfield project. Existing code, production database (`data/aegis.db`), auth tokens, and test suites are the absolute source of truth.
2. **Zero Test Pollution**: Automated tests and live verifications must **never** write to, alter, or delete records in `data/aegis.db`. All tests must use temporary, isolated environments.
3. **Bytecode Suppression**: Always invoke Python with `-B` (or set `PYTHONDONTWRITEBYTECODE=1`) on Termux to prevent cluttering the repository with `.pyc` and `__pycache__` artifacts.
4. **Verified Evidence**: Never assume an implementation works without running regression tests and inspecting real outputs. Distinguish verified facts from assumptions.
5. **Atomic, Traceable Changes**: Commit changes in small, logical units with descriptive conventional commit messages.

---

## 2. Environment Setup in Termux

Aegis runs on native Python 3.14 on Android/Termux without virtualenv or Docker:

```bash
# Clone or navigate to the repository
cd ~/aegis-intelligence

# Install Python requirements
pip install -r requirements.txt

# Verify the Python interpreter and environment
python3 -V
# Ensure Antigravity CLI is available
agy --version
```

---

## 3. Architecture & Code Structure

Before adding or modifying code, adhere to Aegis's modular boundaries:

| Directory | Responsibility | Guidelines |
|---|---|---|
| `core/` | Dispatcher router, permissions, approvals, security gates | Canonical action registry lives in `tool_router.py`. All risk permissions live in `permission_manager.py`. |
| `api/` | HTTP server endpoints, schemas, authentication | Routes live in `routes.py`. Enforce Bearer token auth via `require_auth` helper. |
| `integrations/` | Low-level service connectors | `git_manager.py`, `filesystem_manager.py`, `task_manager.py`, `bug_tracker.py`, `project_memory.py`, `approval_manager.py`. |
| `intelligence/` | Composite analysis engines & reporting | `project_analyzer.py`, `diff_summarizer.py`, `health_monitor.py`. Must reuse existing integrations, not raw SQL queries. |
| `tests/` | Unit and integration test suites | Must inherit from `tests.isolated_test_case.IsolatedTestCase`. |
| `docs/` | Architecture specs, catalogs, workflows | Keep synchronized whenever APIs or tools are added/updated. |

---

## 4. Test Discipline & Isolation Standards

### 4.1 The `IsolatedTestCase` Contract
Every test file **must** inherit from `tests.isolated_test_case.IsolatedTestCase`. This class guarantees:
- A fresh temporary directory (`tempfile.mkdtemp()`) for SQLite data.
- Isolated database initialization with exact schema and default migrations.
- Isolated `.api_token` generation.
- Full teardown and deletion of temporary databases and directories upon test completion.
- Automated assertion that `data/aegis.db` was untouched.

### 4.2 Running the Test Suite
Always run tests using `python3 -B`:

```bash
# Run the entire test suite (76+ tests)
python3 -B -m unittest discover tests

# Run a specific test module
python3 -B -m unittest tests.test_project_assessment

# Run a specific test case method
python3 -B -m unittest tests.test_project_assessment.TestProjectAssessment.test_composite_assessment_success
```

### 4.3 Verifying Zero Production Pollution
After running any tests or manual scripts, verify that production database counts remain strictly unaltered:

```bash
python3 -B -c "
import sqlite3
c = sqlite3.connect('data/aegis.db').cursor()
for table in ['projects', 'tasks', 'bugs', 'project_memory', 'approval_requests']:
    c.execute(f'SELECT COUNT(*) FROM {table}')
    print(f'{table}: {c.fetchone()[0]}')
"
```
Expected counts:
- `projects`: 1 (the legitimate `proj_home_projects_a783bd`)
- `tasks`: 2
- `bugs`: 1
- `project_memory`: 1
- `approval_requests`: 1

---

## 5. Adding New Dispatcher Actions

When introducing a new capability to the unified dispatcher:

1. **Implement Core Logic**: Add or reuse integration methods in `integrations/` or `intelligence/`.
2. **Register Action in `core/tool_router.py`**:
   - Add the handler function to `_dispatch_map`.
   - Register parameter validation and extraction.
3. **Assign Risk & Permissions in `core/permission_manager.py`**:
   - Assign the appropriate `RiskLevel` (`LEVEL_0_READ`, `LEVEL_1_WRITE_SAFE`, `LEVEL_2_WRITE_DESTRUCTIVE`, `LEVEL_3_SYSTEM_CRITICAL`).
4. **Add Isolated Tests**:
   - Write comprehensive tests in `tests/` verifying both successful invocation and edge cases (e.g., missing project, invalid params).
5. **Update Documentation**:
   - Update `docs/TOOL_CATALOG.md` and `docs/openapi.json`.
   - Update `docs/AEGIS_N8N_TOOL_CATALOG.md` if the tool is accessible to n8n AI agents.

---

## 6. Git Hygiene & Commit Standards

- **Atomic Commits**: Group related changes together. Do not bundle unrelated documentation updates with security patches.
- **Conventional Commit Messages**:
  - `feat(dispatcher): add composite project_assessment action`
  - `fix(memory): prevent text truncation during update`
  - `docs(api): document HTTP endpoints in API_REFERENCE.md`
  - `test(security): add permission boundary test cases`
  - `refactor(core): streamline error envelope formatting`
- **Strict Prohibition**: Never run `git push --force` or rewrite history on the `Main` branch.

---

## 7. Pre-Commit Verification Checklist

Before pushing or completing any development session:

- [ ] All new tests pass: `python3 -B -m unittest discover tests`
- [ ] Production database `data/aegis.db` is completely untouched
- [ ] No temporary files (`.pyc`, `__pycache__`, `.tmp`) were created in the repo
- [ ] Working tree is clean: `git status` displays only intended modifications
- [ ] Live daemon reloaded and tested via `curl http://127.0.0.1:8765/health`
- [ ] Associated documentation updated in `docs/` and `CHANGELOG.md`
