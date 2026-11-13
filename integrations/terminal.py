"""Aegis Intelligence - Terminal & Subprocess Integration

Provides safe, sandboxed subprocess execution using argument arrays,
strict timeouts, buffer management, and environment sanitization.
"""

import os
import time
import subprocess
from typing import Optional

# Environment variables to filter out from subprocesses to prevent credential leakage
STRIPPED_ENV_VARS = {
    "AEGIS_API_TOKEN",
    "GEMINI_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "CLOUDFLARE_TUNNEL_TOKEN",
}

class TerminalExecutionResult:
    def __init__(self, exit_code: int, stdout: str, stderr: str, duration_seconds: float, timed_out: bool = False):
        self.exit_code = exit_code
        self.stdout = stdout
        self.stderr = stderr
        self.duration_seconds = duration_seconds
        self.timed_out = timed_out

    def to_dict(self) -> dict:
        return {
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_seconds": round(self.duration_seconds, 3),
            "timed_out": self.timed_out
        }

def safe_run_command(
    cmd: list[str],
    cwd: Optional[str] = None,
    timeout: int = 60,
    extra_env: Optional[dict] = None
) -> TerminalExecutionResult:
    """Execute a command safely using argument array with timeout enforcement."""
    if not isinstance(cmd, (list, tuple)) or not cmd:
        raise ValueError("Command must be a non-empty list of strings.")

    # Sanitize environment
    clean_env = {k: v for k, v in os.environ.items() if k not in STRIPPED_ENV_VARS}
    if extra_env:
        clean_env.update(extra_env)

    start_time = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            env=clean_env,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False # Strictly avoid shell injection
        )
        duration = time.perf_counter() - start_time
        return TerminalExecutionResult(
            exit_code=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            duration_seconds=duration,
            timed_out=False
        )
    except subprocess.TimeoutExpired as e:
        duration = time.perf_counter() - start_time
        out = e.stdout.decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        err = e.stderr.decode("utf-8", errors="replace") if isinstance(e.stderr, bytes) else (e.stderr or "")
        return TerminalExecutionResult(
            exit_code=-1,
            stdout=out,
            stderr=f"Process timed out after {timeout} seconds. {err}",
            duration_seconds=duration,
            timed_out=True
        )
    except FileNotFoundError:
        duration = time.perf_counter() - start_time
        return TerminalExecutionResult(
            exit_code=127,
            stdout="",
            stderr=f"Executable '{cmd[0]}' not found.",
            duration_seconds=duration,
            timed_out=False
        )
    except Exception as e:
        duration = time.perf_counter() - start_time
        return TerminalExecutionResult(
            exit_code=-1,
            stdout="",
            stderr=f"Subprocess execution error: {str(e)}",
            duration_seconds=duration,
            timed_out=False
        )
