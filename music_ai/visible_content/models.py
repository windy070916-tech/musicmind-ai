"""Locale-neutral semantic references for deterministic content shown to users."""

from dataclasses import dataclass
from enum import StrEnum


class VisibleSection(StrEnum):
    """Finite deterministic report sections represented by the manifest."""

    TODAY = "today"
    TOP_ARTISTS = "top_artists"
    TOP_TRACKS = "top_tracks"
    GENRES = "genres"
    HIGHLIGHTS = "highlights"
    RECENT = "recent"
    LONG_TERM = "long_term"


@dataclass(frozen=True, slots=True)
class VisibleContentReference:
    """One semantic concept actually selected for deterministic presentation.

    These fields intentionally contain identifiers rather than localized or rendered
    prose. ``evidence_id`` connects a visible Knowledge observation to a Signal's
    provenance without exposing the observation's text to the interpretation layer.
    """

    reference_id: str
    section: VisibleSection
    concept: str
    subject_key: str | None = None
    direction: str | None = None
    category: str | None = None
    horizon: str | None = None
    evidence_id: str | None = None

    def __post_init__(self) -> None:
        _require_identifier("reference_id", self.reference_id)
        if not isinstance(self.section, VisibleSection):
            raise TypeError("section must be a VisibleSection.")
        _require_identifier("concept", self.concept)
        for name in (
            "subject_key",
            "direction",
            "category",
            "horizon",
            "evidence_id",
        ):
            value = getattr(self, name)
            if value is not None:
                _require_identifier(name, value)

    @property
    def semantic_key(
        self,
    ) -> tuple[str, str, str, str, str]:
        """Return the locale-independent dimensions used for exact matching."""
        return (
            self.concept,
            self.subject_key or "",
            self.direction or "",
            self.category or "",
            self.horizon or "",
        )


@dataclass(frozen=True, slots=True)
class VisibleContentManifest:
    """An immutable ordered snapshot of deterministic concepts actually shown."""

    references: tuple[VisibleContentReference, ...] = ()

    def __post_init__(self) -> None:
        references = tuple(self.references)
        if any(not isinstance(item, VisibleContentReference) for item in references):
            raise TypeError(
                "VisibleContentManifest references must be "
                "VisibleContentReference values."
            )
        reference_ids = [item.reference_id for item in references]
        if len(reference_ids) != len(set(reference_ids)):
            raise ValueError(
                "VisibleContentManifest reference identifiers must be unique."
            )
        object.__setattr__(self, "references", references)

    @property
    def evidence_ids(self) -> frozenset[str]:
        """Return Knowledge evidence identifiers represented by visible content."""
        return frozenset(
            item.evidence_id
            for item in self.references
            if item.evidence_id is not None
        )

    def contains_evidence(self, evidence_id: str) -> bool:
        """Return whether one qualified Knowledge observation is already visible."""
        return evidence_id in self.evidence_ids

    def contains_semantic(
        self,
        *,
        concept: str,
        subject_key: str | None = None,
        direction: str | None = None,
        category: str | None = None,
        horizon: str | None = None,
    ) -> bool:
        """Match one exact locale-neutral semantic reference."""
        key = (
            concept,
            subject_key or "",
            direction or "",
            category or "",
            horizon or "",
        )
        return any(item.semantic_key == key for item in self.references)

    def matches_semantic(
        self,
        *,
        concept: str,
        subject_key: str | None = None,
        direction: str | None = None,
        category: str | None = None,
        horizon: str | None = None,
    ) -> bool:
        """Match supplied semantic dimensions while treating omissions as wildcards.

        Planner Signals do not own presentation categories.  This matcher lets the
        anti-restatement boundary compare the semantic dimensions a Signal does own
        without requiring it to invent a visible-section category.
        """
        constraints = {
            "concept": concept,
            "subject_key": subject_key,
            "direction": direction,
            "category": category,
            "horizon": horizon,
        }
        for name, value in constraints.items():
            if value is not None:
                _require_identifier(name, value)
        return any(
            all(
                expected is None or getattr(reference, name) == expected
                for name, expected in constraints.items()
            )
            for reference in self.references
        )


def _require_identifier(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string.")
    if "\n" in value or "\r" in value:
        raise ValueError(f"{name} must not contain rendered multiline text.")
