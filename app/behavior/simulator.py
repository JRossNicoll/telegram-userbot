"""Human behavior simulation layer for anti-detection."""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from telethon.tl.functions.messages import SetTypingRequest
from telethon.tl.types import SendMessageCancelAction, SendMessageTypingAction

if TYPE_CHECKING:
    from telethon import TelegramClient

    from app.config.settings import BehaviorSettings

logger = logging.getLogger(__name__)


class HumanBehaviorSimulator:
    """Simulates natural human behavior patterns to avoid detection.

    Features:
    - Non-linear response delay distribution (beta distribution)
    - Typing indicator simulation
    - Probabilistic message ignoring
    - Time-of-day activity awareness
    """

    def __init__(self, settings: BehaviorSettings) -> None:
        self._settings = settings
        self._recent_responses: list[str] = []
        self._max_recent = 20

    def should_ignore(self) -> bool:
        """Decide whether to ignore a message (probabilistic).

        Uses the configured ignore rate (default 10-30%) to randomly
        skip messages, making behavior more human-like.
        """
        return random.random() < self._settings.ignore_rate

    def is_active_hours(self) -> bool:
        """Check if current UTC hour falls within configured active hours."""
        current_hour = datetime.now(timezone.utc).hour
        start = self._settings.active_hours_start
        end = self._settings.active_hours_end

        if start <= end:
            return start <= current_hour < end
        else:
            # Wraps midnight (e.g., 22 to 6)
            return current_hour >= start or current_hour < end

    def get_activity_modifier(self) -> float:
        """Return a multiplier for response probability based on time of day.

        During active hours: 1.0 (full activity)
        Outside active hours: 0.3 (much less active, simulates sleeping)
        """
        return 1.0 if self.is_active_hours() else 0.3

    def calculate_delay(self) -> float:
        """Calculate a human-like response delay using beta distribution.

        The beta distribution (alpha=2, beta=5) produces a right-skewed
        distribution — most delays are on the shorter end but occasional
        longer delays occur naturally.
        """
        min_delay = self._settings.min_response_delay
        max_delay = self._settings.max_response_delay

        # Beta distribution: skewed toward shorter delays
        normalized = random.betavariate(2, 5)
        delay = min_delay + (max_delay - min_delay) * normalized

        # Add small random jitter
        jitter = random.uniform(-0.5, 0.5)
        delay = max(min_delay, delay + jitter)

        return round(delay, 2)

    async def simulate_typing(
        self,
        client: TelegramClient,
        chat_id: int,
        response_text: str,
    ) -> None:
        """Simulate typing indicator for a realistic duration.

        Typing duration is based on response length with some randomness.
        Average human types ~40 words per minute / ~200 chars per minute.
        """
        char_count = len(response_text)
        # ~200 chars per minute = ~3.3 chars per second
        typing_duration = min(char_count / 3.3, 8.0)  # Cap at 8 seconds
        typing_duration = max(1.5, typing_duration)  # Minimum 1.5 seconds
        typing_duration += random.uniform(-0.5, 1.0)

        try:
            await client(SetTypingRequest(
                peer=chat_id,
                action=SendMessageTypingAction(),
            ))

            await asyncio.sleep(typing_duration)

            await client(SetTypingRequest(
                peer=chat_id,
                action=SendMessageCancelAction(),
            ))
        except Exception:
            logger.debug("Failed to simulate typing (non-critical)")

    async def apply_response_delay(self) -> float:
        """Wait for a human-like delay before responding. Returns delay used."""
        delay = self.calculate_delay()
        logger.debug("Applying response delay: %.2fs", delay)
        await asyncio.sleep(delay)
        return delay

    def track_response(self, response: str) -> None:
        """Track recent responses to avoid repetition."""
        self._recent_responses.append(response.lower().strip())
        if len(self._recent_responses) > self._max_recent:
            self._recent_responses.pop(0)

    def is_too_similar(self, response: str) -> bool:
        """Check if a response is too similar to recent ones.

        Uses simple substring matching to detect repetitive patterns.
        """
        normalized = response.lower().strip()
        for recent in self._recent_responses[-5:]:
            # Exact match
            if normalized == recent:
                return True
            # High overlap (one contains the other)
            if (
                len(normalized) > 10
                and len(recent) > 10
                and (normalized in recent or recent in normalized)
            ):
                return True
        return False
