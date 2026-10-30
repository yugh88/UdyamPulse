"""LLM providers. Default is a deterministic template writer so the demo works with no API keys.
Azure OpenAI / OpenAI are wired through Semantic Kernel. Any LLM output containing a number that is
not in the structured facts is rejected and the template text is used instead."""

from __future__ import annotations

import asyncio
import json
import logging
import os
from functools import lru_cache

from agents.guard import unsupported_numbers
from core.settings import get_settings

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a credit analyst assistant at an Indian bank writing for a credit officer. "
    "Rewrite the DRAFT into clear, concise professional prose. Rules: use ONLY numbers that appear in FACTS "
    "or DRAFT, verbatim; never compute, round or invent numbers; keep every policy citation like [§4.1]; "
    "do not add recommendations beyond the draft; the final decision belongs to the credit officer."
)


class TemplateLLM:
    """Deterministic writer: returns the agent's template draft unchanged."""

    name = "template"

    def write(self, task: str, facts: dict, draft: str) -> str:
        return draft


class SemanticKernelLLM:
    """Azure OpenAI (or OpenAI) chat completion through Semantic Kernel, guarded against invented numbers."""

    def __init__(self, provider: str) -> None:
        from semantic_kernel import Kernel

        self.name = provider
        self.kernel = Kernel()
        if provider == "azure_openai":
            from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion

            self.service = AzureChatCompletion(
                deployment_name=os.environ["AZURE_OPENAI_DEPLOYMENT"],
                endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
                api_key=os.environ["AZURE_OPENAI_API_KEY"],
                api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-10-21"),
            )
        else:
            from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

            self.service = OpenAIChatCompletion(
                ai_model_id=os.environ.get("OPENAI_MODEL") or "gpt-4o-mini",
                api_key=os.environ["OPENAI_API_KEY"],
            )
        self.kernel.add_service(self.service)

    async def _complete(self, task: str, facts: dict, draft: str) -> str:
        from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
        from semantic_kernel.contents import ChatHistory

        history = ChatHistory()
        history.add_system_message(SYSTEM_PROMPT)
        history.add_user_message(
            f"TASK: {task}\n\nFACTS (JSON):\n{json.dumps(facts, ensure_ascii=False, default=str)}\n\nDRAFT:\n{draft}"
        )
        settings = OpenAIChatPromptExecutionSettings(temperature=0.2, max_tokens=600)
        result = await self.service.get_chat_message_content(history, settings=settings)
        return str(result).strip()

    def write(self, task: str, facts: dict, draft: str) -> str:
        try:
            text = asyncio.run(self._complete(task, facts, draft))
        except Exception as exc:  # network / quota / config -> deterministic fallback
            log.warning("LLM call failed (%s); using template text", exc)
            return draft
        bad = unsupported_numbers(text, {"facts": facts, "draft": draft})
        if bad or not text:
            log.warning("LLM output rejected by number guard: %s", sorted(bad))
            return draft
        return text


@lru_cache
def get_llm() -> TemplateLLM | SemanticKernelLLM:
    provider = get_settings().llm_provider
    if provider in ("azure_openai", "openai"):
        try:
            return SemanticKernelLLM(provider)
        except Exception as exc:
            log.warning("LLM provider '%s' unavailable (%s); falling back to template writer", provider, exc)
    return TemplateLLM()
