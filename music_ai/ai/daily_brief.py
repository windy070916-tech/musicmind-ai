"""Structured Daily Brief model shared by AI report renderers."""

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DailyBrief:
    """A presentation-independent daily briefing generated from knowledge facts."""

    greeting: str
    listening_summary: tuple[str, ...]
    trend: str
    insight: str
    recommendation: str
    closing: str

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> "DailyBrief":
        """Validate a provider payload and return a reusable Daily Brief."""
        return cls(
            greeting=_required_text(payload, "greeting"),
            listening_summary=_summary_items(payload),
            trend=_required_text(payload, "trend"),
            insight=_required_text(payload, "insight"),
            recommendation=_required_text(payload, "recommendation"),
            closing=_required_text(payload, "closing"),
        )


def _required_text(payload: Mapping[str, object], key: str) -> str:
    """Return one required, non-empty text field from a provider payload."""
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Daily Brief field '{key}' must be a non-empty string.")
    return value.strip()


def _summary_items(payload: Mapping[str, object]) -> tuple[str, ...]:
    """Return the non-empty summary lines from a provider payload."""
    value = payload.get("listening_summary")
    if not isinstance(value, list) or not value:
        raise ValueError("Daily Brief field 'listening_summary' must be a non-empty list.")

    items = tuple(item.strip() for item in value if isinstance(item, str) and item.strip())
    if len(items) != len(value):
        raise ValueError("Daily Brief summary items must be non-empty strings.")
    return items
