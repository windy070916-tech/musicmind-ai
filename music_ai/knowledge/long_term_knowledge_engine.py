"""Interpret long-term Temporal Evidence as reusable Knowledge facts."""

from music_ai.knowledge.models import (
    FactCategory,
    FactSource,
    FactTimeHorizon,
    ImportanceLevel,
    InsightType,
    KnowledgeFact,
)
from music_ai.knowledge.message_keys import FactMessageKey
from music_ai.temporal.long_term_models import (
    ArtistBreadthEvidence,
    ArtistConsistencyEvidence,
    ListeningConcentrationEvidence,
    LongTermListeningEvidence,
)


_CONSISTENCY_APPEARANCE_DAYS = 8
_CONSISTENCY_APPEARANCE_SHARE = 0.50
_CONSISTENCY_CLOSED_SUPPORTING_DAYS = 6
_CONCENTRATION_TOP_FIVE_SHARE = 0.70
_BREADTH_UNIQUE_ARTISTS = 20
_BREADTH_ARTISTS_PER_DAY = 2.0
_BREADTH_SINGLE_DAY_ARTISTS = 8


class LongTermKnowledgeEngine:
    """Apply product meaning to completed long-term evidence only."""

    def __init__(self, evidence: LongTermListeningEvidence) -> None:
        if not isinstance(evidence, LongTermListeningEvidence):
            raise TypeError("evidence must be LongTermListeningEvidence.")
        self._evidence = evidence

    def generate_facts(self) -> tuple[KnowledgeFact, ...]:
        """Return at most one newly qualifying fact for each concept."""
        facts: list[KnowledgeFact] = []
        consistency = _strongest_new_consistency(self._evidence.artist_consistency)
        if consistency is not None:
            facts.append(_consistency_fact(self._evidence, consistency))

        concentration = self._evidence.listening_concentration
        if _concentration_qualifies(concentration) and not _prefix_concentration_qualifies(
            concentration
        ):
            facts.append(_concentration_fact(self._evidence, concentration))

        breadth = self._evidence.artist_breadth
        if _breadth_qualifies(breadth) and not _prefix_breadth_qualifies(breadth):
            facts.append(_breadth_fact(self._evidence, breadth))
        return tuple(facts)


def _strongest_new_consistency(
    candidates: tuple[ArtistConsistencyEvidence, ...],
) -> ArtistConsistencyEvidence | None:
    qualifying = tuple(
        candidate
        for candidate in candidates
        if _consistency_qualifies(candidate)
        and not _prefix_consistency_qualifies(candidate)
    )
    if not qualifying:
        return None
    return min(
        qualifying,
        key=lambda item: (
            -item.appearance_share,
            -item.appearance_day_count,
            -item.duration_share,
            item.identity,
        ),
    )


def _consistency_qualifies(evidence: ArtistConsistencyEvidence) -> bool:
    return (
        evidence.evidence_sufficient
        and evidence.appearance_day_count >= _CONSISTENCY_APPEARANCE_DAYS
        and evidence.appearance_share >= _CONSISTENCY_APPEARANCE_SHARE
        and evidence.closed_supporting_day_count
        >= _CONSISTENCY_CLOSED_SUPPORTING_DAYS
    )


def _prefix_consistency_qualifies(evidence: ArtistConsistencyEvidence) -> bool:
    return (
        evidence.prefix_evidence_sufficient
        and evidence.prefix_appearance_day_count >= _CONSISTENCY_APPEARANCE_DAYS
        and evidence.prefix_appearance_share >= _CONSISTENCY_APPEARANCE_SHARE
        and evidence.prefix_closed_supporting_day_count
        >= _CONSISTENCY_CLOSED_SUPPORTING_DAYS
    )


def _concentration_qualifies(evidence: ListeningConcentrationEvidence) -> bool:
    return (
        evidence.evidence_sufficient
        and evidence.top_five_duration_share >= _CONCENTRATION_TOP_FIVE_SHARE
    )


def _prefix_concentration_qualifies(
    evidence: ListeningConcentrationEvidence,
) -> bool:
    return (
        evidence.prefix_evidence_sufficient
        and evidence.prefix_top_five_duration_share
        >= _CONCENTRATION_TOP_FIVE_SHARE
    )


def _breadth_qualifies(evidence: ArtistBreadthEvidence) -> bool:
    return (
        evidence.evidence_sufficient
        and evidence.unique_artist_count >= _BREADTH_UNIQUE_ARTISTS
        and evidence.artists_per_listening_day >= _BREADTH_ARTISTS_PER_DAY
        and evidence.single_day_artist_count >= _BREADTH_SINGLE_DAY_ARTISTS
    )


def _prefix_breadth_qualifies(evidence: ArtistBreadthEvidence) -> bool:
    return (
        evidence.prefix_evidence_sufficient
        and evidence.prefix_unique_artist_count >= _BREADTH_UNIQUE_ARTISTS
        and evidence.prefix_artists_per_listening_day >= _BREADTH_ARTISTS_PER_DAY
        and evidence.prefix_single_day_artist_count >= _BREADTH_SINGLE_DAY_ARTISTS
    )


