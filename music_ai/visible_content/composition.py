"""Post-selection deterministic report composition and visible manifest."""

from dataclasses import dataclass
from enum import StrEnum

from music_ai.analytics.listening_profile import (
    RankedArtist,
    RankedGenre,
    RankedTrack,
)
from music_ai.knowledge.evidence_reference import knowledge_evidence_id
from music_ai.knowledge.models import FactCategory, InsightType, KnowledgeFact
from music_ai.narrative.models import DailyNarrative
from music_ai.visible_content.models import (
    VisibleContentManifest,
    VisibleContentReference,
    VisibleSection,
)


_BASIC_DAILY_CATEGORIES = {
    FactCategory.LISTENING_TIME,
    FactCategory.PLAYBACK_COUNT,
    FactCategory.TOP_ARTIST,
    FactCategory.TOP_SONG,
}


class VisibleProfileState(StrEnum):
    """Final presentation state of the deterministic listening overview."""

    UNAVAILABLE = "unavailable"
    NO_ACTIVITY = "no_activity"
    ACTIVE = "active"


@dataclass(frozen=True, slots=True)
class VisibleProfileSummary:
    """The three locale-neutral summary measurements rendered for an active day."""

    total_estimated_listening_duration_ms: int
    playback_count: int
    unique_track_count: int


@dataclass(frozen=True, slots=True)
class VisibleReportComposition:
    """Exactly selected deterministic report content before localization.

    Presentation and the Visible Content Manifest consume the same immutable
    selection so final display limits cannot drift from anti-restatement evidence.
    """

    subtitle: str | None
    profile_state: VisibleProfileState
    profile_summary: VisibleProfileSummary | None
    top_artists: tuple[RankedArtist, ...]
    top_tracks: tuple[RankedTrack, ...]
    top_genres: tuple[RankedGenre, ...]
    recent_observations: tuple[KnowledgeFact, ...]
    long_term_observations: tuple[KnowledgeFact, ...]
    highlights: tuple[KnowledgeFact, ...]
    manifest: VisibleContentManifest

    def __post_init__(self) -> None:
        for name in (
            "top_artists",
            "top_tracks",
            "top_genres",
            "recent_observations",
            "long_term_observations",
            "highlights",
        ):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if self.profile_state == VisibleProfileState.ACTIVE:
            if self.profile_summary is None:
                raise ValueError("An active profile requires a visible summary.")
        elif self.profile_summary is not None:
            raise ValueError("Only an active profile may have a visible summary.")


def compose_visible_report(narrative: DailyNarrative) -> VisibleReportComposition:
    """Apply final display selection once for rendering and manifest generation."""
    if not isinstance(narrative, DailyNarrative):
        raise TypeError("narrative must be a DailyNarrative.")

    subtitle = _subtitle(narrative.headline)
    profile = narrative.listening_profile
    if profile is None:
        profile_state = VisibleProfileState.UNAVAILABLE
        profile_summary = None
        top_artists: tuple[RankedArtist, ...] = ()
        top_tracks: tuple[RankedTrack, ...] = ()
        top_genres: tuple[RankedGenre, ...] = ()
    elif profile.playback_count == 0:
        profile_state = VisibleProfileState.NO_ACTIVITY
        profile_summary = None
        top_artists = ()
        top_tracks = ()
        top_genres = ()
    else:
        profile_state = VisibleProfileState.ACTIVE
        profile_summary = VisibleProfileSummary(
            total_estimated_listening_duration_ms=(
                profile.total_estimated_listening_duration_ms
            ),
            playback_count=profile.playback_count,
            unique_track_count=profile.unique_track_count,
        )
        top_artists = tuple(profile.top_artists[:3])
        top_tracks = tuple(profile.top_tracks[:5])
        top_genres = tuple(profile.top_genres[:3])

    recent = (
        narrative.recent_thread.observations
        if narrative.recent_thread is not None
        else ()
    )
    long_term = (
        narrative.long_term_thread.observations
        if narrative.long_term_thread is not None
        else ()
    )
    highlights = tuple(_eligible_highlights(narrative.highlights))[:3]
    manifest = _build_manifest(
        subtitle=subtitle,
        profile_state=profile_state,
        profile_summary=profile_summary,
        top_artists=top_artists,
        top_tracks=top_tracks,
        top_genres=top_genres,
        recent=recent,
        long_term=long_term,
        highlights=highlights,
    )
    return VisibleReportComposition(
        subtitle=subtitle,
        profile_state=profile_state,
        profile_summary=profile_summary,
        top_artists=top_artists,
        top_tracks=top_tracks,
        top_genres=top_genres,
        recent_observations=recent,
        long_term_observations=long_term,
        highlights=highlights,
        manifest=manifest,
    )


