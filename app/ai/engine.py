"""AI response engine with support for OpenAI and Anthropic."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.config.settings import AISettings

logger = logging.getLogger(__name__)


class AIEngine:
    """Generates AI-powered responses using OpenAI or Anthropic APIs.

    Maintains a configurable personality prompt and processes
    conversation context to produce natural responses.
    """

    def __init__(self, settings: AISettings) -> None:
        self._settings = settings
        self._provider = settings.provider
        self._personality = settings.personality_prompt
        self._openai_client = None
        self._anthropic_client = None

    def initialize(self) -> None:
        """Initialize the selected AI provider client."""
        if self._provider == "openai":
            import openai

            self._openai_client = openai.AsyncOpenAI(api_key=self._settings.openai_api_key)
            logger.info("OpenAI client initialized (model: %s)", self._settings.openai_model)
        elif self._provider == "anthropic":
            import anthropic

            self._anthropic_client = anthropic.AsyncAnthropic(
                api_key=self._settings.anthropic_api_key
            )
            logger.info(
                "Anthropic client initialized (model: %s)", self._settings.anthropic_model
            )
        else:
            raise ValueError(f"Unsupported AI provider: {self._provider}")

    async def generate_response(
        self,
        message: str,
        context: list[dict[str, str]] | None = None,
        sender_name: str = "User",
    ) -> str:
        """Generate a response to a message with optional conversation context.

        Args:
            message: The incoming message text.
            context: List of previous messages as {"role": ..., "content": ...} dicts.
            sender_name: Display name of the message sender.

        Returns:
            The generated response text.
        """
        if context is None:
            context = []

        if self._provider == "openai":
            return await self._generate_openai(message, context, sender_name)
        elif self._provider == "anthropic":
            return await self._generate_anthropic(message, context, sender_name)
        else:
            raise ValueError(f"Unsupported AI provider: {self._provider}")

    async def _generate_openai(
        self,
        message: str,
        context: list[dict[str, str]],
        sender_name: str,
    ) -> str:
        """Generate response using OpenAI API."""
        if self._openai_client is None:
            raise RuntimeError("OpenAI client not initialized. Call initialize() first.")

        messages = [{"role": "system", "content": self._build_system_prompt()}]

        # Add conversation context
        for ctx_msg in context:
            messages.append(ctx_msg)

        messages.append({"role": "user", "content": f"{sender_name}: {message}"})

        try:
            response = await self._openai_client.chat.completions.create(
                model=self._settings.openai_model,
                messages=messages,
                max_tokens=500,
                temperature=0.9,
                presence_penalty=0.6,
                frequency_penalty=0.5,
            )
            content = response.choices[0].message.content
            return content.strip() if content else ""
        except Exception:
            logger.exception("OpenAI API error")
            return ""

    async def _generate_anthropic(
        self,
        message: str,
        context: list[dict[str, str]],
        sender_name: str,
    ) -> str:
        """Generate response using Anthropic API."""
        if self._anthropic_client is None:
            raise RuntimeError("Anthropic client not initialized. Call initialize() first.")

        messages = []

        # Add conversation context
        for ctx_msg in context:
            messages.append(ctx_msg)

        messages.append({"role": "user", "content": f"{sender_name}: {message}"})

        # Ensure messages alternate properly for Anthropic
        messages = self._fix_message_order(messages)

        try:
            response = await self._anthropic_client.messages.create(
                model=self._settings.anthropic_model,
                max_tokens=500,
                system=self._build_system_prompt(),
                messages=messages,
            )
            content = response.content[0].text
            return content.strip() if content else ""
        except Exception:
            logger.exception("Anthropic API error")
            return ""

    def _build_system_prompt(self) -> str:
        """Build the system prompt with personality and behavioral instructions."""
        return (
            f"{self._personality}\n\n"
            "Important behavioral rules:\n"
            "- Keep responses concise (1-3 sentences for casual chat)\n"
            "- Use natural, conversational language\n"
            "- Vary your phrasing — never repeat the same sentence structure\n"
            "- Match the energy and tone of the conversation\n"
            "- Use lowercase and casual punctuation when appropriate\n"
            "- Occasionally use common chat abbreviations (lol, tbh, ngl, etc.)\n"
            "- Do NOT use overly formal language or bullet points\n"
            "- Do NOT start every message the same way\n"
            "- Do NOT mention that you are an AI or bot\n"
            "- Respond ONLY with the message text — no prefixes like 'Response:'\n"
        )

    @staticmethod
    def _fix_message_order(messages: list[dict[str, str]]) -> list[dict[str, str]]:
        """Ensure messages alternate between user and assistant for Anthropic.

        Anthropic requires strictly alternating user/assistant messages.
        Consecutive messages of the same role are merged.
        """
        if not messages:
            return [{"role": "user", "content": "Hello"}]

        fixed: list[dict[str, str]] = []
        for msg in messages:
            if fixed and fixed[-1]["role"] == msg["role"]:
                fixed[-1]["content"] += f"\n{msg['content']}"
            else:
                fixed.append(dict(msg))

        # Must start with user
        if fixed[0]["role"] != "user":
            fixed.insert(0, {"role": "user", "content": "Hello"})

        return fixed