def _consistency_fact(
    context: LongTermListeningEvidence,
    evidence: ArtistConsistencyEvidence,
) -> KnowledgeFact:
    return KnowledgeFact(
        category=FactCategory.ARTIST_CONSISTENCY,
        importance=ImportanceLevel.HIGH,
        title="Artist consistency",
        description=(
            f"{evidence.artist_name} appeared on {evidence.appearance_day_count} of "
            f"{evidence.listening_day_count} recorded listening days in this period."
        ),
        metadata={
            **_shared_metadata(context),
            "subject_key": _subject_key(evidence),
            "concept_key": "artist_consistency",
            "spotify_artist_id": evidence.spotify_artist_id,
            "artist_name": evidence.artist_name,
            "appearance_day_count": evidence.appearance_day_count,
            "appearance_share": evidence.appearance_share,
            "closed_supporting_day_count": evidence.closed_supporting_day_count,
            "aggregate_duration_ms": evidence.aggregate_duration_ms,
            "duration_share": evidence.duration_share,
        },
        confidence=1.0,
        tags=("long_term", "artist_consistency"),
        source=FactSource.LONG_TERM_LISTENING_EVIDENCE,
        date_range=(context.start_date.isoformat(), context.end_date.isoformat()),
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.LONG_TERM,
        message_key=FactMessageKey.LONG_TERM_ARTIST_CONSISTENCY,
    )


def _concentration_fact(
    context: LongTermListeningEvidence,
    evidence: ListeningConcentrationEvidence,
) -> KnowledgeFact:
    return KnowledgeFact(
        category=FactCategory.LISTENING_CONCENTRATION,
        importance=ImportanceLevel.MEDIUM,
        title="Listening concentration",
        description=(
            "The top five artists accounted for "
            f"{evidence.top_five_duration_share:.0%} of recorded listening time "
            "in this period."
        ),
        metadata={
            **_shared_metadata(context),
            "subject_key": "listening:all_artists",
            "concept_key": "listening_concentration",
            "distinct_artist_count": evidence.distinct_artist_count,
            "top_one_duration_share": evidence.top_one_duration_share,
            "top_five_duration_share": evidence.top_five_duration_share,
            "total_attributed_artist_duration_ms": (
                evidence.total_attributed_artist_duration_ms
            ),
            "closed_listening_day_count": evidence.closed_listening_day_count,
        },
        confidence=1.0,
        tags=("long_term", "listening_concentration"),
        source=FactSource.LONG_TERM_LISTENING_EVIDENCE,
        date_range=(context.start_date.isoformat(), context.end_date.isoformat()),
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.LONG_TERM,
        message_key=FactMessageKey.LONG_TERM_LISTENING_CONCENTRATION,
    )


def _breadth_fact(
    context: LongTermListeningEvidence, evidence: ArtistBreadthEvidence
) -> KnowledgeFact:
    return KnowledgeFact(
        category=FactCategory.ARTIST_BREADTH,
        importance=ImportanceLevel.MEDIUM,
        title="Artist breadth",
        description=(
            f"You listened to {evidence.unique_artist_count} artists across "
            f"{evidence.listening_day_count} recorded listening days; "
            f"{evidence.single_day_artist_count} appeared on one day."
        ),
        metadata={
            **_shared_metadata(context),
            "subject_key": "listening:all_artists",
            "concept_key": "artist_breadth",
            "unique_artist_count": evidence.unique_artist_count,
            "single_day_artist_count": evidence.single_day_artist_count,
            "repeated_artist_count": evidence.repeated_artist_count,
            "artists_per_listening_day": evidence.artists_per_listening_day,
            "closed_listening_day_count": evidence.closed_listening_day_count,
        },
        confidence=1.0,
        tags=("long_term", "artist_breadth"),
        source=FactSource.LONG_TERM_LISTENING_EVIDENCE,
        date_range=(context.start_date.isoformat(), context.end_date.isoformat()),
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.LONG_TERM,
        message_key=FactMessageKey.LONG_TERM_ARTIST_BREADTH,
    )


def _shared_metadata(context: LongTermListeningEvidence) -> dict[str, object]:
    return {
        "recorded_day_count": context.recorded_day_count,
        "listening_day_count": context.listening_day_count,
        "closed_day_count": context.closed_day_count,
        "gap_dates": tuple(value.isoformat() for value in context.gap_dates),
        "contains_open_day": context.contains_open_day,
        "total_estimated_listening_duration_ms": (
            context.total_estimated_listening_duration_ms
        ),
    }


def _subject_key(evidence: ArtistConsistencyEvidence) -> str:
    return f"{evidence.identity[0]}:{evidence.identity[1]}"
