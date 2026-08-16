"""Typed, locale-neutral interpretation Signal contracts."""

from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from math import isfinite


SignalScalar = str | int | float | bool


class SignalType(StrEnum):
    """The seven interpretation families frozen for Sprint 4A."""

    ARTIST_PREFERENCE_FORMATION = "artist_preference_formation"
    TEMPORARY_SPIKE_VS_SUSTAINED_GROWTH = (
        "temporary_spike_vs_sustained_growth"
    )
    EXPLORATION_INTENSITY = "exploration_intensity"
    CORE_VS_EXPLORATION_BALANCE = "core_vs_exploration_balance"
    LISTENING_TIME_OF_DAY_PATTERN = "listening_time_of_day_pattern"
    ARTIST_TIME_OF_DAY_AFFINITY = "artist_time_of_day_affinity"
    TIME_PATTERN_EVOLUTION = "time_pattern_evolution"


class SignalState(StrEnum):
    """Finite approved meanings produced by deterministic projection."""

    LOCALLY_EMERGING = "locally_emerging"
    REPEATED_PRESENCE = "repeated_presence"
    SUSTAINED_GROWTH = "sustained_growth"
    ESTABLISHED_CORE_PRESENCE = "established_core_presence"
    SHORT_WINDOW_MOVEMENT = "short_window_movement"
    CONFLICTING_HORIZONS = "conflicting_horizons"
    BROAD_ARTIST_MIX = "broad_artist_mix"
    BROADER_ARTIST_MIX = "broader_artist_mix"
    NARROWER_ARTIST_MIX = "narrower_artist_mix"
    WIDER_MIX_WITH_CONCENTRATED_CORE = (
        "wider_mix_with_concentrated_core"
    )
    OBSERVED_EVENTS_CONCENTRATED_IN_SEGMENT = (
        "observed_events_concentrated_in_segment"
    )
    ARTIST_OVERREPRESENTED_IN_SEGMENT = (
        "artist_overrepresented_in_segment"
    )
    SEGMENT_SHARE_INCREASED = "segment_share_increased"
    SEGMENT_SHARE_DECREASED = "segment_share_decreased"


class EvidenceMaturity(StrEnum):
    """Deterministic product maturity, never a statistical probability."""

    PRELIMINARY = "preliminary"
    SUPPORTED = "supported"
    STRONG = "strong"


class SignalRoleEligibility(StrEnum):
    """Roles for which a qualified Signal may be considered by the Planner."""

    WATCH_ONLY = "watch_only"
    PRIMARY_OR_SECONDARY = "primary_or_secondary"


class SignalHorizon(StrEnum):
    """Compact observation horizons understood by interpretation planning."""

    RECENT = "recent"
    LONG_TERM = "long_term"
    CROSS_HORIZON = "cross_horizon"
    ADJACENT_30_DAY_WINDOWS = "adjacent_30_day_windows"


class WindowLabel(StrEnum):
    """Semantic labels for compact Signal window references."""

    RECENT = "recent"
    LONG_TERM = "long_term"
    PREVIOUS = "previous"
    CURRENT = "current"
    COMBINED = "combined"


class ClaimScope(StrEnum):
    """Finite claim boundaries approved before provider invocation."""

    BOUNDED_ARTIST_LIFECYCLE = "bounded_artist_lifecycle"
    BOUNDED_MOVEMENT_CLASSIFICATION = "bounded_movement_classification"
    WINDOW_RELATIVE_EXPLORATION = "window_relative_exploration"
    CORE_EXPLORATION_COMPOSITION = "core_exploration_composition"
    OBSERVED_EVENT_DISTRIBUTION = "observed_event_distribution"
    OBSERVED_ARTIST_TIME_ASSOCIATION = "observed_artist_time_association"
    OBSERVED_TIME_DISTRIBUTION_CHANGE = (
        "observed_time_distribution_change"
    )


class SignalCaveat(StrEnum):
    """Required semantic limitations carried with a Signal."""

    OBSERVED_LOCAL_HISTORY_ONLY = "observed_local_history_only"
    NOT_FIRST_EVER_DISCOVERY = "not_first_ever_discovery"
    NOT_PERMANENT_PREFERENCE = "not_permanent_preference"
    NO_CAUSAL_OR_PSYCHOLOGICAL_INFERENCE = (
        "no_causal_or_psychological_inference"
    )
    EVENT_COUNT_NOT_LISTENING_TIME = "event_count_not_listening_time"
    NO_ALWAYS_OR_HABIT_CLAIM = "no_always_or_habit_claim"
    CURRENT_OPEN_DAY_EXCLUDED = "current_open_day_excluded"


@dataclass(frozen=True, slots=True)
class ObservationWindow:
    """One half-open local-date window referenced by a Signal."""

    label: WindowLabel
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if not isinstance(self.label, WindowLabel):
            raise TypeError("label must be WindowLabel.")
        if not isinstance(self.start_date, date) or not isinstance(
            self.end_date, date
        ):
            raise TypeError("Signal window boundaries must be dates.")
        if self.start_date >= self.end_date:
            raise ValueError("Signal window start_date must be before end_date.")


@dataclass(frozen=True, slots=True)
class SupportDimension:
    """One compact observable dimension material to Signal maturity."""

    name: str
    value: SignalScalar

    def __post_init__(self) -> None:
        _validate_named_scalar(self.name, self.value, "support dimension")


@dataclass(frozen=True, slots=True)
class ReferenceValue:
    """One limited value useful when phrasing an approved interpretation."""

    name: str
    value: SignalScalar

    def __post_init__(self) -> None:
        _validate_named_scalar(self.name, self.value, "reference value")


