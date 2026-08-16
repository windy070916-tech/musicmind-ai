"""Minimal rendering for a validated dynamic MusicMind AI brief."""

from music_ai.ai.interpretation_brief import InterpretationBrief


def render_interpretation_brief(brief: InterpretationBrief) -> str:
    """Render at most three plain-text paragraphs in deterministic plan order."""
    if not isinstance(brief, InterpretationBrief):
        raise TypeError("brief must be InterpretationBrief.")
    return "\n\n".join(item.text for item in brief.items)
