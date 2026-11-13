"""Aegis Intelligence - Authentication Security

Implements constant-time token verification for local HTTP requests from n8n.
"""

import hmac
from config import Config

class AuthenticationError(Exception):
    """Raised when request authentication fails."""
    pass

def extract_token(headers: dict) -> str:
    """Extract auth token from X-Aegis-Token or Authorization: Bearer <token> (case-insensitive)."""
    if not isinstance(headers, dict):
        return ""

    # Case-insensitive header lookup
    norm = {str(k).lower(): str(v) for k, v in headers.items()}

    # 1. Check X-Aegis-Token
    token = norm.get("x-aegis-token")
    if token:
        return token.strip()

    # 2. Check Authorization header
    auth_header = norm.get("authorization")
    if auth_header:
        parts = auth_header.strip().split(None, 1)
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        # If no scheme prefix, treat entire value as raw token
        return auth_header.strip()

    return ""

def verify_token(provided_token: str) -> bool:
    """Verify provided token against configured token using constant-time comparison."""
    if not provided_token or not Config.API_TOKEN:
        return False

    return hmac.compare_digest(
        provided_token.strip().encode("utf-8"),
        Config.API_TOKEN.strip().encode("utf-8")
    )

def authenticate_request(headers: dict) -> bool:
    """Verify incoming request headers; raises AuthenticationError on failure."""
    token = extract_token(headers)
    if not token:
        raise AuthenticationError("Missing authentication token in request headers.")

    if not verify_token(token):
        raise AuthenticationError("Invalid authentication token.")

    return True
