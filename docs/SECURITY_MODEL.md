# Aegis Intelligence — Security Architecture & Threat Model

**Document Version**: 2.0.0  
**Security Posture**: Zero-Trust Localhost Architecture  
**Target Environment**: Termux on Android (Linux aarch64)

---

## 1. Termux Threat Model & Operational Boundary

Aegis Intelligence operates natively inside Termux on Android. The security architecture addresses the specific constraints and threat vectors of an unprivileged Android userland:

```
+----------------------------------------------------------------------+
|                     UNTRUSTED OUTSIDE WORLD                          |
|         (Public Internet, Cloudflare Tunnel Ingress, etc.)           |
+-----------------------------------+----------------------------------+
                                    |
                                    | Encrypted HTTPS Tunnel
                                    v
+----------------------------------------------------------------------+
|                     TERMUX APP SANDBOX (u0_a311)                     |
|                                                                      |
|  +------------------------+             +-------------------------+  |
|  | n8n Process (:5678)    |             | Antigravity CLI (agy)   |  |
|  +-----------+------------+             +------------+------------+  |
|              |                                       |               |
|              | Localhost-Only HTTP                   | Subprocess    |
|              v                                       v               |
|  +----------------------------------------------------------------+  |
|  |             AEGIS INTELLIGENCE DAEMON (127.0.0.1:8765)         |  |
|  |                                                                |  |
|  |  [ IP Verification Guard: strictly drops non-127.0.0.1 ]       |  |
|  |  [ Constant-Time Token Auth: secrets.compare_digest ]          |  |
|  |  [ PermissionManager: Risk Levels & Mandatory Approval Gates ] |  |
|  |  [ PathSandboxing: strictly bounds paths to project roots ]    |  |
|  |  [ Safe Process Runner: shell=False, tokenized argument arrays]|  |
|  |  [ Audit Logger: automatic token and secret scrubbing ]        |  |
|  +--------------------------------+-------------------------------+  |
|                                   |                                  |
|                                   v                                  |
|  +----------------------------------------------------------------+  |
|  | PROTECTED DATA STORE (~/aegis-intelligence/data/)              |  |
|  | - .api_token (0600 permissions, owner read/write only)          |  |
|  | - aegis.db (SQLite WAL, parameterized SQL queries)             |  |
|  +----------------------------------------------------------------+  |
+----------------------------------------------------------------------+
```

---

## 2. Security Defense Layers

### Layer 1: Network & Interface Isolation
- **Loopback Binding**: `server.py` binds strictly to `127.0.0.1:8765`.
- **IP Verification**: The request handler verifies `self.client_address[0] in ("127.0.0.1", "::1", "localhost")`. Any non-loopback connection is dropped immediately with HTTP 403 Forbidden.
- **Never Tunnel Port 8765**: Port 8765 must NEVER be forwarded through Cloudflare Tunnel, ngrok, or exposed via LAN/WiFi interfaces. Remote access occurs exclusively via the authenticated n8n webhook.

### Layer 2: Constant-Time Token Authentication
- **Token Secret**: Generated on initial setup as a 48-character cryptographic hex token (`secrets.token_hex(24)`).
- **Filesystem Permissions**: `data/.api_token` permissions are enforced as `0600` (readable and writable only by the Termux user).
- **Dual Header Support**: Authenticates requests passing either `X-Aegis-Token: <token>` or `Authorization: Bearer <token>`.
- **Timing Attack Resistance**: Evaluated using `secrets.compare_digest(provided_token, expected_token)`.

### Layer 3: Risk Classification & Approval Gates (`core/permission_manager.py`)
Operations are categorized into four distinct risk tiers:

| Risk Tier | Operations | Approval Gate? | Behavior |
|---|---|:---:|---|
| **LOW** | `project_list`, `project_get`, `project_inspect`, `project_assessment`, `task_list`, `task_create`, `task_update`, `task_complete`, `bug_list`, `bug_create`, `bug_update`, `bug_resolve`, `memory_search`, `memory_record`, `git_status`, `git_commits`, `git_diff`, `file_read`, `system_health`, `development_health` | **NO** | Executes autonomously. |
| **MEDIUM** | `task_delete`, `bug_delete`, `memory_delete` | **NO** | Autonomous execution of individual database record deletions (non-destructive to files). |
| **HIGH** | `system_install`, `apt_install`, `pkg_install`, `bulk_file_delete` (>3 files), `git clean -fdx` | **YES** | Halts execution; creates pending approval request; returns HTTP 403 `APPROVAL_REQUIRED`. |
| **CRITICAL** | `project_delete` (unregister project), `delete_project_dir`, `delete_project_files`, `modify_n8n`, `git push --force`, `git reset --hard`, out-of-bounds path access | **YES** | Strictly gated. Cannot execute without approved, unexpired, single-use `approval_id`. |

### Layer 4: Approval Expiration & Single-Use Tokens
1. **15-Minute Expiry Window**: All approval tokens expire exactly 900 seconds after creation. Expired tokens are marked `EXPIRED` and cannot be consumed.
2. **Atomic Single-Use**: Consuming an approval token sets `used = 1` inside an atomic SQLite transaction. Replay attacks immediately fail with `PermissionError`.
3. **Action-Matching**: An approval token generated for action `X` cannot be used to execute action `Y`.

### Layer 5: Path Traversal Sandboxing (`security/path_validator.py`)
1. **Canonical Path Resolution**: Paths are resolved using `os.path.realpath()`.
2. **Prefix Enforcement**: Target paths must start with the canonical project root:
   ```python
   rel = os.path.relpath(target_path, project_root)
   if rel.startswith("..") or rel == "..":
       raise PathValidationError("Path traversal escape detected.")
   ```
3. **System Blacklist**: Operations attempting to access system directories (`/proc`, `/sys`, `/dev`, `/system`, `/data/data/com.termux/files/usr/bin`) are unconditionally blocked.

### Layer 6: Subprocess Execution Sandboxing
1. **Zero Shell Execution**: Subprocess calls NEVER use `shell=True`. Commands are tokenized into argument lists (`["git", "status"]`).
2. **Working Directory Lockdown**: Commands execute strictly within the registered project directory (`cwd=project_path`).
3. **Execution Timeouts**: All subprocesses enforce timeouts (default: 10s–120s) to prevent resource denial-of-service on mobile devices.

### Layer 7: Audit Logging & Secret Redaction
- All security events (`PROJECT_REGISTERED`, `AUTH_FAILED`, `APPROVAL_REQUESTED`, `APPROVAL_APPROVED`, `APPROVAL_CONSUMED`) are logged to `audit_logs` and `data/logs/audit.log`.
- Regex filters automatically redact tokens, bearer credentials, and API keys before logging.
