"""Core message handler with trigger logic and context-aware processing."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from telethon import events
from telethon.tl.types import User

if TYPE_CHECKING:
    from telethon import TelegramClient

    from app.ai.engine import AIEngine
    from app.behavior.simulator import HumanBehaviorSimulator
    from app.commands.system import CommandHandler
    from app.config.settings import Settings
    from app.memory.store import MemoryStore
    from app.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class MessageHandler:
    """Processes incoming Telegram messages and orchestrates responses.

    Responsibilities:
    - Evaluate trigger conditions (DM, mention, keywords)
    - Apply human behavior simulation (delays, typing, ignoring)
    - Generate AI responses with conversation context
    - Enforce rate limits and cooldowns
    - Store messages in memory and update user profiles
    """

    def __init__(
        self,
        client: TelegramClient,
        settings: Settings,
        ai_engine: AIEngine,
        behavior: HumanBehaviorSimulator,
        memory: MemoryStore,
        rate_limiter: RateLimiter,
        command_handler: CommandHandler,
        my_id: int,
        my_username: str,
    ) -> None:
        self._client = client
        self._settings = settings
        self._ai = ai_engine
        self._behavior = behavior
        self._memory = memory
        self._rate_limiter = rate_limiter
        self._commands = command_handler
        self._my_id = my_id
        self._my_username = my_username.lower() if my_username else ""

    def register(self) -> None:
        """Register the message event handler with the Telethon client."""
        self._client.add_event_handler(
            self._on_new_message,
            events.NewMessage(incoming=True),
        )
        logger.info("Message handler registered.")

    async def _on_new_message(self, event: events.NewMessage.Event) -> None:
        """Main entry point for all incoming messages."""
        try:
            await self._process_message(event)
        except Exception:
            logger.exception("Unhandled error in message handler")

    async def _process_message(self, event: events.NewMessage.Event) -> None:
        """Process a single incoming message through the full pipeline."""
        message = event.message
        text = message.text or ""

        if not text.strip():
            return

        # Get sender info
        sender = await event.get_sender()
        if not sender or not isinstance(sender, User):
            return

        # Don't respond to ourselves
        if sender.id == self._my_id:
            return

        sender_id = sender.id
        chat_id = event.chat_id or 0
        sender_name = sender.first_name or sender.username or "Unknown"

        # Check ignore list
        if sender_id in self._commands.ignore_list or chat_id in self._commands.ignore_list:
            return

        # Handle owner commands first
        if self._commands.is_command(text):
            response = await self._commands.handle(event)
            if response:
                await event.reply(response)
            return

        # Check if bot is paused
        if self._commands.is_paused:
            return

        # Update user profile
        await self._memory.update_user_profile(
            user_id=sender_id,
            username=sender.username or "",
            first_name=sender.first_name or "",
            last_name=sender.last_name or "",
        )

        # Store incoming message
        await self._memory.store_message(
            chat_id=chat_id,
            user_id=sender_id,
            user_name=sender_name,
            role="user",
            content=text,
        )

        # Determine if we should respond
        should_respond = self._should_trigger(event, text)
        if not should_respond:
            logger.debug("No trigger matched for message from %s in %s", sender_name, chat_id)
            return

        # Apply human behavior: random ignore
        if self._behavior.should_ignore():
            logger.debug("Randomly ignoring message from %s (behavior simulation)", sender_name)
            return

        # Time-of-day activity check
        activity_mod = self._behavior.get_activity_modifier()
        if activity_mod < 1.0:
            import random

            if random.random() > activity_mod:
                logger.debug("Outside active hours — skipping response")
                return

        # Rate limiting
        if not self._rate_limiter.can_respond(chat_id, sender_id):
            logger.debug("Rate limited — not responding to %s in %s", sender_name, chat_id)
            return

        # Get conversation context
        context = await self._memory.get_context(
            chat_id=chat_id,
            limit=self._settings.behavior.context_window_size,
        )

        # Apply response delay (human simulation)
        delay = await self._behavior.apply_response_delay()

        # Generate AI response
        response = await self._ai.generate_response(
            message=text,
            context=context,
            sender_name=sender_name,
        )

        if not response:
            logger.warning("AI returned empty response for message: %s", text[:50])
            return

        # Check for repetition
        if self._behavior.is_too_similar(response):
            logger.debug("Response too similar to recent ones, regenerating...")
            response = await self._ai.generate_response(
                message=text,
                context=context,
                sender_name=f"{sender_name} (please vary your response style)",
            )
            if not response or self._behavior.is_too_similar(response):
                logger.warning("Could not generate non-repetitive response, skipping")
                return

        # Simulate typing
        await self._behavior.simulate_typing(self._client, chat_id, response)

        # Send the response
        await event.reply(response)
        logger.info("Responded to %s in chat %s (delay: %.1fs)", sender_name, chat_id, delay)

        # Track the response
        self._behavior.track_response(response)
        self._rate_limiter.record_response(chat_id, sender_id)

        # Store our response in memory
        await self._memory.store_message(
            chat_id=chat_id,
            user_id=self._my_id,
            user_name="me",
            role="assistant",
            content=response,
        )

        # Log response for analysis
        await self._memory.log_response(
            chat_id=chat_id,
            user_id=sender_id,
            prompt=text,
            response=response,
            delay_seconds=delay,
        )

    def _should_trigger(self, event: events.NewMessage.Event, text: str) -> bool:
        """Determine if the message should trigger a response.

        Triggers:
        1. Direct/private message (if enabled)
        2. Mentioned by @username (if enabled)
        3. Keyword match in message text
        """
        # Direct message (private chat)
        if event.is_private and self._settings.trigger.respond_to_dm:
            return True

        # Mentioned by username
        if (
            self._settings.trigger.respond_to_mentions
            and self._my_username
            and f"@{self._my_username}" in text.lower()
        ):
            return True

        # Reply to our message
        if event.message.reply_to:
            # We'll check if it's a reply to one of our messages
            # This is handled by checking reply_to_msg_id
            reply_header = event.message.reply_to
            if hasattr(reply_header, "reply_to_msg_id") and reply_header.reply_to_msg_id:
                # We can't easily check if it was our message without fetching it,
                # but replying to any message in a private chat is already handled above.
                # For groups, we could fetch the replied message, but for now
                # we rely on mentions and keywords.
                pass

        # Keyword match
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self._settings.trigger.keywords)
