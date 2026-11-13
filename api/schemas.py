"""Aegis Intelligence - API Request Schemas & Validation

Validates incoming JSON payloads and enforces parameter types without heavy dependencies.
"""

from typing import Any, Optional

class ValidationError(Exception):
    """Raised when request payload fails schema validation."""
    pass

def validate_dict(data: Any) -> dict:
    if not isinstance(data, dict):
        raise ValidationError("Request body must be a valid JSON object.")
    return data

def validate_required_string(data: dict, field: str) -> str:
    val = data.get(field)
    if not val or not isinstance(val, str) or not val.strip():
        raise ValidationError(f"Field '{field}' is required and must be a non-empty string.")
    return val.strip()

def validate_optional_string(data: dict, field: str, default: str = "") -> str:
    val = data.get(field)
    if val is None:
        return default
    if not isinstance(val, str):
        raise ValidationError(f"Field '{field}' must be a string if provided.")
    return val.strip()

def validate_optional_int(data: dict, field: str, default: Optional[int] = None) -> Optional[int]:
    val = data.get(field)
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        raise ValidationError(f"Field '{field}' must be an integer.")

def validate_optional_list(data: dict, field: str) -> list:
    val = data.get(field)
    if val is None:
        return []
    if not isinstance(val, list):
        raise ValidationError(f"Field '{field}' must be a list if provided.")
    return val
