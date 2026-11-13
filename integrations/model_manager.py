"""Aegis Intelligence - Model Management Integration

Interacts with the Antigravity CLI to query verified available AI models,
inspect active settings, and switch default model configurations safely.
"""

import re
import json
import os
from pathlib import Path
from typing import Optional
from config import Config
from integrations.terminal import safe_run_command
from security.audit_log import log_audit

# Strip ANSI terminal escape sequences
ANSI_ESCAPE_RE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

# Verified catalog fallback if CLI network check is unavailable
KNOWN_MODEL_CATALOG = [
    {"id": "gemini-3.8-flash-high", "name": "Gemini 3.8 Flash (High)", "family": "Gemini"},
    {"id": "gemini-3.8-flash-medium", "name": "Gemini 3.8 Flash (Medium)", "family": "Gemini"},
    {"id": "gemini-3.8-flash-low", "name": "Gemini 3.8 Flash (Low)", "family": "Gemini"},
    {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6 (Thinking)", "family": "Claude"},
    {"id": "claude-opus-4-6-thinking", "name": "Claude Opus 4.6 (Thinking)", "family": "Claude"},
    {"id": "gpt-oss-120b-medium", "name": "GPT-OSS 120B (Medium)", "family": "GPT"},
]

class ModelManager:
    """Manages AI model discovery and selection for Antigravity CLI."""

    @classmethod
    def list_models(cls) -> list[dict]:
        """Query available models from 'agy models' and categorize by family."""
        res = safe_run_command([Config.AGY_BIN_PATH, "models"], timeout=15)
        models = []

        if res.exit_code == 0 and res.stdout:
            clean_out = ANSI_ESCAPE_RE.sub('', res.stdout)
            # Lines look like: "gemini-3.8-flash-high     Gemini 3.8 Flash (High)"
            for line in clean_out.splitlines():
                line = line.strip()
                if not line or "Fetching" in line or "available models" in line:
                    continue
                match = re.match(r'^([a-z0-9\.\-_]+)\s+(.+)$', line)
                if match:
                    model_id = match.group(1).strip()
                    model_name = match.group(2).strip()
                    family = "Other"
                    if "gemini" in model_id:
                        family = "Gemini"
                    elif "claude" in model_id:
                        family = "Claude"
                    elif "gpt" in model_id:
                        family = "GPT"

                    models.append({
                        "id": model_id,
                        "name": model_name,
                        "family": family
                    })

        # If CLI query produced no models, use verified catalog
        if not models:
            models = list(KNOWN_MODEL_CATALOG)

        return models

    @classmethod
    def get_active_model(cls) -> dict:
        """Read the currently configured active model from settings.json."""
        settings_path = Config.AGY_SETTINGS_PATH
        current_name = None
        if settings_path.is_file():
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    current_name = data.get("model")
            except Exception:
                pass

        available = cls.list_models()
        # Find matching model by name or ID
        if current_name:
            for m in available:
                if m["name"].lower() == current_name.lower() or m["id"].lower() == current_name.lower():
                    return {
                        "id": m["id"],
                        "name": m["name"],
                        "family": m["family"],
                        "source": "settings.json"
                    }

        # Fallback to default
        return {
            "id": Config.AGY_DEFAULT_MODEL,
            "name": current_name or Config.AGY_DEFAULT_MODEL,
            "family": "Gemini" if "gemini" in Config.AGY_DEFAULT_MODEL else "Other",
            "source": "default_configuration"
        }

    @classmethod
    def switch_model(cls, model_target: str) -> dict:
        """Switch the default model in settings.json to a verified model identifier."""
        available = cls.list_models()
        target_model = None

        # Look for exact ID match or display name match
        for m in available:
            if m["id"] == model_target or m["name"].lower() == model_target.lower():
                target_model = m
                break

        if not target_model:
            valid_ids = [m["id"] for m in available]
            raise ValueError(
                f"Model '{model_target}' is not supported or verified by the Antigravity CLI. "
                f"Available verified model IDs: {', '.join(valid_ids)}"
            )

        settings_path = Config.AGY_SETTINGS_PATH
        settings_data = {}
        if settings_path.is_file():
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings_data = json.load(f)
            except Exception:
                settings_data = {}

        # Set model display name in settings.json
        settings_data["model"] = target_model["name"]

        # Atomic write via temp file
        temp_path = settings_path.with_suffix(".tmp")
        try:
            settings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(settings_data, f, indent=2)
            temp_path.replace(settings_path)
        except Exception as e:
            if temp_path.exists():
                temp_path.unlink()
            raise RuntimeError(f"Failed to update settings.json: {e}")

        # Update in-memory default as well
        Config.AGY_DEFAULT_MODEL = target_model["id"]

        log_audit(
            action="MODEL_SWITCHED",
            actor="system",
            resource_type="model",
            resource_id=target_model["id"],
            details={"switched_to": target_model}
        )

        return {
            "success": True,
            "active_model": target_model,
            "message": f"Successfully switched active model to {target_model['name']} ({target_model['id']})."
        }