@dataclass(frozen=True, slots=True)
class KnowledgeEvidenceRef:
    """Traceable reference to one canonical Knowledge observation."""

    evidence_id: str
    category: str
    date_range: tuple[str, str] | None

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_id, str) or not self.evidence_id.strip():
            raise ValueError("evidence_id must be a non-empty string.")
        if not isinstance(self.category, str) or not self.category.strip():
            raise ValueError("category must be a non-empty string.")
        if self.date_range is not None:
            if (
                not isinstance(self.date_range, tuple)
                or len(self.date_range) != 2
                or not all(
                    isinstance(value, str) and value.strip()
                    for value in self.date_range
                )
            ):
                raise ValueError("date_range must be a pair of non-empty strings.")


@dataclass(frozen=True, slots=True)
class Signal:
    """One qualified interpretation candidate projected from Knowledge evidence."""

    signal_id: str
    signal_type: SignalType
    state: SignalState
    subject_key: str | None
    subject_label: str | None
    horizon: SignalHorizon
    windows: tuple[ObservationWindow, ...]
    maturity: EvidenceMaturity
    supporting_dimensions: tuple[SupportDimension, ...]
    reference_values: tuple[ReferenceValue, ...]
    claim_scopes: tuple[ClaimScope, ...]
    caveats: tuple[SignalCaveat, ...]
    evidence_refs: tuple[KnowledgeEvidenceRef, ...]
    role_eligibility: SignalRoleEligibility

    def __post_init__(self) -> None:
        if not isinstance(self.signal_id, str) or not self.signal_id.strip():
            raise ValueError("signal_id must be a non-empty string.")
        for value, expected, field_name in (
            (self.signal_type, SignalType, "signal_type"),
            (self.state, SignalState, "state"),
            (self.horizon, SignalHorizon, "horizon"),
            (self.maturity, EvidenceMaturity, "maturity"),
            (self.role_eligibility, SignalRoleEligibility, "role_eligibility"),
        ):
            if not isinstance(value, expected):
                raise TypeError(f"{field_name} must be {expected.__name__}.")
        _validate_optional_text(self.subject_key, "subject_key")
        _validate_optional_text(self.subject_label, "subject_label")
        for field_name in (
            "windows",
            "supporting_dimensions",
            "reference_values",
            "claim_scopes",
            "caveats",
            "evidence_refs",
        ):
            value = getattr(self, field_name)
            if not isinstance(value, tuple):
                raise TypeError(f"{field_name} must be a tuple.")
        expected_items = (
            (self.windows, ObservationWindow, "windows"),
            (self.supporting_dimensions, SupportDimension, "supporting_dimensions"),
            (self.reference_values, ReferenceValue, "reference_values"),
            (self.claim_scopes, ClaimScope, "claim_scopes"),
            (self.caveats, SignalCaveat, "caveats"),
            (self.evidence_refs, KnowledgeEvidenceRef, "evidence_refs"),
        )
        for values, expected_type, field_name in expected_items:
            if any(not isinstance(item, expected_type) for item in values):
                raise TypeError(
                    f"{field_name} must contain only {expected_type.__name__} values."
                )
        if not self.windows:
            raise ValueError("Signal must reference at least one observation window.")
        if not self.claim_scopes:
            raise ValueError("Signal must contain at least one approved claim scope.")
        if not self.evidence_refs:
            raise ValueError("Signal must reference contributing Knowledge evidence.")
        _require_unique(
            (item.name for item in self.supporting_dimensions),
            "support dimension names",
        )
        _require_unique(
            (item.name for item in self.reference_values),
            "reference value names",
        )
        _require_unique(
            (item.evidence_id for item in self.evidence_refs),
            "Knowledge evidence references",
        )
        _require_unique(self.windows, "observation windows")
        _require_unique(self.claim_scopes, "claim scopes")
        _require_unique(self.caveats, "caveats")
        expected_eligibility = role_eligibility_for_maturity(self.maturity)
        if self.role_eligibility is not expected_eligibility:
            raise ValueError(
                "role_eligibility must match deterministic evidence maturity."
            )


def role_eligibility_for_maturity(
    maturity: EvidenceMaturity,
) -> SignalRoleEligibility:
    """Map frozen Sprint 4A maturity semantics to Planner eligibility."""
    if not isinstance(maturity, EvidenceMaturity):
        raise TypeError("maturity must be EvidenceMaturity.")
    if maturity is EvidenceMaturity.PRELIMINARY:
        return SignalRoleEligibility.WATCH_ONLY
    return SignalRoleEligibility.PRIMARY_OR_SECONDARY


def _validate_named_scalar(name: str, value: SignalScalar, kind: str) -> None:
    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"{kind} name must be a non-empty string.")
    if not isinstance(value, (str, int, float, bool)):
        raise TypeError(f"{kind} value must be a JSON scalar.")
    if isinstance(value, str) and not value.strip():
        raise ValueError(f"{kind} string value must not be empty.")
    if isinstance(value, float) and not isfinite(value):
        raise ValueError(f"{kind} float value must be finite.")


def _validate_optional_text(value: str | None, field_name: str) -> None:
    if value is not None and (
        not isinstance(value, str) or not value.strip()
    ):
        raise ValueError(f"{field_name} must be None or a non-empty string.")


def _require_unique(values: object, label: str) -> None:
    resolved = tuple(values)
    if len(resolved) != len(set(resolved)):
        raise ValueError(f"Signal {label} must be unique.")
