"""Aegis Intelligence - Path Validation & Traversal Security

Enforces directory boundaries, prevents path traversal, and ensures operations
only occur within explicitly registered and validated project directories.
"""

import os
from pathlib import Path

# Paths that must NEVER be registered or targeted as project paths
FORBIDDEN_EXACT_PATHS = {
    "/",
    "/data",
    "/data/data",
    "/data/data/com.termux",
    "/data/data/com.termux/files",
    "/data/data/com.termux/files/usr",
    "/data/data/com.termux/files/usr/bin",
    "/data/data/com.termux/files/usr/etc",
    "/data/data/com.termux/files/usr/lib",
    "/data/data/com.termux/files/usr/include",
    "/data/data/com.termux/files/usr/share",
    "/data/data/com.termux/files/home",
    "/proc",
    "/sys",
    "/dev",
    "/etc",
    "/system",
    "/vendor",
}

FORBIDDEN_PREFIXES = (
    "/proc/",
    "/sys/",
    "/dev/",
    "/system/",
    "/vendor/",
    "/data/data/com.termux/files/usr/bin/",
    "/data/data/com.termux/files/usr/lib/",
    "/data/data/com.termux/files/usr/etc/",
    "/data/data/com.termux/files/usr/include/",
    "/data/data/com.termux/files/usr/share/",
)

class PathValidationError(Exception):
    """Raised when a path fails security or traversal checks."""
    pass

def canonicalize_path(raw_path: str) -> str:
    """Resolve symlinks, relative components, and return canonical absolute path."""
    if not raw_path or not isinstance(raw_path, str):
        raise PathValidationError("Path must be a non-empty string.")

    expanded = os.path.expanduser(raw_path.strip())
    absolute = os.path.abspath(expanded)
    canonical = os.path.realpath(absolute)
    return canonical

def is_safe_project_directory(raw_path: str) -> tuple[bool, str]:
    """Validate that a directory is safe to register as a project root.
    
    Returns (is_safe, error_message_or_canonical_path).
    """
    try:
        canonical = canonicalize_path(raw_path)
    except Exception as e:
        return False, f"Invalid path formatting: {e}"

    if canonical in FORBIDDEN_EXACT_PATHS:
        return False, f"Path '{canonical}' is a sensitive system or root directory and cannot be registered."

    for prefix in FORBIDDEN_PREFIXES:
        if canonical.startswith(prefix):
            return False, f"Path '{canonical}' resides within forbidden system path '{prefix}'."

    if not os.path.exists(canonical):
        return False, f"Path '{canonical}' does not exist on filesystem."

    if not os.path.isdir(canonical):
        return False, f"Path '{canonical}' is not a directory."

    if not os.access(canonical, os.R_OK):
        return False, f"Path '{canonical}' is not readable."

    return True, canonical

def validate_path_within_project(project_root: str, target_rel_or_abs: str) -> str:
    """Verify that a target file or folder resides strictly within the project directory.
    
    Prevents path traversal attacks like '../../foo' or symlink escapes.
    Returns canonical path if valid; raises PathValidationError otherwise.
    """
    root_canonical = canonicalize_path(project_root)
    
    if os.path.isabs(target_rel_or_abs):
        target_canonical = canonicalize_path(target_rel_or_abs)
    else:
        target_combined = os.path.join(root_canonical, target_rel_or_abs)
        target_canonical = canonicalize_path(target_combined)

    # Ensure target_canonical is within root_canonical or is root_canonical itself
    if target_canonical == root_canonical:
        return target_canonical

    # Must start with root_canonical + os.sep
    expected_prefix = root_canonical.rstrip(os.path.sep) + os.path.sep
    if not target_canonical.startswith(expected_prefix):
        raise PathValidationError(
            f"Path traversal detected: '{target_rel_or_abs}' resolves to '{target_canonical}', "
            f"which is outside project root '{root_canonical}'."
        )

    return target_canonical
