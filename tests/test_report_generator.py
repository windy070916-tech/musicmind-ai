from dataclasses import dataclass
import json

import pytest

from music_ai.ai.base import LLMProvider
from music_ai.ai.daily_brief import DailyBrief
from music_ai.ai.prompts import SYSTEM_PROMPT
from music_ai.ai.report_generator import ReportGenerator
from music_ai.knowledge import FactCategory, ImportanceLevel, InsightType, KnowledgeFact


@dataclass
class FakeProvider(LLMProvider):
    system_prompt: str | None = None
    user_prompt: str | None = None
    response: str = json.dumps(
        {
            "greeting": "Hello.",
            "listening_summary": ["You listened for two hours."],
            "trend": "Listening time increased.",
            "insight": "Your listening was focused.",
            "recommendation": "Stay curious about what you return to.",
            "closing": "See you tomorrow.",
        }
    )

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.response


def test_report_generator_builds_prompt_from_knowledge_facts() -> None:
    provider = FakeProvider()
    fact = KnowledgeFact(
        category=FactCategory.LISTENING_TIME,
        importance=ImportanceLevel.MEDIUM,
        title="Listening Time",
        description="You listened to music for 2 hours today.",
        insight_type=InsightType.DAILY_LISTENING,
    )

    report = ReportGenerator(provider).generate_daily_report([fact])

    assert report.startswith("# MusicMind Daily Brief")
    assert "## 🎵 Listening Summary" in report
    assert provider.system_prompt == SYSTEM_PROMPT
    assert "The Recommendation field is a gentle reflection" in provider.system_prompt
    assert "Greeting and Closing must be warm but non-factual" in provider.system_prompt
    assert provider.user_prompt is not None
    assert "Create a Daily Brief from the listening facts below." in provider.user_prompt
    assert (
        "- [listening_time] Listening Time: You listened to music for 2 hours today."
        in provider.user_prompt
    )


def test_report_generator_handles_empty_fact_list() -> None:
    provider = FakeProvider()

    ReportGenerator(provider).generate_daily_report([])

    assert provider.user_prompt is not None
    assert "- No listening facts are available." in provider.user_prompt


def test_report_generator_exposes_a_structured_daily_brief() -> None:
    brief = ReportGenerator(FakeProvider()).generate_daily_brief([])

    assert isinstance(brief, DailyBrief)
    assert brief.greeting == "Hello."


def test_report_generator_rejects_non_schema_provider_responses() -> None:
    with pytest.raises(RuntimeError, match="invalid Daily Brief"):
        ReportGenerator(FakeProvider(response="not JSON")).generate_daily_report([])
