"""Post-Narrative localization for immutable Knowledge facts."""

from dataclasses import dataclass

from music_ai.knowledge.models import KnowledgeFact
from music_ai.localization.catalog import chinese_fact_template
from music_ai.localization.models import (
    LocalizationError,
    SupportedLocale,
    require_supported_locale,
)


@dataclass(frozen=True, slots=True)
class LocalizedFact:
    """Localized presentation text derived without mutating its source fact."""

    title: str
    description: str


def localize_fact(
    fact: KnowledgeFact, locale: SupportedLocale
) -> LocalizedFact:
    """Render canonical English or controlled Simplified Chinese fact text."""
    locale = require_supported_locale(locale)
    if locale is SupportedLocale.EN_US:
        return LocalizedFact(fact.title, fact.description)
    if fact.message_key is None:
        raise LocalizationError(
            "Cannot localize a KnowledgeFact without message_key to zh-CN."
        )

    template = chinese_fact_template(fact.message_key)
    missing = template.required_metadata - set(fact.metadata)
    if missing:
        names = ", ".join(sorted(missing))
        raise LocalizationError(
            f"Fact {fact.message_key.value} is missing localization metadata: {names}."
        )
    try:
        description = template.render_description(fact.metadata)
    except LocalizationError:
        raise
    except (KeyError, TypeError, ValueError) as error:
        raise LocalizationError(
            f"Could not localize fact {fact.message_key.value}: {error}"
        ) from error
    if not description:
        raise LocalizationError(
            f"Fact {fact.message_key.value} produced an empty description."
        )
    return LocalizedFact(template.title, description)
