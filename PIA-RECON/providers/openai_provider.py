"""
OpenAI-compatible provider — covers OpenAI, Azure-compatible, and Ollama
(point base_url at http://localhost:11434/v1).

Uses function-calling tool_choice to force the model into emitting structured
output, then JSON-decodes the function arguments.
"""

import json

from openai import AsyncOpenAI

from .base import LLMProvider, ProviderError


class OpenAIProvider(LLMProvider):
    def __init__(self, model: str, api_key: str, base_url: str | None = None):
        self.model = model
        kwargs = {"api_key": api_key or "unused"}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = AsyncOpenAI(**kwargs)

    async def call_structured(
        self,
        system: str,
        user: str,
        tool_schema: dict,
        tool_name: str,
        max_tokens: int = 2048,
    ) -> dict:
        tool = {
            "type": "function",
            "function": {
                "name": tool_name,
                "description": f"Emit structured output for {tool_name}.",
                "parameters": tool_schema,
            },
        }
        response = await self._client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            tools=[tool],
            tool_choice={"type": "function", "function": {"name": tool_name}},
        )

        choice = response.choices[0]
        tool_calls = getattr(choice.message, "tool_calls", None) or []
        for call in tool_calls:
            if call.function.name == tool_name:
                try:
                    return json.loads(call.function.arguments)
                except json.JSONDecodeError as e:
                    raise ProviderError(
                        f"OpenAI returned tool_call with invalid JSON arguments: {e}"
                    ) from e

        raise ProviderError(
            f"OpenAI response missing tool_call for '{tool_name}'. "
            f"Finish reason: {choice.finish_reason}. "
            f"Content: {choice.message.content!r}"
        )
