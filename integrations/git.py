"""Aegis Intelligence - Git Integration Module

Inspects Git repository state, working tree changes, commit history, and contributors.
"""

import os
from typing import Optional
from integrations.terminal import safe_run_command

class GitIntegration:
    """Provides structured Git inspection for registered projects."""

    @staticmethod
    def is_git_repository(repo_path: str) -> bool:
        """Check if path contains a valid git repository."""
        if not os.path.isdir(repo_path):
            return False
        res = safe_run_command(["git", "rev-parse", "--is-inside-work-tree"], cwd=repo_path, timeout=5)
        return res.exit_code == 0 and res.stdout.strip() == "true"

    @classmethod
    def get_repo_status(cls, repo_path: str) -> dict:
        """Get structured status: branch, clean/dirty, staged, modified, untracked."""
        if not cls.is_git_repository(repo_path):
            return {
                "is_git": False,
                "branch": None,
                "is_clean": True,
                "staged": [],
                "modified": [],
                "untracked": [],
                "ahead": 0,
                "behind": 0,
                "error": "Not a Git repository"
            }

        # Current branch
        branch_res = safe_run_command(["git", "branch", "--show-current"], cwd=repo_path, timeout=5)
        branch = branch_res.stdout.strip() if branch_res.exit_code == 0 else "HEAD"
        if not branch:
            # Fallback for detached HEAD
            head_res = safe_run_command(["git", "rev-parse", "--short", "HEAD"], cwd=repo_path, timeout=5)
            branch = head_res.stdout.strip() if head_res.exit_code == 0 else "unknown"

        # Porcelain status
        status_res = safe_run_command(["git", "status", "--porcelain=v1", "-b"], cwd=repo_path, timeout=10)
        staged = []
        modified = []
        untracked = []
        ahead = 0
        behind = 0

        if status_res.exit_code == 0:
            lines = status_res.stdout.splitlines()
            for line in lines:
                if line.startswith("##"):
                    # Check ahead/behind tracking
                    if "ahead " in line:
                        try:
                            ahead = int(line.split("ahead ")[1].split("]")[0].split(",")[0])
                        except Exception:
                            pass
                    if "behind " in line:
                        try:
                            behind = int(line.split("behind ")[1].split("]")[0].split(",")[0])
                        except Exception:
                            pass
                    continue

                if len(line) < 3:
                    continue
                index_code = line[0]
                worktree_code = line[1]
                filepath = line[3:].strip()

                if index_code in ("M", "A", "D", "R", "C"):
                    staged.append({"path": filepath, "status": index_code})
                if worktree_code in ("M", "D"):
                    modified.append({"path": filepath, "status": worktree_code})
                elif line.startswith("??"):
                    untracked.append(filepath)

        # Origin URL
        origin_res = safe_run_command(["git", "remote", "get-url", "origin"], cwd=repo_path, timeout=5)
        origin_url = origin_res.stdout.strip() if origin_res.exit_code == 0 else None

        is_clean = len(staged) == 0 and len(modified) == 0 and len(untracked) == 0

        return {
            "is_git": True,
            "origin": origin_url,
            "branch": branch,
            "is_clean": is_clean,
            "staged_count": len(staged),
            "modified_count": len(modified),
            "untracked_count": len(untracked),
            "staged": staged,
            "modified": modified,
            "untracked": untracked,
            "ahead": ahead,
            "behind": behind
        }

    @classmethod
    def get_recent_commits(cls, repo_path: str, count: int = 10) -> list[dict]:
        """Retrieve recent commits with hash, author, date, and message."""
        if not cls.is_git_repository(repo_path):
            return []

        # %h = short hash, %an = author name, %aI = author date ISO, %s = subject
        format_str = "%h%x09%an%x09%aI%x09%s"
        cmd = ["git", "log", f"-n{count}", f"--pretty=format:{format_str}"]
        res = safe_run_command(cmd, cwd=repo_path, timeout=10)

        commits = []
        if res.exit_code == 0 and res.stdout.strip():
            for line in res.stdout.splitlines():
                parts = line.split("\t", 3)
                if len(parts) == 4:
                    commits.append({
                        "hash": parts[0],
                        "author": parts[1],
                        "date": parts[2],
                        "message": parts[3]
                    })
        return commits

    @classmethod
    def get_diff(cls, repo_path: str, staged: bool = False, max_lines: int = 500) -> str:
        """Get working-tree or staged git diff, safely truncated."""
        if not cls.is_git_repository(repo_path):
            return ""

        cmd = ["git", "diff"]
        if staged:
            cmd.append("--staged")

        res = safe_run_command(cmd, cwd=repo_path, timeout=15)
        if res.exit_code != 0:
            return ""

        lines = res.stdout.splitlines()
        if len(lines) > max_lines:
            truncated = lines[:max_lines]
            truncated.append(f"\n... [Diff truncated: {len(lines) - max_lines} more lines]")
            return "\n".join(truncated)
        return res.stdout

    @classmethod
    def get_contributors(cls, repo_path: str) -> list[dict]:
        """Get list of contributors with commit counts."""
        if not cls.is_git_repository(repo_path):
            return []

        res = safe_run_command(["git", "shortlog", "-sn", "--no-merges", "HEAD"], cwd=repo_path, timeout=10)
        contributors = []
        if res.exit_code == 0 and res.stdout.strip():
            for line in res.stdout.splitlines():
                parts = line.strip().split(None, 1)
                if len(parts) == 2:
                    try:
                        contributors.append({
                            "commits": int(parts[0]),
                            "name": parts[1]
                        })
                    except Exception:
                        pass
        return contributors
