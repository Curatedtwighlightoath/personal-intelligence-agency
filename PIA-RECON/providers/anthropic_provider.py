"""Anthropic (Claude) provider using tool-use for structured output."""

import anthropic

from .base import LLMProvider, ProviderError


class AnthropicProvider(LLMProvider):
    def __init__(self, model: str, api_key: str, base_url: str | None = None):
        self.model = model
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = anthropic.AsyncAnthropic(**kwargs)

    async def call_structured(
        self,
        system: str,
        user: str,
        tool_schema: dict,
        tool_name: str,
        max_tokens: int = 2048,
    ) -> dict:
        tool = {
            "name": tool_name,
            "description": f"Emit structured output for {tool_name}.",
            "input_schema": tool_schema,
        }
        response = await self._client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=[tool],
            tool_choice={"type": "tool", "name": tool_name},
            messages=[{"role": "user", "content": user}],
        )

        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool_name:
                return dict(block.input)

        raise ProviderError(
            f"Anthropic response missing tool_use block for '{tool_name}'. "
            f"Got: {response.content!r}"
        )
