"""Rate limiting and cooldown management."""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config.settings import RateLimitSettings

logger = logging.getLogger(__name__)


class RateLimiter:
    """Manages rate limits and cooldowns to prevent spam-like behavior.

    Tracks message rates per chat and per user, enforcing configurable
    limits and cooldown periods.
    """

    def __init__(self, settings: RateLimitSettings) -> None:
        self._settings = settings
        # Timestamps of messages sent per chat: {chat_id: [timestamps]}
        self._chat_messages: dict[int, list[float]] = defaultdict(list)
        # Last response time per user: {user_id: timestamp}
        self._user_cooldowns: dict[int, float] = {}
        # Global message timestamps
        self._global_messages: list[float] = []

    def can_respond(self, chat_id: int, user_id: int) -> bool:
        """Check if we can respond based on all rate limits.

        Returns True if all limits allow a response, False otherwise.
        """
        now = time.time()
        self._cleanup_old_timestamps(now)

        # Check per-chat rate limit
        chat_msgs = self._chat_messages[chat_id]
        recent_chat = [t for t in chat_msgs if now - t < 60]
        if len(recent_chat) >= self._settings.per_chat:
            logger.debug("Rate limited: chat %s (%d msgs/min)", chat_id, len(recent_chat))
            return False

        # Check per-user cooldown
        last_response = self._user_cooldowns.get(user_id, 0)
        if now - last_response < self._settings.user_cooldown_seconds:
            remaining = self._settings.user_cooldown_seconds - (now - last_response)
            logger.debug("Cooldown active for user %s (%.1fs remaining)", user_id, remaining)
            return False

        # Check global rate limit
        recent_global = [t for t in self._global_messages if now - t < 60]
        if len(recent_global) >= self._settings.global_rate_limit:
            logger.debug("Global rate limit reached (%d msgs/min)", len(recent_global))
            return False

        return True

    def record_response(self, chat_id: int, user_id: int) -> None:
        """Record that a response was sent."""
        now = time.time()
        self._chat_messages[chat_id].append(now)
        self._user_cooldowns[user_id] = now
        self._global_messages.append(now)

    def _cleanup_old_timestamps(self, now: float) -> None:
        """Remove timestamps older than 2 minutes to prevent memory growth."""
        cutoff = now - 120

        for chat_id in list(self._chat_messages.keys()):
            self._chat_messages[chat_id] = [
                t for t in self._chat_messages[chat_id] if t > cutoff
            ]
            if not self._chat_messages[chat_id]:
                del self._chat_messages[chat_id]

        self._global_messages = [t for t in self._global_messages if t > cutoff]

        # Clean old user cooldowns (keep last 1000)
        if len(self._user_cooldowns) > 1000:
            sorted_users = sorted(self._user_cooldowns.items(), key=lambda x: x[1])
            self._user_cooldowns = dict(sorted_users[-500:])
