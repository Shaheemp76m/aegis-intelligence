"""Aegis Intelligence - Antigravity CLI Execution Engine

Invokes the installed 'agy' CLI in headless print mode using subprocess argument arrays,
enforces timeouts, parses structured JSON outputs, and records token metrics.
"""

import re
import json
from typing import Optional
from config import Config
from integrations.terminal import safe_run_command
from security.path_validator import validate_path_within_project, canonicalize_path

# Regex to extract JSON block from possible terminal spinner noise
JSON_EXTRACT_RE = re.compile(r'(\{[\s\S]*\})')

class AgyExecutionResult:
    def __init__(
        self,
        exit_code: int,
        status: str,
        response: str,
        duration_seconds: float,
        conversation_id: Optional[str] = None,
        usage: Optional[dict] = None,
        raw_stdout: str = "",
        raw_stderr: str = "",
        timed_out: bool = False
    ):
        self.exit_code = exit_code
        self.status = status
        self.response = response
        self.duration_seconds = duration_seconds
        self.conversation_id = conversation_id
        self.usage = usage or {}
        self.raw_stdout = raw_stdout
        self.raw_stderr = raw_stderr
        self.timed_out = timed_out

    def to_dict(self) -> dict:
        return {
            "exit_code": self.exit_code,
            "status": self.status,
            "response": self.response,
            "duration_seconds": round(self.duration_seconds, 3),
            "conversation_id": self.conversation_id,
            "usage": self.usage,
            "stderr": self.raw_stderr,
            "timed_out": self.timed_out
        }

class AgyExecutor:
    """Safe headless executor for Antigravity CLI."""

    @classmethod
    def execute(
        cls,
        prompt: str,
        project_path: str,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        mode: Optional[str] = None
    ) -> AgyExecutionResult:
        """Execute a development prompt via 'agy -p' in the specified project directory."""
        if not prompt or not prompt.strip():
            raise ValueError("Execution prompt cannot be empty.")

        # Ensure project directory is valid and canonical
        canonical_cwd = canonicalize_path(project_path)

        # Build argument array strictly as a list (prevent shell injection)
        cmd = [
            Config.AGY_BIN_PATH,
            "-p",
            prompt.strip(),
            "--output-format",
            "json"
        ]

        if model:
            cmd.extend(["--model", model.strip()])

        if mode and mode in ("accept-edits", "auto", "plan"):
            cmd.extend(["--mode", mode])

        exec_timeout = timeout or Config.AGY_DEFAULT_TIMEOUT

        res = safe_run_command(cmd, cwd=canonical_cwd, timeout=exec_timeout)

        # Parse output
        if res.timed_out:
            return AgyExecutionResult(
                exit_code=-1,
                status="TIMED_OUT",
                response="",
                duration_seconds=res.duration_seconds,
                raw_stdout=res.stdout,
                raw_stderr=res.stderr,
                timed_out=True
            )

        # Try to parse JSON output
        parsed_json = None
        if res.stdout:
            try:
                parsed_json = json.loads(res.stdout.strip())
            except Exception:
                # If wrapped in terminal output, use regex extraction
                match = JSON_EXTRACT_RE.search(res.stdout)
                if match:
                    try:
                        parsed_json = json.loads(match.group(1))
                    except Exception:
                        pass

        if parsed_json and isinstance(parsed_json, dict):
            return AgyExecutionResult(
                exit_code=res.exit_code,
                status=parsed_json.get("status", "SUCCESS" if res.exit_code == 0 else "FAILED"),
                response=parsed_json.get("response", ""),
                duration_seconds=parsed_json.get("duration_seconds", res.duration_seconds),
                conversation_id=parsed_json.get("conversation_id"),
                usage=parsed_json.get("usage", {}),
                raw_stdout=res.stdout,
                raw_stderr=res.stderr,
                timed_out=False
            )

        # Fallback if text format or CLI non-JSON response
        return AgyExecutionResult(
            exit_code=res.exit_code,
            status="SUCCESS" if res.exit_code == 0 else "FAILED",
            response=res.stdout.strip(),
            duration_seconds=res.duration_seconds,
            raw_stdout=res.stdout,
            raw_stderr=res.stderr,
            timed_out=False
        )
