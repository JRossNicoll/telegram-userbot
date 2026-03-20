"""Telegram MTProto client wrapper using Telethon."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from telethon import TelegramClient

if TYPE_CHECKING:
    from app.config.settings import TelegramSettings

logger = logging.getLogger(__name__)


class UserClient:
    """Manages the Telethon MTProto client connection and session persistence."""

    def __init__(self, settings: TelegramSettings) -> None:
        self._settings = settings
        self._client: TelegramClient | None = None

    @property
    def client(self) -> TelegramClient:
        if self._client is None:
            raise RuntimeError("Client not initialized. Call connect() first.")
        return self._client

    async def connect(self) -> TelegramClient:
        """Initialize and connect the Telethon client.

        Uses file-based session persistence so re-authentication
        is not required on every restart.
        """
        session_dir = Path("sessions")
        session_dir.mkdir(exist_ok=True)
        session_path = str(session_dir / self._settings.session_name)

        self._client = TelegramClient(
            session_path,
            self._settings.api_id,
            self._settings.api_hash,
        )

        await self._client.connect()

        if not await self._client.is_user_authorized():
            logger.info("Session not authorized. Starting phone authentication...")
            await self._client.send_code_request(self._settings.phone)
            code = input("Enter the Telegram verification code: ")
            try:
                await self._client.sign_in(self._settings.phone, code)
            except Exception:
                # 2FA might be enabled
                password = input("Two-factor authentication enabled. Enter your password: ")
                await self._client.sign_in(password=password)

        me = await self._client.get_me()
        logger.info(
            "Logged in as %s (ID: %s)",
            me.first_name if me else "Unknown",
            me.id if me else "Unknown",
        )
        return self._client

    async def disconnect(self) -> None:
        """Gracefully disconnect the client."""
        if self._client and self._client.is_connected():
            await self._client.disconnect()
            logger.info("Client disconnected.")

    async def get_me(self):
        """Return the current user entity."""
        return await self.client.get_me()
