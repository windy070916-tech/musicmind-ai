"""Generate presentation-ready reports from structured knowledge facts."""

from collections.abc import Sequence

from music_ai.ai.base import LLMProvider, create_llm_provider
from music_ai.ai.prompts import DAILY_REPORT_PROMPT, SYSTEM_PROMPT
from music_ai.knowledge.models import KnowledgeFact


class ReportGenerator:
    """Turn knowledge facts into a Markdown report through an LLM provider."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """Use an injected provider or create the one selected by configuration."""
        self._provider = provider or create_llm_provider()

    def generate_daily_report(self, facts: Sequence[KnowledgeFact]) -> str:
        """Generate a Markdown daily report from structured daily and trend facts."""
        user_prompt = DAILY_REPORT_PROMPT.format(facts=_format_facts(facts))
        return self._provider.generate(SYSTEM_PROMPT, user_prompt)


def _format_facts(facts: Sequence[KnowledgeFact]) -> str:
    """Convert public knowledge objects into compact, provider-neutral prompt text."""
    if not facts:
        return "- No listening facts are available."

    return "\n".join(
        f"- [{fact.category}] {fact.title}: {fact.description}" for fact in facts
    )
