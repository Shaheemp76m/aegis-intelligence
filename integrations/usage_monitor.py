"""Aegis Intelligence - Usage & Quota Monitoring

Reports execution metrics tracked in SQLite and explicitly distinguishes
supported session metrics from unsupported account-level quota endpoints.
"""

import json
from config import Config
from storage.database import db_session, rows_to_dict_list

class UsageMonitor:
    """Monitors AI token usage and accounts for Antigravity CLI capabilities."""

    @classmethod
    def get_usage_summary(cls) -> dict:
        """Return token usage metrics from database and explicit quota capability status."""
        total_jobs = 0
        total_input_tokens = 0
        total_output_tokens = 0
        total_thinking_tokens = 0
        total_tokens = 0
        model_breakdown = {}

        with db_session() as conn:
            rows = conn.execute(
                "SELECT model, token_usage FROM execution_jobs WHERE status = 'completed'"
            ).fetchall()

            for r in rows:
                total_jobs += 1
                model = r["model"] or "default"
                usage_raw = r["token_usage"] or "{}"
                try:
                    usage = json.loads(usage_raw)
                    inp = usage.get("input_tokens", 0)
                    out = usage.get("output_tokens", 0)
                    thk = usage.get("thinking_tokens", 0)
                    tot = usage.get("total_tokens", inp + out + thk)

                    total_input_tokens += inp
                    total_output_tokens += out
                    total_thinking_tokens += thk
                    total_tokens += tot

                    if model not in model_breakdown:
                        model_breakdown[model] = {
                            "jobs": 0,
                            "input_tokens": 0,
                            "output_tokens": 0,
                            "thinking_tokens": 0,
                            "total_tokens": 0
                        }
                    model_breakdown[model]["jobs"] += 1
                    model_breakdown[model]["input_tokens"] += inp
                    model_breakdown[model]["output_tokens"] += out
                    model_breakdown[model]["thinking_tokens"] += thk
                    model_breakdown[model]["total_tokens"] += tot
                except Exception:
                    pass

        return {
            "account_quota": {
                "status": "unsupported",
                "remaining_quota": "unavailable",
                "usage_percentage": "unavailable",
                "reset_time": "unavailable",
                "details": "Antigravity CLI v1.5.8 does not expose account billing or quota limits via CLI."
            },
            "local_session_usage": {
                "status": "supported",
                "total_completed_jobs": total_jobs,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_thinking_tokens": total_thinking_tokens,
                "total_tokens": total_tokens,
                "model_breakdown": model_breakdown
            }
        }
