"""Markdown rendering for MusicMind's structured Daily Brief."""

from music_ai.ai.daily_brief import DailyBrief


def render_daily_brief(brief: DailyBrief) -> str:
    """Render a Daily Brief in the stable Markdown format used by MusicMind."""
    summary = "\n".join(f"- {item}" for item in brief.listening_summary)
    return f"""# MusicMind Daily Brief

## 👋 Greeting

{brief.greeting}

## 🎵 Listening Summary

{summary}

## 📈 Trend

{brief.trend}

## 🧠 Insight

{brief.insight}

## 💡 Recommendation

{brief.recommendation}

## ✨ Closing

{brief.closing}"""
