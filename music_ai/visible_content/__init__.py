"""Locale-neutral deterministic report composition and visibility contracts."""

from importlib import import_module

from music_ai.visible_content.models import (
    VisibleContentManifest,
    VisibleContentReference,
    VisibleSection,
)


__all__ = [
    "VisibleContentManifest",
    "VisibleContentReference",
    "VisibleProfileState",
    "VisibleProfileSummary",
    "VisibleReportComposition",
    "VisibleSection",
    "compose_visible_report",
]

_COMPOSITION_EXPORTS = {
    "VisibleProfileState": ("music_ai.visible_content.composition", "VisibleProfileState"),
    "VisibleProfileSummary": ("music_ai.visible_content.composition", "VisibleProfileSummary"),
    "VisibleReportComposition": ("music_ai.visible_content.composition", "VisibleReportComposition"),
    "compose_visible_report": ("music_ai.visible_content.composition", "compose_visible_report"),
}


def __getattr__(name: str):
    target = _COMPOSITION_EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    value = getattr(import_module(target[0]), target[1])
    globals()[name] = value
    return value
