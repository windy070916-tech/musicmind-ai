from dataclasses import dataclass

from music_ai.ai.base import LLMProvider
from music_ai.ai.prompts import SYSTEM_PROMPT
from music_ai.ai.report_generator import ReportGenerator
from music_ai.knowledge import FactCategory, ImportanceLevel, InsightType, KnowledgeFact


@dataclass
class FakeProvider(LLMProvider):
    system_prompt: str | None = None
    user_prompt: str | None = None

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return "mock report"


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

    assert report == "mock report"
    assert provider.system_prompt == SYSTEM_PROMPT
    assert provider.user_prompt is not None
    assert "Create today's music listening report from these facts." in provider.user_prompt
    assert (
        "- [listening_time] Listening Time: You listened to music for 2 hours today."
        in provider.user_prompt
    )


def test_report_generator_handles_empty_fact_list() -> None:
    provider = FakeProvider()

    ReportGenerator(provider).generate_daily_report([])

    assert provider.user_prompt is not None
    assert "- No listening facts are available." in provider.user_prompt
