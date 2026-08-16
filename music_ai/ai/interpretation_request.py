"""Deliberate provider projection of an approved interpretation plan."""

from dataclasses import dataclass
from datetime import date
from enum import Enum
import json
from math import isfinite

from music_ai.localization.models import SupportedLocale, require_supported_locale
from music_ai.planning.models import (
    InterpretationPlan,
    InterpretationRole,
    SignalRelationship,
)
from music_ai.signal.models import Signal, SignalType
from music_ai.visible_content.models import (
    VisibleContentManifest,
    VisibleContentReference,
)


GLOBAL_PROHIBITED_CLAIMS = (
    "Do not discover or add factual patterns outside the selected Signals.",
    "Do not change evidence maturity, qualification, roles, or relationships.",
    "Do not infer causes, mood, psychology, personality, stress, motivation, activity, or life circumstances.",
    "Do not guess genre from names.",
    "Do not claim first-ever discovery without explicit proof.",
    "Do not claim a permanent preference or complete listening history.",
    "Do not predict future behavior.",
    "Do not recommend music or actions.",
)

# Provider support is deliberately narrower than the Signal's audit contract.
# Complete numerators/denominators and qualification arithmetic stay deterministic.
_PROVIDER_SUPPORT_SUFFIXES = {
    SignalType.ARTIST_PREFERENCE_FORMATION: (
        "closed_supporting_day_count",
        "recent_closed_artist_day_count",
        "qualifying_day_count",
        "appearance_day_count",
        "listening_day_count",
    ),
    SignalType.TEMPORARY_SPIKE_VS_SUSTAINED_GROWTH: (
        "recent_closed_artist_day_count",
        "qualifying_day_count",
        "closed_supporting_day_count",
        "appearance_day_count",
    ),
    SignalType.EXPLORATION_INTENSITY: (
        "previous_listening_day_count",
        "current_listening_day_count",
        "closed_listening_day_count",
        "supporting_days",
    ),
    SignalType.CORE_VS_EXPLORATION_BALANCE: (
        "previous_listening_day_count",
        "current_listening_day_count",
    ),
    SignalType.LISTENING_TIME_OF_DAY_PATTERN: (
        "segment_listening_day_count",
    ),
    SignalType.ARTIST_TIME_OF_DAY_AFFINITY: (
        "artist_segment_listening_day_count",
    ),
    SignalType.TIME_PATTERN_EVOLUTION: (
        "previous_segment_listening_day_count",
        "current_segment_listening_day_count",
    ),
}
_PROVIDER_REFERENCE_SUFFIXES = {
    SignalType.ARTIST_PREFERENCE_FORMATION: (
        "previous_value",
        "current_value",
        "recent_duration_share",
        "comparison_duration_share",
        "appearance_share",
        "duration_share",
    ),
    SignalType.TEMPORARY_SPIKE_VS_SUSTAINED_GROWTH: (
        "previous_value",
        "current_value",
        "recent_duration_share",
        "comparison_duration_share",
    ),
    SignalType.EXPLORATION_INTENSITY: (
        "previous_value",
        "current_value",
        "signed_change",
    ),
    SignalType.CORE_VS_EXPLORATION_BALANCE: (
        "previous_value",
        "current_value",
    ),
    SignalType.LISTENING_TIME_OF_DAY_PATTERN: (
        "segment",
        "segment_event_share",
    ),
    SignalType.ARTIST_TIME_OF_DAY_AFFINITY: (
        "segment",
        "artist_segment_share",
        "overall_segment_share",
        "share_point_lift",
    ),
    SignalType.TIME_PATTERN_EVOLUTION: (
        "segment",
        "previous_segment_event_share",
        "current_segment_event_share",
        "signed_share_change",
    ),
}
_MAX_PROVIDER_SUPPORT_DIMENSIONS = 4
_MAX_PROVIDER_REFERENCE_VALUES = 4


