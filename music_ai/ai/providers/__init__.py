"""Concrete LLM provider adapters."""

from music_ai.ai.providers.deepseek import DeepSeekProvider
from music_ai.ai.providers.openai import OpenAIProvider

__all__ = ["DeepSeekProvider", "OpenAIProvider"]
