"""Aegis Intelligence - Configuration Module

Handles environment variable loading, default values, and runtime configuration
for Termux Android execution environment.
"""

import os
import secrets
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent
HOME_DIR = Path(os.path.expanduser("~"))

def _load_env_file(filepath: Path) -> None:
    """Load key-value pairs from a .env file into os.environ if not already set."""
    if not filepath.is_file():
        return
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("\"'")
                    if key and key not in os.environ:
                        os.environ[key] = val
    except Exception:
        pass

# Attempt to load .env from project directory or HOME
_load_env_file(BASE_DIR / ".env")
_load_env_file(HOME_DIR / ".aegis.env")

class Config:
    """Aegis Configuration container."""

    # Server binding (strictly localhost for Termux security)
    HOST: str = os.getenv("AEGIS_HOST", "127.0.0.1")
    PORT: int = int(os.getenv("AEGIS_PORT", "8765"))

    # Storage and Directories
    DATA_DIR: Path = Path(os.getenv("AEGIS_DATA_DIR", str(BASE_DIR / "data")))
    DB_PATH: Path = Path(os.getenv("AEGIS_DB_PATH", str(DATA_DIR / "aegis.db")))
    LOGS_DIR: Path = DATA_DIR / "logs"
    REPORTS_DIR: Path = DATA_DIR / "reports"
    MEMORY_DIR: Path = DATA_DIR / "memory"
    PROJECTS_DIR: Path = DATA_DIR / "projects"
    TOKEN_FILE: Path = DATA_DIR / ".api_token"

    # Known placeholder tokens from templates that should not be used in runtime
    PLACEHOLDER_TOKENS: set[str] = {
        "your_secure_random_token_here_change_me",
        "change_me",
        "your_token_here",
    }

    # Security
    API_TOKEN: str = ""

    # Antigravity CLI Execution
    AGY_BIN_PATH: str = os.getenv("AGY_BIN_PATH", "agy")
    AGY_DEFAULT_TIMEOUT: int = int(os.getenv("AGY_DEFAULT_TIMEOUT", "120"))
    AGY_DEFAULT_MODEL: str = os.getenv("AGY_DEFAULT_MODEL", "gemini-3.8-flash-high")
    AGY_SETTINGS_PATH: Path = HOME_DIR / ".gemini" / "antigravity-cli" / "settings.json"

    # Approvals & Autonomy
    APPROVAL_EXPIRY_SECONDS: int = int(os.getenv("APPROVAL_EXPIRY_SECONDS", "900"))  # 15 min
    MAX_REQUEST_BODY_BYTES: int = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(5 * 1024 * 1024))) # 5MB

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def load_api_token(cls) -> str:
        """Resolve and enforce API token from environment or persistent file."""
        env_token = os.getenv("AEGIS_API_TOKEN", "").strip()
        if env_token and env_token not in cls.PLACEHOLDER_TOKENS:
            cls.API_TOKEN = env_token
            # Sync to token file so local clients and n8n reading .api_token have the matching token
            try:
                cls.TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
                cls.TOKEN_FILE.write_text(cls.API_TOKEN, encoding="utf-8")
                cls.TOKEN_FILE.chmod(0o600)
            except Exception:
                pass
            return cls.API_TOKEN

        # Check existing token file
        if cls.TOKEN_FILE.is_file():
            file_token = cls.TOKEN_FILE.read_text(encoding="utf-8").strip()
            if file_token and file_token not in cls.PLACEHOLDER_TOKENS:
                cls.API_TOKEN = file_token
                try:
                    cls.TOKEN_FILE.chmod(0o600)
                except Exception:
                    pass
                return cls.API_TOKEN

        # Generate new cryptographically secure token (48 hex chars)
        cls.TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        cls.API_TOKEN = secrets.token_hex(24)
        try:
            cls.TOKEN_FILE.write_text(cls.API_TOKEN, encoding="utf-8")
            cls.TOKEN_FILE.chmod(0o600)
        except Exception:
            pass
        return cls.API_TOKEN

    @classmethod
    def ensure_directories(cls) -> None:
        """Ensure all required runtime data directories exist."""
        for d in [cls.DATA_DIR, cls.LOGS_DIR, cls.REPORTS_DIR, cls.MEMORY_DIR, cls.PROJECTS_DIR]:
            d.mkdir(parents=True, exist_ok=True)

# Ensure data directories exist and resolve API token on module import
Config.ensure_directories()
Config.load_api_token()
