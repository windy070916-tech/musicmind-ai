"""Shared provider contract and configuration-based provider factory."""

from abc import ABC, abstractmethod
from os import getenv
from typing import Any

import requests


class LLMProvider(ABC):
    """A provider capable of producing a response from two text prompts."""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Return the provider's generated text response."""


def create_llm_provider() -> LLMProvider:
    """Create the configured provider without exposing it to business logic."""
    provider_name = getenv("LLM_PROVIDER", "").strip().lower()

    if provider_name == "deepseek":
        from music_ai.ai.providers.deepseek import DeepSeekProvider

        return DeepSeekProvider(
            api_key=_required_environment_value("DEEPSEEK_API_KEY"),
            model=getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        )

    if provider_name == "openai":
        from music_ai.ai.providers.openai import OpenAIProvider

        return OpenAIProvider(
            api_key=_required_environment_value("OPENAI_API_KEY"),
            model=getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        )

    if not provider_name:
        raise RuntimeError("Missing required environment variable: LLM_PROVIDER")
    raise RuntimeError(f"Unsupported LLM_PROVIDER: {provider_name}")


def _required_environment_value(name: str) -> str:
    """Return a required provider credential without exposing its value."""
    value = getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _post_chat_completion(
    url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    provider_name: str,
) -> dict[str, Any]:
    """Call a non-streaming, OpenAI-compatible chat completion endpoint."""
    try:
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
            },
            timeout=30,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        raise RuntimeError(f"{provider_name} request failed.") from error

    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError(f"{provider_name} returned an invalid response.")
    return payload


def _response_content(payload: dict[str, Any], provider_name: str) -> str:
    """Extract the first chat-completion message content from an API response."""
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError(f"{provider_name} returned no generated content.") from error

    if not isinstance(content, str) or not content.strip():
        raise RuntimeError(f"{provider_name} returned no generated content.")
    return content
