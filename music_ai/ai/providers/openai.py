"""OpenAI adapter implementing MusicMind's shared LLM provider contract."""

from dataclasses import dataclass, field

from music_ai.ai.base import LLMProvider, _post_chat_completion, _response_content


@dataclass(frozen=True, slots=True)
class OpenAIProvider(LLMProvider):
    """Generate text through OpenAI's chat completion endpoint."""

    api_key: str = field(repr=False)
    model: str = "gpt-4.1-mini"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompts to OpenAI and return the generated message content."""
        response = _post_chat_completion(
            "https://api.openai.com/v1/chat/completions",
            self.api_key,
            self.model,
            system_prompt,
            user_prompt,
            "OpenAI",
        )
        return _response_content(response, "OpenAI")
