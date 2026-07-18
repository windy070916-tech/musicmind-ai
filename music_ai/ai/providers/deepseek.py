"""DeepSeek adapter implementing MusicMind's shared LLM provider contract."""

from dataclasses import dataclass, field

from music_ai.ai.base import LLMProvider, _post_chat_completion, _response_content


@dataclass(frozen=True, slots=True)
class DeepSeekProvider(LLMProvider):
    """Generate text through DeepSeek's OpenAI-compatible chat endpoint."""

    api_key: str = field(repr=False)
    model: str = "deepseek-v4-flash"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompts to DeepSeek and return the generated message content."""
        response = _post_chat_completion(
            "https://api.deepseek.com/chat/completions",
            self.api_key,
            self.model,
            system_prompt,
            user_prompt,
            "DeepSeek",
        )
        return _response_content(response, "DeepSeek")
