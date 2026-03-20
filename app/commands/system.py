"""Command system for manual overrides and admin controls.

Commands are prefixed with '!' and can only be executed by the bot owner.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telethon.events import NewMessage

    from app.behavior.simulator import HumanBehaviorSimulator
    from app.memory.store import MemoryStore
    from app.utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

CommandFunc = Callable[["CommandHandler", "NewMessage.Event", list[str]], Awaitable[str | None]]


class CommandHandler:
    """Handles owner-only commands for controlling the userbot.

    Commands:
        !ping        - Check if the bot is alive
        !stats       - Show memory store statistics
        !contacts    - Show frequent contacts
        !status      - Show current bot status
        !pause       - Pause automatic responses
        !resume      - Resume automatic responses
        !ignore <id> - Add a chat/user to the ignore list
        !unignore <id> - Remove from the ignore list
        !help        - Show available commands
    """

    COMMAND_PREFIX = "!"

    def __init__(
        self,
        owner_id: int,
        memory: MemoryStore,
        rate_limiter: RateLimiter,
        behavior: HumanBehaviorSimulator,
    ) -> None:
        self._owner_id = owner_id
        self._memory = memory
        self._rate_limiter = rate_limiter
        self._behavior = behavior
        self._paused = False
        self._ignore_list: set[int] = set()
        self._start_time = time.time()

        self._commands: dict[str, CommandFunc] = {
            "ping": self._cmd_ping,
            "stats": self._cmd_stats,
            "contacts": self._cmd_contacts,
            "status": self._cmd_status,
            "pause": self._cmd_pause,
            "resume": self._cmd_resume,
            "ignore": self._cmd_ignore,
            "unignore": self._cmd_unignore,
            "help": self._cmd_help,
        }

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def ignore_list(self) -> set[int]:
        return self._ignore_list

    def is_command(self, text: str) -> bool:
        """Check if a message is a command."""
        return text.strip().startswith(self.COMMAND_PREFIX)

    async def handle(self, event: NewMessage.Event) -> str | None:
        """Process a command message. Returns response text or None."""
        sender = await event.get_sender()
        sender_id = sender.id if sender else 0

        if sender_id != self._owner_id:
            logger.debug("Command rejected: sender %s is not owner %s", sender_id, self._owner_id)
            return None

        text = event.message.text.strip()
        parts = text[len(self.COMMAND_PREFIX):].split()
        if not parts:
            return None

        cmd_name = parts[0].lower()
        args = parts[1:]

        handler = self._commands.get(cmd_name)
        if handler is None:
            return f"Unknown command: {cmd_name}. Use !help for available commands."

        try:
            return await handler(event, args)
        except Exception:
            logger.exception("Error executing command: %s", cmd_name)
            return f"Error executing command: {cmd_name}"

    async def _cmd_ping(self, event: NewMessage.Event, args: list[str]) -> str:
        uptime = time.time() - self._start_time
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        return f"Pong! Uptime: {hours}h {minutes}m"

    async def _cmd_stats(self, event: NewMessage.Event, args: list[str]) -> str:
        stats = await self._memory.get_stats()
        return (
            f"Stats:\n"
            f"  Messages tracked: {stats.get('total_messages', 0)}\n"
            f"  Users profiled: {stats.get('total_users', 0)}\n"
            f"  Responses sent: {stats.get('total_responses', 0)}"
        )

    async def _cmd_contacts(self, event: NewMessage.Event, args: list[str]) -> str:
        limit = int(args[0]) if args else 10
        contacts = await self._memory.get_frequent_contacts(limit)
        if not contacts:
            return "No contacts tracked yet."
        lines = ["Frequent contacts:"]
        for c in contacts:
            name = c["first_name"] or c["username"] or str(c["user_id"])
            lines.append(f"  {name}: {c['interaction_count']} interactions")
        return "\n".join(lines)

    async def _cmd_status(self, event: NewMessage.Event, args: list[str]) -> str:
        return (
            f"Status:\n"
            f"  Paused: {self._paused}\n"
            f"  Active hours: {self._behavior.is_active_hours()}\n"
            f"  Ignored chats/users: {len(self._ignore_list)}"
        )

    async def _cmd_pause(self, event: NewMessage.Event, args: list[str]) -> str:
        self._paused = True
        return "Automatic responses paused."

    async def _cmd_resume(self, event: NewMessage.Event, args: list[str]) -> str:
        self._paused = False
        return "Automatic responses resumed."

    async def _cmd_ignore(self, event: NewMessage.Event, args: list[str]) -> str:
        if not args:
            return "Usage: !ignore <chat_id or user_id>"
        try:
            target_id = int(args[0])
            self._ignore_list.add(target_id)
            return f"Added {target_id} to ignore list."
        except ValueError:
            return "Invalid ID. Must be a number."

    async def _cmd_unignore(self, event: NewMessage.Event, args: list[str]) -> str:
        if not args:
            return "Usage: !unignore <chat_id or user_id>"
        try:
            target_id = int(args[0])
            self._ignore_list.discard(target_id)
            return f"Removed {target_id} from ignore list."
        except ValueError:
            return "Invalid ID. Must be a number."

    async def _cmd_help(self, event: NewMessage.Event, args: list[str]) -> str:
        return (
            "Available commands:\n"
            "  !ping - Check if bot is alive\n"
            "  !stats - Show statistics\n"
            "  !contacts [N] - Show top N contacts\n"
            "  !status - Show current status\n"
            "  !pause - Pause auto-responses\n"
            "  !resume - Resume auto-responses\n"
            "  !ignore <id> - Ignore a chat/user\n"
            "  !unignore <id> - Remove from ignore list\n"
            "  !help - Show this message"
        )