def _eligible_highlights(facts: tuple[KnowledgeFact, ...]):
    for fact in facts:
        if fact.insight_type == InsightType.DAILY_LISTENING:
            continue
        if fact.category in _BASIC_DAILY_CATEGORIES:
            continue
        yield fact


def _subtitle(headline: str) -> str | None:
    normalized = headline.strip()
    if not normalized or normalized.casefold() in {
        "daily listening",
        "musicmind daily",
    }:
        return None
    return normalized


def _build_manifest(
    *,
    subtitle: str | None,
    profile_state: VisibleProfileState,
    profile_summary: VisibleProfileSummary | None,
    top_artists: tuple[RankedArtist, ...],
    top_tracks: tuple[RankedTrack, ...],
    top_genres: tuple[RankedGenre, ...],
    recent: tuple[KnowledgeFact, ...],
    long_term: tuple[KnowledgeFact, ...],
    highlights: tuple[KnowledgeFact, ...],
) -> VisibleContentManifest:
    references = [
        VisibleContentReference(
            reference_id="visible:today:summary",
            section=VisibleSection.TODAY,
            concept="today_summary",
            horizon="daily",
        )
    ]
    if subtitle is not None:
        references.append(
            VisibleContentReference(
                reference_id="visible:today:headline",
                section=VisibleSection.TODAY,
                concept="report_headline",
                horizon="daily",
            )
        )
    if profile_state == VisibleProfileState.UNAVAILABLE:
        references.append(
            VisibleContentReference(
                reference_id="visible:today:unavailable",
                section=VisibleSection.TODAY,
                concept="listening_unavailable",
                horizon="daily",
            )
        )
    elif profile_state == VisibleProfileState.NO_ACTIVITY:
        references.append(
            VisibleContentReference(
                reference_id="visible:today:no_activity",
                section=VisibleSection.TODAY,
                concept="no_listening_activity",
                horizon="daily",
            )
        )
    elif profile_summary is not None:
        for concept in (
            "estimated_listening_duration",
            "playback_count",
            "distinct_tracks",
        ):
            references.append(
                VisibleContentReference(
                    reference_id=f"visible:today:{concept}",
                    section=VisibleSection.TODAY,
                    concept=concept,
                    horizon="daily",
                )
            )

    references.extend(
        VisibleContentReference(
            reference_id=f"visible:artist:{rank}:{_artist_key(artist)}",
            section=VisibleSection.TOP_ARTISTS,
            concept="top_artist",
            subject_key=_artist_key(artist),
            category="profile",
            horizon="daily",
        )
        for rank, artist in enumerate(top_artists, start=1)
    )
    references.extend(
        VisibleContentReference(
            reference_id=f"visible:track:{rank}:{track.spotify_track_id}",
            section=VisibleSection.TOP_TRACKS,
            concept="top_track",
            subject_key=f"track:{track.spotify_track_id}",
            category="profile",
            horizon="daily",
        )
        for rank, track in enumerate(top_tracks, start=1)
    )
    references.extend(
        VisibleContentReference(
            reference_id=f"visible:genre:{rank}:{genre.genre.casefold()}",
            section=VisibleSection.GENRES,
            concept="top_genre",
            subject_key=f"genre:{genre.genre.strip().casefold()}",
            category="profile",
            horizon="daily",
        )
        for rank, genre in enumerate(top_genres, start=1)
    )
    for section, facts in (
        (VisibleSection.RECENT, recent),
        (VisibleSection.LONG_TERM, long_term),
        (VisibleSection.HIGHLIGHTS, highlights),
    ):
        references.extend(
            _fact_reference(section, position, fact)
            for position, fact in enumerate(facts, start=1)
        )
    return VisibleContentManifest(tuple(references))


def _fact_reference(
    section: VisibleSection,
    position: int,
    fact: KnowledgeFact,
) -> VisibleContentReference:
    concept = _semantic_metadata(fact, "concept_key") or str(fact.category)
    subject = _semantic_metadata(fact, "subject_key")
    direction = _semantic_metadata(fact, "direction")
    evidence_id = knowledge_evidence_id(fact)
    return VisibleContentReference(
        reference_id=f"visible:{section}:{position}:{evidence_id}",
        section=section,
        concept=concept,
        subject_key=subject or None,
        direction=direction or None,
        category=str(fact.category),
        horizon=str(fact.time_horizon),
        evidence_id=evidence_id,
    )


def _semantic_metadata(fact: KnowledgeFact, key: str) -> str:
    value = fact.metadata.get(key)
    return value if isinstance(value, str) and value.strip() else ""


def _artist_key(artist: RankedArtist) -> str:
    if artist.spotify_artist_id:
        return f"spotify:{artist.spotify_artist_id}"
    return f"legacy:{artist.name.strip().casefold()}"