@dataclass(frozen=True, slots=True)
class ProviderPlanItem:
    """The provider-visible portion of one planner-approved item."""

    plan_item_id: str
    role: str
    signal_ids: tuple[str, ...]
    relationship: str
    interpretation_key: str

    def __post_init__(self) -> None:
        _required_text(self.plan_item_id, "plan_item_id")
        if self.role not in {value.value for value in InterpretationRole}:
            raise ValueError("Provider plan item role is invalid.")
        if self.relationship not in {value.value for value in SignalRelationship}:
            raise ValueError("Provider plan item relationship is invalid.")
        if not isinstance(self.signal_ids, tuple) or not self.signal_ids:
            raise ValueError("Provider plan item requires Signal IDs.")
        if len(self.signal_ids) != len(set(self.signal_ids)):
            raise ValueError("Provider plan item Signal IDs must be unique.")
        for signal_id in self.signal_ids:
            _required_text(signal_id, "signal_id")
        expected_count = (
            1 if self.relationship == SignalRelationship.UNRELATED.value else 2
        )
        if len(self.signal_ids) != expected_count:
            raise ValueError("Provider relationship shape does not match Signal IDs.")
        _required_text(self.interpretation_key, "interpretation_key")


@dataclass(frozen=True, slots=True)
class ProviderSupportValue:
    """One explicitly selected supporting dimension or reference value."""

    name: str
    value: str | int | float


@dataclass(frozen=True, slots=True)
class ProviderWindow:
    """Compact provider-safe observation window."""

    label: str
    start_date: str
    end_date: str


@dataclass(frozen=True, slots=True)
class ProviderSignal:
    """Narrow provider projection, intentionally not an internal Signal dump."""

    signal_id: str
    signal_type: str
    state: str
    subject_key: str | None
    subject_label: str | None
    horizon: str
    maturity: str
    windows: tuple[ProviderWindow, ...]
    supporting_dimensions: tuple[ProviderSupportValue, ...]
    reference_values: tuple[ProviderSupportValue, ...]
    claim_scopes: tuple[str, ...]
    caveats: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ProviderVisibleReference:
    """Non-evidentiary context used only to avoid duplicating visible content."""

    concept: str
    subject_key: str | None
    direction: str | None
    category: str | None
    horizon: str | None


