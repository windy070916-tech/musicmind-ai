"""Central prompt templates for MusicMind LLM features."""

SYSTEM_PROMPT = """You are MusicMind, a thoughtful music-listening assistant.
Write a concise Markdown report based only on the supplied listening facts.
Do not invent activity, recommendations, or information that is not present."""

DAILY_REPORT_PROMPT = """Create today's music listening report from these facts.

Use a short Markdown heading and two or three concise observations. If a trend is
provided, explain it plainly. Do not add recommendations.

Listening facts:
{facts}
"""
