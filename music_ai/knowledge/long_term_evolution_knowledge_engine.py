"""Interpret long-term evolution Evidence as deterministic Knowledge facts."""

from fractions import Fraction

from music_ai.knowledge.message_keys import FactMessageKey
from music_ai.knowledge.models import (
    FactCategory,
    FactSource,
    FactTimeHorizon,
    ImportanceLevel,
    InsightType,
    KnowledgeFact,
)
from music_ai.temporal.long_term_evolution_models import (
    ArtistBreadthEvolutionEvidence,
    ArtistShareEvolutionCandidate,
    ConcentrationEvolutionEvidence,
    LongTermEvolutionEvidence,
)


_ARTIST_SHARE_CHANGE_THRESHOLD = Fraction(15, 100)
_ARTIST_SHARE_WINDOW_THRESHOLD = Fraction(20, 100)
_CONCENTRATION_CHANGE_THRESHOLD = Fraction(15, 100)
_BREADTH_ABSOLUTE_CHANGE_THRESHOLD = Fraction(1, 2)
_BREADTH_RELATIVE_CHANGE_THRESHOLD = Fraction(20, 100)


class LongTermEvolutionKnowledgeEngine:
    """Apply product thresholds to completed adjacent-window evidence."""

    def __init__(self, evidence: LongTermEvolutionEvidence) -> None:
        if not isinstance(evidence, LongTermEvolutionEvidence):
            raise TypeError("evidence must be LongTermEvolutionEvidence.")
        self._evidence = evidence

    def generate_facts(self) -> tuple[KnowledgeFact, ...]:
        """Return qualifying facts in the fixed evolution concept order."""
        if not self._evidence.comparison_evidence_sufficient:
            return ()

        facts: list[KnowledgeFact] = []
        artist = _strongest_qualifying_artist(self._evidence)
        if artist is not None:
            facts.append(_artist_share_fact(self._evidence, artist))

        if _breadth_qualifies(self._evidence.breadth):
            facts.append(_breadth_fact(self._evidence, self._evidence.breadth))

        if _concentration_qualifies(self._evidence.concentration):
            facts.append(
                _concentration_fact(self._evidence, self._evidence.concentration)
            )
        return tuple(facts)


def _strongest_qualifying_artist(
    evidence: LongTermEvolutionEvidence,
) -> ArtistShareEvolutionCandidate | None:
    if not evidence.artist_share_calculable:
        return None
    qualifying: list[tuple[Fraction, ArtistShareEvolutionCandidate]] = []
    for candidate in evidence.artist_share_candidates:
        previous = Fraction(
            candidate.previous_duration_ms,
            candidate.previous_attributed_duration_ms,
        )
        current = Fraction(
            candidate.current_duration_ms,
            candidate.current_attributed_duration_ms,
        )
        absolute_change = abs(current - previous)
        if (
            absolute_change > 0
            and absolute_change >= _ARTIST_SHARE_CHANGE_THRESHOLD
            and max(previous, current) >= _ARTIST_SHARE_WINDOW_THRESHOLD
        ):
            qualifying.append((absolute_change, candidate))
    if not qualifying:
        return None
    return min(
        qualifying,
        key=lambda item: (-item[0], item[1].identity),
    )[1]


def _concentration_qualifies(
    evidence: ConcentrationEvolutionEvidence,
) -> bool:
    if not evidence.is_calculable:
        return False
    previous = Fraction(
        evidence.previous_top_five_duration_ms,
        evidence.previous_attributed_duration_ms,
    )
    current = Fraction(
        evidence.current_top_five_duration_ms,
        evidence.current_attributed_duration_ms,
    )
    change = abs(current - previous)
    return change > 0 and change >= _CONCENTRATION_CHANGE_THRESHOLD


def _breadth_qualifies(evidence: ArtistBreadthEvolutionEvidence) -> bool:
    if not evidence.is_calculable:
        return False
    previous = Fraction(
        evidence.previous_artist_day_count,
        evidence.previous_listening_day_count,
    )
    current = Fraction(
        evidence.current_artist_day_count,
        evidence.current_listening_day_count,
    )
    if previous <= 0:
        return False
    absolute_change = abs(current - previous)
    relative_change = absolute_change / previous
    return (
        absolute_change > 0
        and absolute_change >= _BREADTH_ABSOLUTE_CHANGE_THRESHOLD
        and relative_change >= _BREADTH_RELATIVE_CHANGE_THRESHOLD
    )


