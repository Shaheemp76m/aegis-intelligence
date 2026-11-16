# Aegis Intelligence — Testing Architecture & Verification Guide

**Framework**: Python `unittest` Standard Library  
**Base Test Harness**: `tests/isolated_test_case.py` (`IsolatedTestCase`)  
**Current Test Suite Count**: **76 Automated Tests (100% Pass Rate)**  
**Target Environment**: Termux on Android (Linux aarch64)

---

## 1. Testing Philosophy & Zero-Pollution Standard

Aegis Intelligence enforces a strict **Zero Production Contamination Rule**:
- **Automated tests MUST NEVER connect to, query, or modify `data/aegis.db`**.
- Tests must execute inside ephemeral, isolated temporary directories with their own temporary SQLite databases and mock token secrets.
- On test teardown, all temporary databases, logs, and files are completely purged from disk.

---

## 2. The `IsolatedTestCase` Architecture

Located in `tests/isolated_test_case.py`, `IsolatedTestCase` serves as the mandatory base class for all test modules:

```
[ Test Class Starts (setUpClass) ]
              │
              ▼
1. Close all thread-cached SQLite connections (close_connections())
              │
              ▼
2. Save original Config attributes (DB_PATH, DATA_DIR, TOKEN_FILE, API_TOKEN)
              │
              ▼
3. Create unique isolated temporary directory:
   /data/data/com.termux/files/usr/tmp/aegis_test_<ClassName>_<random>/
              │
              ▼
4. Redirect Config to isolated paths:
   Config.DATA_DIR = Path(temp_dir) / "data"
   Config.DB_PATH = Config.DATA_DIR / "aegis_test.db"
   Config.TOKEN_FILE = Config.DATA_DIR / ".api_token"
   Config.API_TOKEN = "aegis_test_isolated_token_secret_0987654321"
              │
              ▼
5. Initialize clean database schema (init_db())
              │
              ▼
[ Run Test Methods (...) ]
              │
              ▼
[ Test Class Completes (tearDownClass) ]
              │
              ▼
6. Close all thread connections (close_connections())
              │
              ▼
7. Restore original Config and environment variables
              │
              ▼
8. Delete temporary directory tree from disk (shutil.rmtree())
```

---

## 3. How to Run Tests in Termux

### Prevention of Python Bytecode (`__pycache__`)
Always use the `-B` flag when running tests in Termux to prevent generating `.pyc` clutter:

```bash
cd ~/aegis-intelligence
python3 -B -m unittest discover tests
```

### Running Specific Test Suites

#### 1. Full Regression Suite (All 76 Tests)
```bash
python3 -B -m unittest discover tests
```

#### 2. Composite Assessment Suite (`test_project_assessment.py`)
```bash
python3 -B -m unittest tests/test_project_assessment.py
```

#### 3. Dispatcher Coverage Suite (`test_dispatcher_coverage.py`)
```bash
python3 -B -m unittest tests/test_dispatcher_coverage.py
```

#### 4. Authentication & Security Regressions
```bash
python3 -B -m unittest tests/test_auth_regression.py tests/test_security.py
```

#### 5. Task & Bug Lifecycle Tests
```bash
python3 -B -m unittest tests/test_api_complete.py
```

---

## 4. Verifying Production Database Integrity

After executing any test suite, verify that the production database remained completely untouched:

```bash
python3 -c "import sqlite3; conn = sqlite3.connect('data/aegis.db'); cur = conn.cursor(); \
print('projects:', cur.execute('SELECT COUNT(*) FROM projects').fetchone()[0]); \
print('tasks:', cur.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]); \
print('bugs:', cur.execute('SELECT COUNT(*) FROM bugs').fetchone()[0]); \
print('memory:', cur.execute('SELECT COUNT(*) FROM project_memory').fetchone()[0]); \
print('approvals:', cur.execute('SELECT COUNT(*) FROM approvals').fetchone()[0])"
```

**Expected Baseline Counts**:
- `projects`: **1** (`proj_home_projects_a783bd`)
- `tasks`: **2**
- `bugs`: **1**
- `memory`: **1**
- `approvals`: **1**

---

## 5. Adding New Tests

When writing new tests:
1. Always inherit from `tests.isolated_test_case.IsolatedTestCase`.
2. Do not hardcode paths to `/data/data/.../home/aegis-intelligence/data`. Use `self._temp_dir` or `Config.DATA_DIR`.
3. If creating sample Git repositories or mock project files, place them inside `self._temp_dir`.
4. Ensure all assertions are deterministic and do not depend on external network access.
