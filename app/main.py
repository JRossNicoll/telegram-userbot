"""Main entry point for the Telegram MTProto Userbot."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
import sys

from app.ai.engine import AIEngine
from app.behavior.simulator import HumanBehaviorSimulator
from app.client.telegram_client import UserClient
from app.commands.system import CommandHandler
from app.config.settings import Settings
from app.handlers.message_handler import MessageHandler
from app.memory.store import MemoryStore
from app.utils.logging_config import setup_logging
from app.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class Userbot:
    """Main application class that wires all components together."""

    def __init__(self) -> None:
        self._settings = Settings()
        self._user_client = UserClient(self._settings.telegram)
        self._ai_engine = AIEngine(self._settings.ai)
        self._behavior = HumanBehaviorSimulator(self._settings.behavior)
        self._memory = MemoryStore(self._settings.database_path)
        self._rate_limiter = RateLimiter(self._settings.rate_limit)
        self._running = False

    async def start(self) -> None:
        """Initialize all components and start listening for messages."""
        setup_logging(self._settings.log_level)
        logger.info("Starting Telegram Userbot...")

        # Validate critical settings
        if not self._settings.telegram.api_id or not self._settings.telegram.api_hash:
            logger.error("TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env")
            sys.exit(1)

        if not self._settings.telegram.phone:
            logger.error("TELEGRAM_PHONE must be set in .env")
            sys.exit(1)

        # Initialize components
        await self._memory.initialize()
        self._ai_engine.initialize()

        # Connect to Telegram
        client = await self._user_client.connect()
        me = await self._user_client.get_me()
        my_id = me.id
        my_username = me.username or ""

        logger.info("Connected as @%s (ID: %s)", my_username, my_id)

        # Set up command handler (owner = the logged-in user)
        command_handler = CommandHandler(
            owner_id=my_id,
            memory=self._memory,
            rate_limiter=self._rate_limiter,
            behavior=self._behavior,
        )

        # Set up message handler
        message_handler = MessageHandler(
            client=client,
            settings=self._settings,
            ai_engine=self._ai_engine,
            behavior=self._behavior,
            memory=self._memory,
            rate_limiter=self._rate_limiter,
            command_handler=command_handler,
            my_id=my_id,
            my_username=my_username,
        )
        message_handler.register()

        self._running = True
        logger.info("Userbot is now running. Listening for messages...")
        logger.info(
            "Trigger keywords: %s | DM: %s | Mentions: %s",
            ", ".join(self._settings.trigger.keywords),
            self._settings.trigger.respond_to_dm,
            self._settings.trigger.respond_to_mentions,
        )
        logger.info(
            "Behavior: delay %.0f-%.0fs | ignore rate %.0f%% | context window %d",
            self._settings.behavior.min_response_delay,
            self._settings.behavior.max_response_delay,
            self._settings.behavior.ignore_rate * 100,
            self._settings.behavior.context_window_size,
        )

        # Run until disconnected
        await client.run_until_disconnected()

    async def stop(self) -> None:
        """Gracefully shut down all components."""
        logger.info("Shutting down userbot...")
        self._running = False
        await self._user_client.disconnect()
        await self._memory.close()
        logger.info("Userbot stopped.")


def _handle_signals(bot: Userbot, loop: asyncio.AbstractEventLoop) -> None:
    """Register signal handlers for graceful shutdown."""
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.ensure_future(bot.stop()))


def main() -> None:
    """Entry point."""
    bot = Userbot()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    with contextlib.suppress(NotImplementedError):
        _handle_signals(bot, loop)

    try:
        loop.run_until_complete(bot.start())
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt.")
        loop.run_until_complete(bot.stop())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
