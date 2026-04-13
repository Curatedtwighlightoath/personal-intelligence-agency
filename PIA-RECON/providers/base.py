"""
LLMProvider ABC. One method: call_structured.

Every provider takes a JSON-Schema tool description and returns the tool's
input dict. This deliberately mirrors how matcher.EVAL_TOOL is already
structured, so both Anthropic tool-use and OpenAI function-calling can
satisfy the same contract.
"""

from abc import ABC, abstractmethod


class ProviderError(RuntimeError):
    """Raised when a provider call fails in a way callers can recognize."""


class LLMProvider(ABC):
    """Structured-output LLM client, provider-agnostic."""

    @abstractmethod
    async def call_structured(
        self,
        system: str,
        user: str,
        tool_schema: dict,
        tool_name: str,
        max_tokens: int = 2048,
    ) -> dict:
        """
        Run a single chat turn that MUST emit a tool call named `tool_name`
        whose arguments match `tool_schema` (JSON Schema).

        Returns the tool's input dict. Raises ProviderError on
        authentication, structure, or network failures that the caller
        should surface to the user.
        """
        ...
