"""Generate presentation-ready reports from structured knowledge facts."""

from collections.abc import Sequence
import json

from music_ai.ai.base import LLMProvider, create_llm_provider
from music_ai.ai.daily_brief import DailyBrief
from music_ai.ai.markdown_renderer import render_daily_brief
from music_ai.ai.prompts import DAILY_REPORT_PROMPT, SYSTEM_PROMPT
from music_ai.knowledge.models import KnowledgeFact


class ReportGenerator:
    """Turn knowledge facts into a Markdown report through an LLM provider."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        """Use an injected provider or create the one selected by configuration."""
        self._provider = provider or create_llm_provider()

    def generate_daily_brief(self, facts: Sequence[KnowledgeFact]) -> DailyBrief:
        """Generate a validated, presentation-independent Daily Brief from facts."""
        user_prompt = DAILY_REPORT_PROMPT.format(facts=_format_facts(facts))
        response = self._provider.generate(SYSTEM_PROMPT, user_prompt)
        return _parse_daily_brief(response)

    def generate_daily_report(self, facts: Sequence[KnowledgeFact]) -> str:
        """Generate the Markdown rendering of a structured Daily Brief."""
        return render_daily_brief(self.generate_daily_brief(facts))


def _format_facts(facts: Sequence[KnowledgeFact]) -> str:
    """Convert public knowledge objects into compact, provider-neutral prompt text."""
    if not facts:
        return "- No listening facts are available."

    return "\n".join(
        f"- [{fact.category}] {fact.title}: {fact.description}" for fact in facts
    )


def _parse_daily_brief(response: str) -> DailyBrief:
    """Decode and validate the JSON Daily Brief returned by the configured provider."""
    try:
        payload = json.loads(response)
    except json.JSONDecodeError as error:
        raise RuntimeError("LLM provider returned an invalid Daily Brief response.") from error

    if not isinstance(payload, dict):
        raise RuntimeError("LLM provider returned an invalid Daily Brief response.")

    try:
        return DailyBrief.from_payload(payload)
    except ValueError as error:
        raise RuntimeError("LLM provider returned an invalid Daily Brief response.") from error