@dataclass(frozen=True, slots=True)
class InterpretationRequest:
    """Selected Signal evidence plus non-evidentiary duplicate-awareness context."""

    target_locale: str
    plan_items: tuple[ProviderPlanItem, ...]
    signals: tuple[ProviderSignal, ...]
    visible_content: tuple[ProviderVisibleReference, ...]
    prohibited_claims: tuple[str, ...] = GLOBAL_PROHIBITED_CLAIMS

    def __post_init__(self) -> None:
        try:
            SupportedLocale(self.target_locale)
        except (TypeError, ValueError) as error:
            raise ValueError("target_locale must be a supported locale value.") from error
        for field_name in (
            "plan_items",
            "signals",
            "visible_content",
            "prohibited_claims",
        ):
            if not isinstance(getattr(self, field_name), tuple):
                raise TypeError(f"{field_name} must be a tuple.")
        if not 1 <= len(self.plan_items) <= 3:
            raise ValueError("A provider request requires one to three plan items.")
        if any(not isinstance(item, ProviderPlanItem) for item in self.plan_items):
            raise TypeError("plan_items must contain ProviderPlanItem values.")
        if any(not isinstance(item, ProviderSignal) for item in self.signals):
            raise TypeError("signals must contain ProviderSignal values.")
        if any(
            not isinstance(item, ProviderVisibleReference)
            for item in self.visible_content
        ):
            raise TypeError(
                "visible_content must contain ProviderVisibleReference values."
            )
        item_ids = tuple(item.plan_item_id for item in self.plan_items)
        roles = tuple(item.role for item in self.plan_items)
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Provider plan item IDs must be unique.")
        if len(roles) != len(set(roles)):
            raise ValueError("Provider plan roles must be unique.")
        if "secondary" in roles and "primary" not in roles:
            raise ValueError("Secondary cannot exist without Primary.")
        role_order = {"primary": 0, "secondary": 1, "watch": 2}
        if roles != tuple(sorted(roles, key=role_order.__getitem__)):
            raise ValueError("Provider plan items must follow role order.")
        selected_ids = tuple(
            signal_id for item in self.plan_items for signal_id in item.signal_ids
        )
        if len(selected_ids) != len(set(selected_ids)):
            raise ValueError("A selected Signal cannot appear in multiple plan items.")
        projected_ids = tuple(signal.signal_id for signal in self.signals)
        if len(projected_ids) != len(set(projected_ids)):
            raise ValueError("Projected Signal IDs must be unique.")
        if frozenset(projected_ids) != frozenset(selected_ids):
            raise ValueError("Request Signals must exactly match planner selection.")
        if not self.prohibited_claims or any(
            not isinstance(value, str) or not value.strip()
            for value in self.prohibited_claims
        ):
            raise ValueError("prohibited_claims must contain non-empty policy text.")

    @classmethod
    def from_plan(
        cls,
        plan: InterpretationPlan,
        signals: tuple[Signal, ...],
        manifest: VisibleContentManifest,
        locale: SupportedLocale,
    ) -> "InterpretationRequest":
        """Project selected evidence and narrow duplicate-awareness references."""
        locale = require_supported_locale(locale)
        if not plan.items:
            raise ValueError("A provider request requires a non-empty plan.")

        signal_by_id: dict[str, Signal] = {}
        for signal in signals:
            if signal.signal_id in signal_by_id:
                raise ValueError("Signal IDs must be unique in a provider projection.")
            signal_by_id[signal.signal_id] = signal

        selected_ids = tuple(
            dict.fromkeys(
                signal_id
                for item in plan.items
                for signal_id in item.signal_ids
            )
        )
        missing = tuple(value for value in selected_ids if value not in signal_by_id)
        if missing:
            raise ValueError("Plan references a Signal absent from the projection input.")
        selected = tuple(signal_by_id[value] for value in selected_ids)

        return cls(
            target_locale=locale.value,
            plan_items=tuple(
                ProviderPlanItem(
                    plan_item_id=item.plan_item_id,
                    role=_enum_value(item.role),
                    signal_ids=tuple(item.signal_ids),
                    relationship=_enum_value(item.relationship),
                    interpretation_key=item.interpretation_key,
                )
                for item in plan.items
            ),
            signals=tuple(_project_signal(signal) for signal in selected),
            visible_content=tuple(
                _project_visible_reference(reference)
                for reference in _relevant_visible_references(manifest, selected)
            ),
        )

    @property
    def approved_opaque_labels(self) -> tuple[str, ...]:
        """Exact source labels approved by the selected Signal projection."""
        return tuple(
            dict.fromkeys(
                signal.subject_label
                for signal in self.signals
                if isinstance(signal.subject_label, str) and signal.subject_label
            )
        )

    def to_payload(self) -> dict[str, object]:
        """Return the exact public wire contract without dataclass auto-dumping."""
        return {
            "target_locale": self.target_locale,
            "plan_items": [
                {
                    "plan_item_id": item.plan_item_id,
                    "role": item.role,
                    "signal_ids": list(item.signal_ids),
                    "relationship": item.relationship,
                    "interpretation_key": item.interpretation_key,
                }
                for item in self.plan_items
            ],
            "signals": [
                {
                    "signal_id": signal.signal_id,
                    "signal_type": signal.signal_type,
                    "state": signal.state,
                    "subject_key": signal.subject_key,
                    "subject_label": signal.subject_label,
                    "horizon": signal.horizon,
                    "maturity": signal.maturity,
                    "windows": [
                        {
                            "label": window.label,
                            "start_date": window.start_date,
                            "end_date": window.end_date,
                        }
                        for window in signal.windows
                    ],
                    "supporting_dimensions": [
                        {"name": value.name, "value": value.value}
                        for value in signal.supporting_dimensions
                    ],
                    "reference_values": [
                        {"name": value.name, "value": value.value}
                        for value in signal.reference_values
                    ],
                    "claim_scopes": list(signal.claim_scopes),
                    "caveats": list(signal.caveats),
                }
                for signal in self.signals
            ],
            "visible_content": [
                {
                    "concept": reference.concept,
                    "subject_key": reference.subject_key,
                    "direction": reference.direction,
                    "category": reference.category,
                    "horizon": reference.horizon,
                }
                for reference in self.visible_content
            ],
            "prohibited_claims": list(self.prohibited_claims),
        }

    def to_json(self) -> str:
        """Serialize deterministically for any provider transport."""
        return json.dumps(
            self.to_payload(),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )


