"""Aegis Intelligence - Telegram Native Typing Indicator Service

Provides non-blocking background heartbeat for Telegram 'typing' chat actions.
Refreshes approximately every 4 seconds to maintain the typing indicator in the
user's Telegram client during Gemini AI reasoning and long-running Antigravity jobs.
Stops cleanly when the agent finishes, fails, or the session is closed.
"""

import os
import json
import logging
import threading
import time
import urllib.request
import urllib.error
from typing import Optional, Dict

logger = logging.getLogger("aegis.telegram_typing")

# Path to local Telegram token (0600 permissions, Git-ignored)
TELEGRAM_TOKEN_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", ".telegram_token")


def get_telegram_token() -> Optional[str]:
    """Retrieve Telegram Bot token from environment or data/.telegram_token."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if token and token.strip():
        return token.strip()

    if os.path.exists(TELEGRAM_TOKEN_FILE):
        try:
            with open(TELEGRAM_TOKEN_FILE, "r", encoding="utf-8") as f:
                t = f.read().strip()
                if t:
                    return t
        except Exception as e:
            logger.debug(f"Could not read Telegram token from file: {e}")

    return None


def send_chat_action(chat_id: str, action: str = "typing", token: Optional[str] = None) -> bool:
    """Send a native Telegram chat action (e.g. 'typing').
    
    Returns True if accepted by Telegram (HTTP 200), False otherwise.
    Never raises exceptions.
    """
    bot_token = token or get_telegram_token()
    if not bot_token or not chat_id:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendChatAction"
    payload = json.dumps({"chat_id": str(chat_id).strip(), "action": action}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        logger.debug(f"Telegram sendChatAction failed for chat {chat_id}: {e}")
        return False


def send_telegram_message(
    chat_id: str,
    text: str,
    parse_mode: str = "HTML",
    token: Optional[str] = None
) -> bool:
    """Send a native Telegram message to a user or chat.
    
    Used for asynchronous background job completion notifications.
    Returns True if accepted by Telegram (HTTP 200), False otherwise.
    Never raises exceptions.
    """
    bot_token = token or get_telegram_token()
    if not bot_token or not chat_id or not text:
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": str(chat_id).strip(),
        "text": text,
        "parse_mode": parse_mode
    }).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        logger.warning(f"Telegram sendMessage failed for chat {chat_id}: {e}")
        return False


class HeartbeatHandle:
    """Encapsulates a running background heartbeat thread and its stop event."""

    def __init__(self, session_id: str, chat_id: str, thread: threading.Thread, stop_event: threading.Event):
        self.session_id = session_id
        self.chat_id = chat_id
        self.thread = thread
        self.stop_event = stop_event
        self.started_at = time.time()


class TelegramTypingService:
    """Manages background typing heartbeats across active sessions."""

    _active_heartbeats: Dict[str, HeartbeatHandle] = {}
    _lock = threading.Lock()

    @classmethod
    def start_heartbeat(
        cls,
        session_id: str,
        chat_id: str,
        interval: float = 4.0,
        max_duration: float = 180.0
    ) -> bool:
        """Start a background typing heartbeat for a given session and chat.
        
        Refreshes the 'typing' indicator every `interval` seconds (default 4.0s).
        Automatically terminates after `max_duration` (default 180s) or upon stop.
        """
        if not session_id or not chat_id:
            return False

        with cls._lock:
            # Stop any existing heartbeat for this session
            cls._stop_heartbeat_unlocked(session_id)

            stop_event = threading.Event()
            token = get_telegram_token()
            if not token:
                logger.debug("Cannot start typing heartbeat: No Telegram token available.")
                return False

            def _heartbeat_worker():
                start_time = time.time()
                logger.debug(f"Typing heartbeat started for session {session_id}, chat {chat_id}")

                while not stop_event.is_set():
                    elapsed = time.time() - start_time
                    if elapsed >= max_duration:
                        logger.debug(f"Typing heartbeat reached max duration ({max_duration}s) for {session_id}")
                        break

                    # Send typing action
                    send_chat_action(chat_id, "typing", token=token)

                    # Wait for interval or until stopped early
                    if stop_event.wait(timeout=interval):
                        break

                logger.debug(f"Typing heartbeat stopped for session {session_id}")

            t = threading.Thread(
                target=_heartbeat_worker,
                name=f"aegis-typing-{session_id}",
                daemon=True
            )
            handle = HeartbeatHandle(session_id, chat_id, t, stop_event)
            cls._active_heartbeats[session_id] = handle
            t.start()
            return True

    @classmethod
    def stop_heartbeat(cls, session_id: str) -> bool:
        """Stop an active typing heartbeat for a given session."""
        if not session_id:
            return False

        with cls._lock:
            return cls._stop_heartbeat_unlocked(session_id)

    @classmethod
    def _stop_heartbeat_unlocked(cls, session_id: str) -> bool:
        handle = cls._active_heartbeats.pop(session_id, None)
        if handle:
            handle.stop_event.set()
            return True
        return False

    @classmethod
    def stop_all(cls) -> int:
        """Stop all active typing heartbeats."""
        with cls._lock:
            count = 0
            for sid, handle in list(cls._active_heartbeats.items()):
                handle.stop_event.set()
                count += 1
            cls._active_heartbeats.clear()
            return count

    @classmethod
    def is_active(cls, session_id: str) -> bool:
        """Check if a typing heartbeat is currently running for a session."""
        with cls._lock:
            handle = cls._active_heartbeats.get(session_id)
            return handle is not None and handle.thread.is_alive() and not handle.stop_event.is_set()
