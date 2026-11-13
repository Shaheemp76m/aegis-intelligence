"""Aegis Intelligence - Filesystem Integration Module

Safe inspection of project directory structures, configuration detection,
file hierarchy analysis, and safe file reading.
"""

import os
import json
from pathlib import Path
from typing import Optional
from security.path_validator import validate_path_within_project, canonicalize_path

# Extensions to ignore during project scanning
IGNORE_DIRS = {
    ".git", ".svn", ".hg", "node_modules", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".venv", "venv", "env", ".env", "dist", "build",
    ".idea", ".vscode", ".next", ".nuxt", "target"
}

IGNORE_EXTENSIONS = {
    ".pyc", ".pyo", ".so", ".dll", ".dylib", ".exe", ".bin", ".iso",
    ".tar", ".gz", ".zip", ".7z", ".png", ".jpg", ".jpeg", ".gif",
    ".ico", ".webp", ".pdf", ".mp4", ".mp3", ".woff", ".woff2", ".ttf"
}

CONFIG_FILE_CANDIDATES = {
    "package.json", "tsconfig.json", "vite.config.ts", "vite.config.js",
    "webpack.config.js", "pyproject.toml", "setup.py", "requirements.txt",
    "Pipfile", "poetry.lock", "Cargo.toml", "go.mod", "Makefile",
    "Dockerfile", "docker-compose.yml", "tailwind.config.js", ".eslintrc.json"
}

DOC_FILE_CANDIDATES = {
    "README.md", "README", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE",
    "ARCHITECTURE.md", "SPEC.md", "ROADMAP.md"
}

