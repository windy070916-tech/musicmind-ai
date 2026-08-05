from dataclasses import dataclass
import json

import pytest

from music_ai.ai.base import LLMProvider
from music_ai.ai.daily_brief import DailyBrief
from music_ai.ai.prompts import SYSTEM_PROMPT, build_system_prompt
from music_ai.ai.report_generator import ReportGenerator
from music_ai.knowledge import (
    FactCategory,
    FactMessageKey,
    ImportanceLevel,
    InsightType,
    KnowledgeFact,
)
from music_ai.localization import SupportedLocale


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
    assert provider.system_prompt == build_system_prompt(SupportedLocale.EN_US)
    assert provider.system_prompt.startswith(SYSTEM_PROMPT)
    assert "every user-visible JSON string value in English" in provider.system_prompt
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


def test_chinese_report_uses_language_instruction_and_canonical_fact_input() -> None:
    provider = FakeProvider()
    fact = KnowledgeFact(
        category=FactCategory.LISTENING_TIME,
        importance=ImportanceLevel.MEDIUM,
        title="Listening Time",
        description="You listened to music for 2 hours today.",
        message_key=FactMessageKey.DAILY_LISTENING_TIME,
    )
    report = ReportGenerator(
        provider,
        locale=SupportedLocale.ZH_CN,
    ).generate_daily_report([fact])
    assert report.startswith("# MusicMind AI 每日报告")
    assert "natural Simplified Chinese" in (provider.system_prompt or "")
    assert "Keep artist, track, album, and genre names exactly as supplied." in (
        provider.system_prompt or ""
    )
    assert "You listened to music for 2 hours today." in (provider.user_prompt or "")
    assert "daily.listening_time" not in (provider.user_prompt or "")


def test_locale_prompts_are_stable_and_do_not_leak_fixed_english_output() -> None:
    original = SYSTEM_PROMPT

    chinese_first = build_system_prompt(SupportedLocale.ZH_CN)
    english_second = build_system_prompt(SupportedLocale.EN_US)
    english_first = build_system_prompt(SupportedLocale.EN_US)
    chinese_second = build_system_prompt(SupportedLocale.ZH_CN)

    assert SYSTEM_PROMPT == original
    assert chinese_first == chinese_second
    assert english_first == english_second
    assert "natural Simplified Chinese" in chinese_first
    assert "every user-visible JSON string value in English" in english_first
    assert "Keep artist, track, album, and genre names exactly as supplied." in (
        chinese_first
    )
    assert "neutral fallback in natural Simplified Chinese" in chinese_first
    assert "neutral fallback in English" in english_first
    for prompt in (chinese_first, english_first):
        assert "Use only the supplied listening facts." in prompt
        assert "Return only valid JSON with exactly these fields" in prompt
        assert "The Recommendation field is a gentle reflection" in prompt
    assert "No additional pattern stands out yet." not in chinese_first
    assert "Keep noticing what you return to most." not in chinese_first
    assert "Let tomorrow's listening unfold naturally." not in chinese_first


def test_report_generator_exposes_a_structured_daily_brief() -> None:
    brief = ReportGenerator(FakeProvider()).generate_daily_brief([])

    assert isinstance(brief, DailyBrief)
    assert brief.greeting == "Hello."


def test_report_generator_rejects_non_schema_provider_responses() -> None:
    with pytest.raises(RuntimeError, match="invalid Daily Brief"):
        ReportGenerator(FakeProvider(response="not JSON")).generate_daily_report([])
