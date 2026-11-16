"""Aegis Intelligence - Telegram Conversation Session Manager

Provides persistent, multi-turn conversation session tracking in SQLite.
Enforces user/chat isolation, prevents state corruption, supports deduplication,
and maintains rolling conversation context across independent executions.
"""

import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from storage.database import db_session, row_to_dict
from security.audit_log import log_audit
from intelligence.project_analyzer import ProjectAnalyzer
from integrations.telegram_typing import TelegramTypingService


class SessionManager:
    """Manages Telegram conversation sessions and message deduplication."""

    @classmethod
    def check_dedup(cls, chat_id: str, message_id: str) -> bool:
        """Check if a Telegram message ID has already been processed for this chat.
        
        Returns True if duplicate (already processed), False if fresh.
        """
        if not chat_id or not message_id:
            return False

        key = f"{str(chat_id).strip()}_{str(message_id).strip()}"
        now_iso = datetime.now(timezone.utc).isoformat()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

        with db_session() as conn:
            # Purge messages older than 1 hour to prevent table bloat
            conn.execute("DELETE FROM processed_telegram_messages WHERE processed_at < ?", (cutoff,))

            existing = conn.execute(
                "SELECT message_id FROM processed_telegram_messages WHERE message_id = ?",
                (key,)
            ).fetchone()

            if existing:
                return True

            conn.execute(
                "INSERT OR REPLACE INTO processed_telegram_messages (message_id, chat_id, processed_at) VALUES (?, ?, ?)",
                (key, str(chat_id).strip(), now_iso)
            )
            return False

    @classmethod
    def get_active_session(cls, telegram_chat_id: str, telegram_user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve the currently active session for a given Telegram chat and user."""
        chat_id_str = str(telegram_chat_id).strip()
        user_id_str = str(telegram_user_id).strip()

        with db_session() as conn:
            row = conn.execute(
                """
                SELECT * FROM conversation_sessions
                WHERE telegram_chat_id = ? AND telegram_user_id = ? AND status = 'active'
                ORDER BY updated_at DESC LIMIT 1
                """,
                (chat_id_str, user_id_str)
            ).fetchone()

            if not row:
                return None

            data = row_to_dict(row)
            try:
                data["context"] = json.loads(data.get("context_json", "[]"))
            except Exception:
                data["context"] = []
            data["turns_count"] = len(data["context"])
            return data

    @classmethod
    def get_or_create_session(
        cls,
        telegram_chat_id: str,
        telegram_user_id: str,
        project_id: Optional[str] = None,
        message_id: Optional[str] = None,
        user_prompt: str = ""
    ) -> Dict[str, Any]:
        """Get an existing active conversation session or create a new one.
        
        Also checks message deduplication if message_id is provided.
        """
        chat_id_str = str(telegram_chat_id).strip()
        user_id_str = str(telegram_user_id).strip()

        if not chat_id_str or not user_id_str:
            raise ValueError("telegram_chat_id and telegram_user_id are required.")

        # Check deduplication
        is_duplicate = False
        if message_id:
            is_duplicate = cls.check_dedup(chat_id_str, str(message_id).strip())

        active = cls.get_active_session(chat_id_str, user_id_str)
        now_iso = datetime.now(timezone.utc).isoformat()

        if active:
            # Build text summary of previous context for easy LLM consumption
            context_history = cls._format_context_history(active.get("context", []))
            if not is_duplicate:
                TelegramTypingService.start_heartbeat(active["id"], active["telegram_chat_id"])
            return {
                "session_id": active["id"],
                "telegram_chat_id": active["telegram_chat_id"],
                "telegram_user_id": active["telegram_user_id"],
                "project_id": active.get("project_id"),
                "status": active["status"],
                "is_new": False,
                "is_duplicate": is_duplicate,
                "turns_count": active.get("turns_count", 0),
                "context_history": context_history,
                "raw_context": active.get("context", []),
                "user_prompt": user_prompt,
                "created_at": active["created_at"],
                "updated_at": active["updated_at"]
            }

        # Determine project_id if not provided
        resolved_pid = project_id
        if not resolved_pid:
            active_proj = ProjectAnalyzer.get_active_project()
            if active_proj:
                resolved_pid = active_proj.get("id")

        new_id = f"sess_{uuid.uuid4().hex[:8]}"

        with db_session() as conn:
            conn.execute(
                """
                INSERT INTO conversation_sessions (
                    id, telegram_chat_id, telegram_user_id, project_id,
                    status, context_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, 'active', '[]', ?, ?)
                """,
                (new_id, chat_id_str, user_id_str, resolved_pid, now_iso, now_iso)
            )

        if not is_duplicate:
            TelegramTypingService.start_heartbeat(new_id, chat_id_str)

        log_audit(
            action="SESSION_CREATED",
            actor=f"tg_{user_id_str}",
            resource_type="session",
            resource_id=new_id,
            details={"chat_id": chat_id_str, "project_id": resolved_pid}
        )

        return {
            "session_id": new_id,
            "telegram_chat_id": chat_id_str,
            "telegram_user_id": user_id_str,
            "project_id": resolved_pid,
            "status": "active",
            "is_new": True,
            "is_duplicate": is_duplicate,
            "turns_count": 0,
            "context_history": "",
            "raw_context": [],
            "user_prompt": user_prompt,
            "created_at": now_iso,
            "updated_at": now_iso
        }

    @classmethod
    def add_turn(
        cls,
        session_id: str,
        user_text: str,
        agent_output: str,
        max_turns: int = 15
    ) -> Dict[str, Any]:
        """Append a completed dialogue turn (user text & agent output) to session context."""
        now_iso = datetime.now(timezone.utc).isoformat()

        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM conversation_sessions WHERE id = ?",
                (session_id,)
            ).fetchone()

            if not row:
                raise ValueError(f"Session '{session_id}' not found.")

            session_data = row_to_dict(row)
            try:
                context = json.loads(session_data.get("context_json", "[]"))
            except Exception:
                context = []

            # Append new turn
            context.append({
                "user": user_text.strip(),
                "agent": agent_output.strip(),
                "timestamp": now_iso
            })

            # Retain only the most recent max_turns
            if len(context) > max_turns:
                context = context[-max_turns:]

            conn.execute(
                "UPDATE conversation_sessions SET context_json = ?, updated_at = ? WHERE id = ?",
                (json.dumps(context), now_iso, session_id)
            )

        # Stop typing indicator when turn completes
        TelegramTypingService.stop_heartbeat(session_id)

        return {
            "session_id": session_id,
            "turns_count": len(context),
            "updated_at": now_iso,
            "status": "success"
        }

    @classmethod
    def close_session(
        cls,
        session_id: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        telegram_user_id: Optional[str] = None,
        status: str = "completed",
        reason: str = ""
    ) -> Dict[str, Any]:
        """Close an active conversation session, marking it completed or cancelled."""
        if status not in ["completed", "cancelled"]:
            status = "completed"

        now_iso = datetime.now(timezone.utc).isoformat()
        closed_ids = []

        with db_session() as conn:
            if session_id:
                row = conn.execute(
                    "SELECT id, telegram_user_id FROM conversation_sessions WHERE id = ?",
                    (session_id,)
                ).fetchone()
                if row:
                    conn.execute(
                        "UPDATE conversation_sessions SET status = ?, updated_at = ? WHERE id = ?",
                        (status, now_iso, session_id)
                    )
                    closed_ids.append(session_id)
            elif telegram_chat_id and telegram_user_id:
                chat_id_str = str(telegram_chat_id).strip()
                user_id_str = str(telegram_user_id).strip()
                rows = conn.execute(
                    """
                    SELECT id FROM conversation_sessions
                    WHERE telegram_chat_id = ? AND telegram_user_id = ? AND status = 'active'
                    """,
                    (chat_id_str, user_id_str)
                ).fetchall()
                for r in rows:
                    closed_ids.append(r["id"])
                if closed_ids:
                    conn.execute(
                        """
                        UPDATE conversation_sessions SET status = ?, updated_at = ?
                        WHERE telegram_chat_id = ? AND telegram_user_id = ? AND status = 'active'
                        """,
                        (status, now_iso, chat_id_str, user_id_str)
                    )

        for cid in closed_ids:
            TelegramTypingService.stop_heartbeat(cid)
            log_audit(
                action="SESSION_CLOSED",
                actor="system",
                resource_type="session",
                resource_id=cid,
                details={"status": status, "reason": reason}
            )

        return {
            "closed_count": len(closed_ids),
            "closed_ids": closed_ids,
            "status": status,
            "updated_at": now_iso
        }

    @classmethod
    def get_session(cls, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve full details of a specific session by ID."""
        with db_session() as conn:
            row = conn.execute(
                "SELECT * FROM conversation_sessions WHERE id = ?",
                (session_id,)
            ).fetchone()
            if not row:
                return None
            data = row_to_dict(row)
            try:
                data["context"] = json.loads(data.get("context_json", "[]"))
            except Exception:
                data["context"] = []
            data["turns_count"] = len(data["context"])
            return data

    @classmethod
    def list_sessions(
        cls,
        telegram_chat_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """List recent conversation sessions with optional filters."""
        query = "SELECT * FROM conversation_sessions WHERE 1=1"
        params = []

        if telegram_chat_id:
            query += " AND telegram_chat_id = ?"
            params.append(str(telegram_chat_id).strip())
        if status:
            query += " AND status = ?"
            params.append(status.strip())

        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)

        with db_session() as conn:
            rows = conn.execute(query, params).fetchall()
            results = []
            for r in rows:
                item = row_to_dict(r)
                try:
                    item["context"] = json.loads(item.get("context_json", "[]"))
                except Exception:
                    item["context"] = []
                item["turns_count"] = len(item["context"])
                results.append(item)
            return results

    @staticmethod
    def _format_context_history(turns: List[Dict[str, str]]) -> str:
        """Format previous conversation turns into a clean text briefing for LLM context."""
        if not turns:
            return ""
        lines = []
        for i, turn in enumerate(turns, start=1):
            user_msg = turn.get("user", "").strip()
            agent_msg = turn.get("agent", "").strip()
            if len(agent_msg) > 300:
                agent_msg = agent_msg[:300] + "... [truncated]"
            lines.append(f"[Turn {i}] User: {user_msg}\nAgent: {agent_msg}")
        return "\n".join(lines)