class FilesystemIntegration:
    """Safe project filesystem explorer."""

    @classmethod
    def inspect_directory(
        cls,
        project_root: str,
        max_depth: int = 3,
        max_files: int = 300
    ) -> dict:
        """Scan project directory structure safely within bounds."""
        canonical_root = canonicalize_path(project_root)
        total_files = 0
        total_bytes = 0
        tree = []
        extension_counts = {}
        config_files_found = []
        doc_files_found = []

        root_depth = canonical_root.rstrip(os.path.sep).count(os.path.sep)

        for current_root, dirs, files in os.walk(canonical_root, followlinks=False):
            # Exclude ignored directories in-place
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]

            current_depth = current_root.count(os.path.sep) - root_depth
            if current_depth > max_depth:
                dirs[:] = []
                continue

            rel_root = os.path.relpath(current_root, canonical_root)
            if rel_root == ".":
                rel_root = ""

            for fname in files:
                total_files += 1
                rel_file_path = os.path.join(rel_root, fname) if rel_root else fname
                full_path = os.path.join(current_root, fname)

                # Track size safely
                try:
                    fsize = os.path.getsize(full_path)
                    total_bytes += fsize
                except Exception:
                    fsize = 0

                # Check extensions
                _, ext = os.path.splitext(fname)
                ext = ext.lower()
                if ext:
                    extension_counts[ext] = extension_counts.get(ext, 0) + 1

                # Detect config and docs
                if fname in CONFIG_FILE_CANDIDATES:
                    config_files_found.append(rel_file_path)
                if fname in DOC_FILE_CANDIDATES or fname.lower().startswith("readme"):
                    doc_files_found.append(rel_file_path)

                if len(tree) < max_files:
                    tree.append({
                        "path": rel_file_path,
                        "size": fsize,
                        "depth": current_depth
                    })

        return {
            "root_path": canonical_root,
            "total_files": total_files,
            "total_bytes": total_bytes,
            "total_size_human": cls.format_bytes(total_bytes),
            "tree_sample": tree[:max_files],
            "tree_truncated": total_files > max_files,
            "extensions": extension_counts,
            "config_files": sorted(config_files_found),
            "doc_files": sorted(doc_files_found)
        }

    @classmethod
    def get_recently_modified_files(cls, project_root: str, limit: int = 15) -> list[dict]:
        """Find recently modified files within project boundary."""
        canonical_root = canonicalize_path(project_root)
        files_with_mtime = []

        for current_root, dirs, files in os.walk(canonical_root, followlinks=False):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]

            rel_root = os.path.relpath(current_root, canonical_root)
            if rel_root == ".":
                rel_root = ""

            for fname in files:
                _, ext = os.path.splitext(fname)
                if ext.lower() in IGNORE_EXTENSIONS:
                    continue

                full_path = os.path.join(current_root, fname)
                try:
                    stat = os.stat(full_path)
                    rel_path = os.path.join(rel_root, fname) if rel_root else fname
                    files_with_mtime.append({
                        "path": rel_path,
                        "mtime": stat.st_mtime,
                        "size": stat.st_size
                    })
                except Exception:
                    pass

        files_with_mtime.sort(key=lambda x: x["mtime"], reverse=True)
        import datetime
        results = []
        for f in files_with_mtime[:limit]:
            results.append({
                "path": f["path"],
                "modified_at": datetime.datetime.fromtimestamp(f["mtime"], tz=datetime.timezone.utc).isoformat(),
                "size": f["size"]
            })
        return results

    @classmethod
    def read_file_content(cls, project_root: str, rel_path: str, max_bytes: int = 65536) -> str:
        """Read content of a file strictly inside the project root."""
        safe_path = validate_path_within_project(project_root, rel_path)
        if not os.path.isfile(safe_path):
            raise FileNotFoundError(f"File '{rel_path}' does not exist inside project.")

        with open(safe_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(max_bytes)

    @classmethod
    def detect_tech_stack(cls, project_root: str) -> tuple[list[str], list[str]]:
        """Infer programming languages and technology stack from project files."""
        canonical_root = canonicalize_path(project_root)
        languages = set()
        stack = set()

        # Check Node.js / TypeScript / React / Vue
        pkg_json = os.path.join(canonical_root, "package.json")
        if os.path.isfile(pkg_json):
            stack.add("Node.js")
            languages.add("JavaScript")
            try:
                with open(pkg_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    if "typescript" in deps:
                        languages.add("TypeScript")
                        stack.add("TypeScript")
                    if "react" in deps:
                        stack.add("React")
                    if "vue" in deps:
                        stack.add("Vue")
                    if "svelte" in deps:
                        stack.add("Svelte")
                    if "vite" in deps:
                        stack.add("Vite")
                    if "tailwindcss" in deps:
                        stack.add("TailwindCSS")
                    if "express" in deps:
                        stack.add("Express")
                    if "next" in deps:
                        stack.add("Next.js")
            except Exception:
                pass

        # Check Python
        for py_indicator in ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"]:
            if os.path.isfile(os.path.join(canonical_root, py_indicator)):
                languages.add("Python")
                stack.add("Python")
                break

        # Check Rust
        if os.path.isfile(os.path.join(canonical_root, "Cargo.toml")):
            languages.add("Rust")
            stack.add("Cargo")

        # Check Go
        if os.path.isfile(os.path.join(canonical_root, "go.mod")):
            languages.add("Go")

        # Fallback extension inspection
        for _, _, files in os.walk(canonical_root):
            for fname in files:
                if fname.endswith(".py"):
                    languages.add("Python")
                elif fname.endswith(".ts") or fname.endswith(".tsx"):
                    languages.add("TypeScript")
                elif fname.endswith(".js") or fname.endswith(".jsx"):
                    languages.add("JavaScript")
                elif fname.endswith(".sh"):
                    languages.add("Shell")
                elif fname.endswith(".rs"):
                    languages.add("Rust")
                elif fname.endswith(".go"):
                    languages.add("Go")
                elif fname.endswith(".html"):
                    languages.add("HTML")
                elif fname.endswith(".css"):
                    languages.add("CSS")
            break # only check top level for fallback

        return sorted(list(languages)), sorted(list(stack))

    @staticmethod
    def format_bytes(num_bytes: int) -> str:
        """Format raw byte counts to human readable form."""
        for unit in ["B", "KB", "MB", "GB"]:
            if abs(num_bytes) < 1024.0:
                return f"{num_bytes:3.1f} {unit}"
            num_bytes /= 1024.0
        return f"{num_bytes:.1f} TB"
