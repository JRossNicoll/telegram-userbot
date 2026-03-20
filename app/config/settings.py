"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv


def _load_env() -> None:
    """Load .env file from project root."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    load_dotenv(env_path)


_load_env()


def _csv_list(val: str) -> list[str]:
    """Parse a comma-separated string into a list of stripped, lowercased strings."""
    return [item.strip().lower() for item in val.split(",") if item.strip()]


@dataclass(frozen=True)
class TelegramSettings:
    api_id: int = int(os.getenv("TELEGRAM_API_ID", "0"))
    api_hash: str = os.getenv("TELEGRAM_API_HASH", "")
    phone: str = os.getenv("TELEGRAM_PHONE", "")
    session_name: str = os.getenv("TELEGRAM_SESSION_NAME", "userbot_session")


@dataclass(frozen=True)
class AISettings:
    provider: str = os.getenv("AI_PROVIDER", "openai").lower()
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")
    personality_prompt: str = os.getenv(
        "PERSONALITY_PROMPT",
        "You are a helpful and friendly person chatting on Telegram. "
        "Keep responses natural, concise, and conversational.",
    )


@dataclass(frozen=True)
class BehaviorSettings:
    min_response_delay: float = float(os.getenv("MIN_RESPONSE_DELAY", "3"))
    max_response_delay: float = float(os.getenv("MAX_RESPONSE_DELAY", "25"))
    ignore_rate: float = float(os.getenv("IGNORE_RATE", "0.15"))
    context_window_size: int = int(os.getenv("CONTEXT_WINDOW_SIZE", "10"))
    active_hours_start: int = int(os.getenv("ACTIVE_HOURS_START", "8"))
    active_hours_end: int = int(os.getenv("ACTIVE_HOURS_END", "23"))


@dataclass(frozen=True)
class RateLimitSettings:
    per_chat: int = int(os.getenv("RATE_LIMIT_PER_CHAT", "5"))
    user_cooldown_seconds: int = int(os.getenv("USER_COOLDOWN_SECONDS", "30"))
    global_rate_limit: int = int(os.getenv("GLOBAL_RATE_LIMIT", "20"))


@dataclass(frozen=True)
class TriggerSettings:
    keywords: list[str] = field(
        default_factory=lambda: _csv_list(os.getenv("TRIGGER_KEYWORDS", "hey,help,question,ask"))
    )
    respond_to_dm: bool = os.getenv("RESPOND_TO_DM", "true").lower() == "true"
    respond_to_mentions: bool = os.getenv("RESPOND_TO_MENTIONS", "true").lower() == "true"


@dataclass(frozen=True)
class Settings:
    telegram: TelegramSettings = field(default_factory=TelegramSettings)
    ai: AISettings = field(default_factory=AISettings)
    behavior: BehaviorSettings = field(default_factory=BehaviorSettings)
    rate_limit: RateLimitSettings = field(default_factory=RateLimitSettings)
    trigger: TriggerSettings = field(default_factory=TriggerSettings)
    log_level: str = os.getenv("LOG_LEVEL", "INFO").upper()
    database_path: str = os.getenv("DATABASE_PATH", "data/userbot.db")
