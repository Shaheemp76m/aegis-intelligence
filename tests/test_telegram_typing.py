"""Aegis Intelligence - Telegram Typing Service Tests

Tests background typing indicator heartbeats, token resolution,
HTTP dispatch, and lifecycle management within an isolated test environment.
"""

import os
import time
import unittest
from unittest.mock import patch, MagicMock
from tests.isolated_test_case import IsolatedTestCase
from integrations.telegram_typing import (
    TelegramTypingService,
    send_chat_action,
    get_telegram_token
)


class TestTelegramTyping(IsolatedTestCase):
    """Test suite for Telegram typing indicator heartbeat service."""

    def setUp(self):
        super().setUp()
        TelegramTypingService.stop_all()

    def tearDown(self):
        TelegramTypingService.stop_all()
        super().tearDown()

    def test_get_telegram_token_from_env(self):
        """Test retrieving bot token from environment variable."""
        with patch.dict(os.environ, {"TELEGRAM_BOT_TOKEN": "123456:TEST_TOKEN_ENV"}):
            token = get_telegram_token()
            self.assertEqual(token, "123456:TEST_TOKEN_ENV")

    def test_get_telegram_token_from_file(self):
        """Test retrieving bot token from file when env var is not present."""
        token_path = os.path.join(self._temp_data_dir, ".telegram_token")
        with open(token_path, "w", encoding="utf-8") as f:
            f.write("654321:TEST_TOKEN_FILE\n")

        with patch.dict(os.environ, {}, clear=True):
            with patch("integrations.telegram_typing.TELEGRAM_TOKEN_FILE", token_path):
                token = get_telegram_token()
                self.assertEqual(token, "654321:TEST_TOKEN_FILE")

    def test_get_telegram_token_none_when_empty(self):
        """Test retrieving token when neither env var nor file is present."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("integrations.telegram_typing.TELEGRAM_TOKEN_FILE", "/nonexistent/token"):
                token = get_telegram_token()
                self.assertIsNone(token)

    @patch("urllib.request.urlopen")
    def test_send_chat_action_success(self, mock_urlopen):
        """Test sending chat action with HTTP 200 response."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        result = send_chat_action("12345678", "typing", token="fake_token")
        self.assertTrue(result)
        mock_urlopen.assert_called_once()
        req = mock_urlopen.call_args[0][0]
        self.assertIn("https://api.telegram.org/botfake_token/sendChatAction", req.full_url)

    def test_send_chat_action_missing_token_or_chat_id(self):
        """Test that missing token or chat_id returns False without network request."""
        self.assertFalse(send_chat_action("", "typing", token="fake_token"))
        self.assertFalse(send_chat_action("12345", "typing", token=None))

    @patch("urllib.request.urlopen")
    def test_send_chat_action_http_error(self, mock_urlopen):
        """Test send_chat_action handles network/HTTP errors cleanly without raising."""
        mock_urlopen.side_effect = Exception("Connection timed out")
        result = send_chat_action("12345678", "typing", token="fake_token")
        self.assertFalse(result)

    @patch("integrations.telegram_typing.send_chat_action")
    def test_heartbeat_lifecycle(self, mock_send):
        """Test starting, monitoring, and stopping a background typing heartbeat."""
        mock_send.return_value = True
        session_id = "sess_typing_test_01"
        chat_id = "5170203589"

        with patch("integrations.telegram_typing.get_telegram_token", return_value="fake_token"):
            started = TelegramTypingService.start_heartbeat(
                session_id,
                chat_id,
                interval=0.05,
                max_duration=2.0
            )
            self.assertTrue(started)
            self.assertTrue(TelegramTypingService.is_active(session_id))

            # Allow worker loop to pulse
            time.sleep(0.15)
            self.assertGreaterEqual(mock_send.call_count, 1)

            # Stop heartbeat
            stopped = TelegramTypingService.stop_heartbeat(session_id)
            self.assertTrue(stopped)
            self.assertFalse(TelegramTypingService.is_active(session_id))

    @patch("integrations.telegram_typing.send_chat_action")
    def test_heartbeat_restart_and_stop_all(self, mock_send):
        """Test starting multiple heartbeats and stop_all functionality."""
        mock_send.return_value = True
        with patch("integrations.telegram_typing.get_telegram_token", return_value="fake_token"):
            TelegramTypingService.start_heartbeat("sess_a", "chat_1", interval=0.1)
            TelegramTypingService.start_heartbeat("sess_b", "chat_2", interval=0.1)

            self.assertTrue(TelegramTypingService.is_active("sess_a"))
            self.assertTrue(TelegramTypingService.is_active("sess_b"))

            count = TelegramTypingService.stop_all()
            self.assertEqual(count, 2)
            self.assertFalse(TelegramTypingService.is_active("sess_a"))
            self.assertFalse(TelegramTypingService.is_active("sess_b"))

    def test_heartbeat_invalid_args(self):
        """Test invalid parameters return False without crashing."""
        self.assertFalse(TelegramTypingService.start_heartbeat("", "chat_1"))
        self.assertFalse(TelegramTypingService.start_heartbeat("sess_1", ""))
        self.assertFalse(TelegramTypingService.stop_heartbeat(""))


if __name__ == "__main__":
    unittest.main()
