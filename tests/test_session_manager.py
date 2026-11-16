"""Aegis Intelligence - Session Manager Tests

Verifies persistent conversation session tracking, context formatting,
user/chat isolation, message deduplication, and dispatcher integration.
"""

from tests.isolated_test_case import IsolatedTestCase
from intelligence.session_manager import SessionManager
from core.tool_router import ToolRouter


class TestSessionManager(IsolatedTestCase):
    """Test suite for conversation session management."""

    def setUp(self):
        super().setUp()
        from storage.database import db_session
        with db_session() as conn:
            conn.execute("DELETE FROM conversation_sessions")
            conn.execute("DELETE FROM processed_telegram_messages")

    def test_get_or_create_fresh_session(self):
        """Verify that a new session is created when none exists."""
        res = SessionManager.get_or_create_session(
            telegram_chat_id="12345",
            telegram_user_id="12345",
            user_prompt="Hello Aegis"
        )
        self.assertIsNotNone(res["session_id"])
        self.assertTrue(res["session_id"].startswith("sess_"))
        self.assertEqual(res["telegram_chat_id"], "12345")
        self.assertEqual(res["telegram_user_id"], "12345")
        self.assertEqual(res["status"], "active")
        self.assertTrue(res["is_new"])
        self.assertFalse(res["is_duplicate"])
        self.assertEqual(res["turns_count"], 0)
        self.assertEqual(res["context_history"], "")

    def test_get_or_create_existing_active_session(self):
        """Verify that an existing active session is returned for subsequent messages."""
        s1 = SessionManager.get_or_create_session(
            telegram_chat_id="12345",
            telegram_user_id="12345"
        )
        s2 = SessionManager.get_or_create_session(
            telegram_chat_id="12345",
            telegram_user_id="12345"
        )
        self.assertEqual(s1["session_id"], s2["session_id"])
        self.assertFalse(s2["is_new"])

    def test_user_chat_isolation(self):
        """Verify that different users/chats get isolated sessions."""
        s1 = SessionManager.get_or_create_session(
            telegram_chat_id="user_1",
            telegram_user_id="user_1"
        )
        s2 = SessionManager.get_or_create_session(
            telegram_chat_id="user_2",
            telegram_user_id="user_2"
        )
        self.assertNotEqual(s1["session_id"], s2["session_id"])

    def test_add_turns_and_context_history(self):
        """Verify recording conversation turns and formatting context history."""
        s = SessionManager.get_or_create_session(
            telegram_chat_id="12345",
            telegram_user_id="12345"
        )
        sid = s["session_id"]

        SessionManager.add_turn(sid, "What is Aegis?", "Aegis is an autonomous Devops assistant.")
        SessionManager.add_turn(sid, "List my projects", "Found 1 project: Home Projects.")

        updated = SessionManager.get_or_create_session(
            telegram_chat_id="12345",
            telegram_user_id="12345"
        )
        self.assertEqual(updated["turns_count"], 2)
        self.assertIn("What is Aegis?", updated["context_history"])
        self.assertIn("Home Projects", updated["context_history"])

    def test_close_session_and_restart(self):
        """Verify closing a session and then starting a new one."""
        s1 = SessionManager.get_or_create_session(
            telegram_chat_id="12345",
            telegram_user_id="12345"
        )
        close_res = SessionManager.close_session(
            telegram_chat_id="12345",
            telegram_user_id="12345",
            status="completed"
        )
        self.assertEqual(close_res["closed_count"], 1)

        # Next call should create a fresh session
        s2 = SessionManager.get_or_create_session(
            telegram_chat_id="12345",
            telegram_user_id="12345"
        )
        self.assertNotEqual(s1["session_id"], s2["session_id"])
        self.assertTrue(s2["is_new"])

    def test_message_deduplication(self):
        """Verify that duplicate message IDs are detected."""
        is_dup_1 = SessionManager.check_dedup("chat_99", "msg_1001")
        self.assertFalse(is_dup_1)

        # Same message again
        is_dup_2 = SessionManager.check_dedup("chat_99", "msg_1001")
        self.assertTrue(is_dup_2)

        # Different message
        is_dup_3 = SessionManager.check_dedup("chat_99", "msg_1002")
        self.assertFalse(is_dup_3)

    def test_dispatcher_session_integration(self):
        """Verify routing session actions through the tool router."""
        res = ToolRouter.dispatch(
            "session_get_or_create",
            params={
                "telegram_chat_id": "777",
                "telegram_user_id": "777",
                "user_prompt": "Run status"
            }
        )
        self.assertIn("session_id", res)
        sid = res["session_id"]

        turn_res = ToolRouter.dispatch(
            "session_add_turn",
            params={
                "session_id": sid,
                "user_text": "Run status",
                "agent_output": "All systems nominal."
            }
        )
        self.assertEqual(turn_res["status"], "success")

        close_res = ToolRouter.dispatch(
            "session_close",
            params={"session_id": sid}
        )
        self.assertEqual(close_res["closed_count"], 1)
