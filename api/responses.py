"""Aegis Intelligence - Standardized API Response Formatting

Ensures all responses conform strictly to the required envelope structure:
{
    "success": true | false,
    "request_id": "req_...",
    "data": { ... } | null,
    "error": { "code": "...", "message": "..." } | null
}
"""

import json
from datetime import date, datetime
from typing import Any, Optional

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime and set objects."""
    def default(self, obj):
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        if isinstance(obj, set):
            return sorted(list(obj))
        return super().default(obj)

def success_response(data: Any, request_id: str, status_code: int = 200) -> tuple[int, bytes]:
    """Build successful API response bytes."""
    envelope = {
        "success": True,
        "request_id": request_id,
        "data": data,
        "error": None
    }
    body = json.dumps(envelope, cls=DateTimeEncoder, indent=2).encode("utf-8")
    return status_code, body

def error_response(code: str, message: str, request_id: str, status_code: int = 400) -> tuple[int, bytes]:
    """Build error API response bytes."""
    envelope = {
        "success": False,
        "request_id": request_id,
        "data": None,
        "error": {
            "code": code,
            "message": message
        }
    }
    body = json.dumps(envelope, cls=DateTimeEncoder, indent=2).encode("utf-8")
    return status_code, body