def _project_signal(signal: Signal) -> ProviderSignal:
    return ProviderSignal(
        signal_id=signal.signal_id,
        signal_type=_enum_value(signal.signal_type),
        state=_enum_value(signal.state),
        subject_key=signal.subject_key,
        subject_label=signal.subject_label,
        horizon=_enum_value(signal.horizon),
        maturity=_enum_value(signal.maturity),
        windows=tuple(
            ProviderWindow(
                label=window.label,
                start_date=_date_value(window.start_date),
                end_date=_date_value(window.end_date),
            )
            for window in signal.windows
        ),
        supporting_dimensions=tuple(
            ProviderSupportValue(value.name, _provider_scalar(value.value))
            for value in _selected_values(
                signal.supporting_dimensions,
                _PROVIDER_SUPPORT_SUFFIXES[signal.signal_type],
                _MAX_PROVIDER_SUPPORT_DIMENSIONS,
            )
        ),
        reference_values=tuple(
            ProviderSupportValue(value.name, _provider_scalar(value.value))
            for value in _selected_values(
                signal.reference_values,
                _PROVIDER_REFERENCE_SUFFIXES[signal.signal_type],
                _MAX_PROVIDER_REFERENCE_VALUES,
            )
        ),
        claim_scopes=tuple(_enum_value(value) for value in signal.claim_scopes),
        caveats=tuple(_enum_value(value) for value in signal.caveats),
    )


def _relevant_visible_references(
    manifest: VisibleContentManifest,
    signals: tuple[Signal, ...],
) -> tuple[VisibleContentReference, ...]:
    """Select duplicate-awareness context without making it evidence."""
    subjects = {signal.subject_key for signal in signals if signal.subject_key}
    concepts = {
        value
        for signal in signals
        for value in (_enum_value(signal.signal_type), _enum_value(signal.state))
    }
    categories = {
        _enum_value(reference.category)
        for signal in signals
        for reference in signal.evidence_refs
    }
    evidence_ids = {
        reference.evidence_id
        for signal in signals
        for reference in signal.evidence_refs
    }
    return tuple(
        reference
        for reference in manifest.references
        if (
            reference.evidence_id in evidence_ids
            or (
                reference.subject_key is not None
                and reference.subject_key in subjects
            )
            or (
                reference.subject_key is None
                and (
                    reference.concept in concepts
                    or (
                        reference.category is not None
                        and _enum_value(reference.category) in categories
                    )
                )
            )
        )
    )


def _project_visible_reference(
    reference: VisibleContentReference,
) -> ProviderVisibleReference:
    return ProviderVisibleReference(
        concept=reference.concept,
        subject_key=reference.subject_key,
        direction=reference.direction,
        category=_optional_enum_value(reference.category),
        horizon=_optional_enum_value(reference.horizon),
    )


def _provider_scalar(value: object) -> str | int | float:
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float) and isfinite(value):
        return value
    if isinstance(value, Enum):
        return str(value.value)
    return str(value)


def _selected_values(
    values: tuple[object, ...],
    suffix_priority: tuple[str, ...],
    limit: int,
) -> tuple[object, ...]:
    """Select a small policy-owned subset without exposing qualification totals."""
    selected: list[object] = []
    seen_names: set[str] = set()
    for suffix in suffix_priority:
        for value in values:
            name = value.name
            if name in seen_names:
                continue
            if name == suffix or name.endswith(f".{suffix}"):
                selected.append(value)
                seen_names.add(name)
                if len(selected) == limit:
                    return tuple(selected)
    return tuple(selected)


def _date_value(value: object) -> str:
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str) and value:
        return value
    raise TypeError("Provider window dates must be dates or non-empty ISO strings.")


def _enum_value(value: object) -> str:
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, str) and value:
        return value
    raise TypeError("Provider enum values must be enums or non-empty strings.")


def _optional_enum_value(value: object) -> str | None:
    if value is None:
        return None
    return _enum_value(value)


def _required_text(value: object, field_name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be non-empty text.")
