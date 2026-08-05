"""Markdown rendering for MusicMind's structured Daily Brief."""

from music_ai.ai.daily_brief import DailyBrief
from music_ai.localization.catalog import ui_text
from music_ai.localization.models import SupportedLocale, UiMessageKey


def render_daily_brief(
    brief: DailyBrief,
    *,
    locale: SupportedLocale = SupportedLocale.EN_US,
) -> str:
    """Render a Daily Brief in the stable Markdown format used by MusicMind."""
    summary = "\n".join(f"- {item}" for item in brief.listening_summary)
    return f"""# {ui_text(locale, UiMessageKey.AI_REPORT_TITLE)}

## 👋 {ui_text(locale, UiMessageKey.AI_GREETING)}

{brief.greeting}

## 🎵 {ui_text(locale, UiMessageKey.AI_LISTENING_SUMMARY)}

{summary}

## 📈 {ui_text(locale, UiMessageKey.AI_TREND)}

{brief.trend}

## 🧠 {ui_text(locale, UiMessageKey.AI_INSIGHT)}

{brief.insight}

## 💡 {ui_text(locale, UiMessageKey.AI_RECOMMENDATION)}

{brief.recommendation}

## ✨ {ui_text(locale, UiMessageKey.AI_CLOSING)}

{brief.closing}"""