def _artist_share_fact(
    context: LongTermEvolutionEvidence,
    evidence: ArtistShareEvolutionCandidate,
) -> KnowledgeFact:
    previous = Fraction(
        evidence.previous_duration_ms,
        evidence.previous_attributed_duration_ms,
    )
    current = Fraction(
        evidence.current_duration_ms,
        evidence.current_attributed_duration_ms,
    )
    direction = "increase" if current > previous else "decrease"
    verb = "increased" if direction == "increase" else "decreased"
    message_key = (
        FactMessageKey.LONG_TERM_ARTIST_SHARE_EVOLUTION_INCREASED
        if direction == "increase"
        else FactMessageKey.LONG_TERM_ARTIST_SHARE_EVOLUTION_DECREASED
    )
    return KnowledgeFact(
        category=FactCategory.ARTIST_DURATION_SHARE_EVOLUTION,
        importance=ImportanceLevel.HIGH,
        title=f"Artist share {verb}",
        description=(
            "The share of attributable artist listening for "
            f"{evidence.artist_name} {verb} from {_format_percentage(previous)} "
            "in the previous 30-day period to "
            f"{_format_percentage(current)} in the current 30-day period."
        ),
        metadata={
            **_common_metadata(
                context,
                subject_key=_subject_key(evidence),
                concept_key="artist_duration_share",
                direction=direction,
                previous_value=float(previous),
                current_value=float(current),
            ),
            "artist_identity": evidence.identity,
            "artist_name": evidence.artist_name,
            "previous_duration_ms": evidence.previous_duration_ms,
            "current_duration_ms": evidence.current_duration_ms,
            "previous_attributed_duration_ms": (
                evidence.previous_attributed_duration_ms
            ),
            "current_attributed_duration_ms": (
                evidence.current_attributed_duration_ms
            ),
            "signed_share_change": float(current - previous),
            "absolute_share_change": float(abs(current - previous)),
        },
        confidence=1.0,
        tags=("long_term", "artist_share_evolution"),
        source=FactSource.LONG_TERM_EVOLUTION_EVIDENCE,
        date_range=(
            context.previous_window.start_date.isoformat(),
            context.current_window.end_date.isoformat(),
        ),
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.LONG_TERM,
        message_key=message_key,
    )


def _breadth_fact(
    context: LongTermEvolutionEvidence,
    evidence: ArtistBreadthEvolutionEvidence,
) -> KnowledgeFact:
    previous = Fraction(
        evidence.previous_artist_day_count,
        evidence.previous_listening_day_count,
    )
    current = Fraction(
        evidence.current_artist_day_count,
        evidence.current_listening_day_count,
    )
    direction = "increase" if current > previous else "decrease"
    verb = "increased" if direction == "increase" else "decreased"
    message_key = (
        FactMessageKey.LONG_TERM_ARTIST_BREADTH_EVOLUTION_INCREASED
        if direction == "increase"
        else FactMessageKey.LONG_TERM_ARTIST_BREADTH_EVOLUTION_DECREASED
    )
    relative_change = (current - previous) / previous
    return KnowledgeFact(
        category=FactCategory.ARTIST_BREADTH_EVOLUTION,
        importance=ImportanceLevel.MEDIUM,
        title=f"Artist breadth {verb}",
        description=(
            f"Artists per listening day {verb} from "
            f"{_format_one_decimal(previous)} in the previous 30-day period to "
            f"{_format_one_decimal(current)} in the current 30-day period."
        ),
        metadata={
            **_common_metadata(
                context,
                subject_key="listening:all_artists",
                concept_key="artist_breadth",
                direction=direction,
                previous_value=float(previous),
                current_value=float(current),
            ),
            "previous_artist_day_count": evidence.previous_artist_day_count,
            "current_artist_day_count": evidence.current_artist_day_count,
            "previous_listening_day_count": evidence.previous_listening_day_count,
            "current_listening_day_count": evidence.current_listening_day_count,
            "signed_change": float(current - previous),
            "absolute_change": float(abs(current - previous)),
            "relative_change": float(relative_change),
            "absolute_relative_change": float(abs(relative_change)),
        },
        confidence=1.0,
        tags=("long_term", "artist_breadth_evolution"),
        source=FactSource.LONG_TERM_EVOLUTION_EVIDENCE,
        date_range=(
            context.previous_window.start_date.isoformat(),
            context.current_window.end_date.isoformat(),
        ),
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.LONG_TERM,
        message_key=message_key,
    )


