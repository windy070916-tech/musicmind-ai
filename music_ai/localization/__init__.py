"""Deterministic runtime localization for MusicMind user-facing output."""

from importlib import import_module

from music_ai.localization.models import (
    LocalizationError,
    MissingTranslationError,
    SupportedLocale,
    UnsupportedLocaleError,
)


__all__ = [
    "LocalizationError",
    "LocalizedFact",
    "MissingTranslationError",
    "SupportedLocale",
    "UnsupportedLocaleError",
    "localize_fact",
    "resolve_locale",
    "ui_text",
    "validate_localization_catalogs",
]

_EXPORTS = {
    "LocalizedFact": ("music_ai.localization.fact_localizer", "LocalizedFact"),
    "localize_fact": ("music_ai.localization.fact_localizer", "localize_fact"),
    "resolve_locale": ("music_ai.localization.resolver", "resolve_locale"),
    "ui_text": ("music_ai.localization.catalog", "ui_text"),
    "validate_localization_catalogs": ("music_ai.localization.catalog", "validate_localization_catalogs"),
}


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    value = getattr(import_module(target[0]), target[1])
    globals()[name] = value
    return value
