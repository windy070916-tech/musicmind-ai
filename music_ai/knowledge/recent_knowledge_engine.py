"""Interpret deterministic Temporal Evidence as reusable Knowledge facts."""

from music_ai.knowledge.models import (
    FactCategory,
    FactSource,
    FactTimeHorizon,
    ImportanceLevel,
    InsightType,
    KnowledgeFact,
)
from music_ai.temporal.models import (
    ArtistContinuityEvidence,
    ArtistEmergenceEvidence,
    RecentListeningEvidence,
)


_MEANINGFUL_CONTINUITY_SHARE = 0.5
_MEANINGFUL_RECENT_ARTIST_SHARE = 0.25
_MEANINGFUL_EMERGENCE_CHANGE = 0.15


class RecentKnowledgeEngine:
    """Interpret completed Temporal Evidence without reading Memory."""

    def __init__(self, evidence: RecentListeningEvidence) -> None:
        if not isinstance(evidence, RecentListeningEvidence):
            raise TypeError("evidence must be RecentListeningEvidence.")
        self._evidence = evidence

    def generate_facts(self) -> list[KnowledgeFact]:
        """Return only recent observations supported by meaningful evidence."""
        facts: list[KnowledgeFact] = []
        for evidence in self._evidence.continuity:
            fact = _continuity_fact(evidence)
            if fact is not None:
                facts.append(fact)
        for evidence in self._evidence.emergence:
            fact = _emergence_fact(evidence)
            if fact is not None:
                facts.append(fact)
        return facts


def _continuity_fact(
    evidence: ArtistContinuityEvidence,
) -> KnowledgeFact | None:
    """Interpret a newly sufficient repeated rank-one pattern."""
    if (
        not evidence.evidence_sufficient
        or not evidence.continuity_transition
        or evidence.qualifying_day_share < _MEANINGFUL_CONTINUITY_SHARE
    ):
        return None

    return KnowledgeFact(
        category=FactCategory.ARTIST_CONTINUITY,
        importance=ImportanceLevel.MEDIUM,
        title="Artist Continuity",
        description=(
            f"{evidence.artist_name} was your top artist on "
            f"{evidence.qualifying_day_count} of "
            f"{evidence.listening_day_count} recent listening days."
        ),
        metadata={
            "subject_key": _subject_key(
                evidence.spotify_artist_id, evidence.artist_name
            ),
            "spotify_artist_id": evidence.spotify_artist_id,
            "artist_name": evidence.artist_name,
            "recorded_day_count": evidence.recorded_day_count,
            "listening_day_count": evidence.listening_day_count,
            "qualifying_day_count": evidence.qualifying_day_count,
            "qualifying_day_share": evidence.qualifying_day_share,
            "gap_dates": tuple(
                value.isoformat() for value in evidence.gap_dates
            ),
            "contains_open_day": evidence.contains_open_day,
        },
        confidence=1.0,
        tags=("recent", "artist_continuity"),
        source=FactSource.RECENT_LISTENING_EVIDENCE,
        date_range=(
            evidence.window_start_date.isoformat(),
            evidence.window_end_date.isoformat(),
        ),
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.RECENT,
    )


def _emergence_fact(
    evidence: ArtistEmergenceEvidence,
) -> KnowledgeFact | None:
    """Interpret a sufficiently large positive prominence transition."""
    if (
        not evidence.evidence_sufficient
        or not evidence.emergence_transition
        or evidence.recent_duration_share is None
        or evidence.comparison_duration_share is None
        or evidence.duration_share_change is None
        or evidence.recent_duration_share < _MEANINGFUL_RECENT_ARTIST_SHARE
        or evidence.duration_share_change < _MEANINGFUL_EMERGENCE_CHANGE
    ):
        return None

    return KnowledgeFact(
        category=FactCategory.ARTIST_EMERGENCE,
        importance=ImportanceLevel.HIGH,
        title="Artist Emergence",
        description=(
            f"{evidence.artist_name} grew from "
            f"{evidence.comparison_duration_share:.0%} to "
            f"{evidence.recent_duration_share:.0%} of your listening time."
        ),
        metadata={
            "subject_key": _subject_key(
                evidence.spotify_artist_id, evidence.artist_name
            ),
            "spotify_artist_id": evidence.spotify_artist_id,
            "artist_name": evidence.artist_name,
            "recent_duration_share": evidence.recent_duration_share,
            "comparison_duration_share": evidence.comparison_duration_share,
            "duration_share_change": evidence.duration_share_change,
            "recent_recorded_day_count": evidence.recent_recorded_day_count,
            "comparison_recorded_day_count": (
                evidence.comparison_recorded_day_count
            ),
            "recent_closed_listening_day_count": (
                evidence.recent_closed_listening_day_count
            ),
            "comparison_closed_listening_day_count": (
                evidence.comparison_closed_listening_day_count
            ),
            "recent_closed_artist_day_count": (
                evidence.recent_closed_artist_day_count
            ),
            "recent_gap_dates": tuple(
                value.isoformat() for value in evidence.recent_gap_dates
            ),
            "comparison_gap_dates": tuple(
                value.isoformat() for value in evidence.comparison_gap_dates
            ),
            "contains_open_day": evidence.contains_open_day,
        },
        confidence=1.0,
        tags=("recent", "artist_emergence"),
        source=FactSource.RECENT_LISTENING_EVIDENCE,
        date_range=(
            evidence.comparison_start_date.isoformat(),
            evidence.recent_end_date.isoformat(),
        ),
        insight_type=InsightType.BEHAVIOR,
        time_horizon=FactTimeHorizon.RECENT,
    )


def _subject_key(spotify_artist_id: str | None, artist_name: str) -> str:
    if spotify_artist_id:
        return f"spotify:{spotify_artist_id}"
    return f"legacy:{artist_name.strip().casefold()}"