def _concentration_fact(
    context: LongTermEvolutionEvidence,
    evidence: ConcentrationEvolutionEvidence,
) -> KnowledgeFact:
    previous = Fraction(
        evidence.previous_top_five_duration_ms,
        evidence.previous_attributed_duration_ms,
    )
    current = Fraction(
        evidence.current_top_five_duration_ms,
        evidence.current_attributed_duration_ms,
    )
    direction = "increase" if current > previous else "decrease"
    verb = "increased" if direction == "increase" else "decreased"
    message_key = (
        FactMessageKey.LONG_TERM_LISTENING_CONCENTRATION_EVOLUTION_INCREASED
        if direction == "increase"
        else FactMessageKey.LONG_TERM_LISTENING_CONCENTRATION_EVOLUTION_DECREASED
    )
    return KnowledgeFact(
        category=FactCategory.LISTENING_CONCENTRATION_EVOLUTION,
        importance=ImportanceLevel.MEDIUM,
        title=f"Listening concentration {verb}",
        description=(
            "The top five artists' share of attributable artist listening "
            f"{verb} from {_format_percentage(previous)} in the previous "
            "30-day period to "
            f"{_format_percentage(current)} in the current 30-day period."
        ),
        metadata={
            **_common_metadata(
                context,
                subject_key="listening:all_artists",
                concept_key="listening_concentration",
                direction=direction,
                previous_value=float(previous),
                current_value=float(current),
            ),
            "previous_top_five_duration_ms": (
                evidence.previous_top_five_duration_ms
            ),
            "current_top_five_duration_ms": evidence.current_top_five_duration_ms,
            "previous_attributed_duration_ms": (
                evidence.previous_attributed_duration_ms
            ),
            "current_attributed_duration_ms": evidence.current_attributed_duration_ms,
            "signed_share_change": float(current - previous),
            "absolute_share_change": float(abs(current - previous)),
        },
        confidence=1.0,
        tags=("long_term", "listening_concentration_evolution"),
        source=FactSource.LONG_TERM_EVOLUTION_EVIDENCE,
        date_range=(
            context.previous_window.start_date.isoformat(),
            context.current_window.end_date.isoformat(),
        ),
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.LONG_TERM,
        message_key=message_key,
    )


def _common_metadata(
    context: LongTermEvolutionEvidence,
    *,
    subject_key: str,
    concept_key: str,
    direction: str,
    previous_value: float,
    current_value: float,
) -> dict[str, object]:
    return {
        "subject_key": subject_key,
        "concept_key": concept_key,
        "direction": direction,
        "previous_start_date": context.previous_window.start_date.isoformat(),
        "previous_end_date": context.previous_window.end_date.isoformat(),
        "current_start_date": context.current_window.start_date.isoformat(),
        "current_end_date": context.current_window.end_date.isoformat(),
        "contains_open_snapshot": (
            context.previous_window.contains_open_snapshot
            or context.current_window.contains_open_snapshot
        ),
        "previous_value": previous_value,
        "current_value": current_value,
    }


def _subject_key(evidence: ArtistShareEvolutionCandidate) -> str:
    return f"{evidence.identity[0]}:{evidence.identity[1]}"


def _format_percentage(value: Fraction) -> str:
    return f"{float(value):.0%}"


def _format_one_decimal(value: Fraction) -> str:
    scaled_numerator = value.numerator * 10
    whole_tenths, remainder = divmod(scaled_numerator, value.denominator)
    if remainder * 2 >= value.denominator:
        whole_tenths += 1
    return f"{whole_tenths // 10}.{whole_tenths % 10}"
