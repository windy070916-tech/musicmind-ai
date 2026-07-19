import pytest

from music_ai.ai.daily_brief import DailyBrief
from music_ai.ai.markdown_renderer import render_daily_brief


def test_daily_brief_validates_provider_payload() -> None:
    brief = DailyBrief.from_payload(
        {
            "greeting": "A calm start to your day.",
            "listening_summary": ["You spent two hours with music."],
            "trend": "Your listening time increased.",
            "insight": "One artist held your attention.",
            "recommendation": "Stay curious about what you return to.",
            "closing": "Enjoy the rest of your day.",
        }
    )

    assert brief.listening_summary == ("You spent two hours with music.",)


def test_daily_brief_rejects_missing_or_invalid_fields() -> None:
    with pytest.raises(ValueError, match="greeting"):
        DailyBrief.from_payload({})


def test_markdown_renderer_uses_the_complete_daily_brief_structure() -> None:
    brief = DailyBrief(
        greeting="Hello.",
        listening_summary=("You listened for two hours.", "Kanye West led the day."),
        trend="Listening time increased.",
        insight="Your listening was focused.",
        recommendation="Notice what made that artist stand out.",
        closing="See you tomorrow.",
    )

    markdown = render_daily_brief(brief)

    assert markdown.startswith("# MusicMind Daily Brief")
    assert "## 👋 Greeting" in markdown
    assert "## 🎵 Listening Summary" in markdown
    assert "- You listened for two hours." in markdown
    assert "## 📈 Trend" in markdown
    assert "## 🧠 Insight" in markdown
    assert "## 💡 Recommendation" in markdown
    assert markdown.endswith("See you tomorrow.")
