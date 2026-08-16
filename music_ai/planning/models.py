"""Immutable contracts produced by deterministic interpretation planning."""

from dataclasses import dataclass
from enum import StrEnum


class InterpretationRole(StrEnum):
    """The three bounded roles in MusicMind's dynamic AI brief."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    WATCH = "watch"


class SignalRelationship(StrEnum):
    """Finite narrative relationships between already-qualified Signals."""

    REINFORCEMENT = "reinforcement"
    CONTRAST = "contrast"
    CONTEXTUAL_SUPPORT = "contextual_support"
    UNRELATED = "unrelated"


@dataclass(frozen=True, slots=True)
class PlanItem:
    """One planner-approved meaning that the provider must realize."""

    plan_item_id: str
    role: InterpretationRole
    signal_ids: tuple[str, ...]
    relationship: SignalRelationship
    interpretation_key: str

    def __post_init__(self) -> None:
        _require_text("plan_item_id", self.plan_item_id)
        if not isinstance(self.role, InterpretationRole):
            raise TypeError("role must be an InterpretationRole.")
        if not isinstance(self.relationship, SignalRelationship):
            raise TypeError("relationship must be a SignalRelationship.")
        signal_ids = tuple(self.signal_ids)
        if not signal_ids:
            raise ValueError("PlanItem must reference at least one Signal.")
        if len(signal_ids) != len(set(signal_ids)):
            raise ValueError("PlanItem Signal identifiers must be unique.")
        for signal_id in signal_ids:
            _require_text("signal_id", signal_id)
        if self.relationship is SignalRelationship.UNRELATED:
            if len(signal_ids) != 1:
                raise ValueError(
                    "An unrelated PlanItem must reference exactly one Signal."
                )
        elif len(signal_ids) != 2:
            raise ValueError(
                "A related PlanItem must reference exactly two Signals."
            )
        _require_text("interpretation_key", self.interpretation_key)
        object.__setattr__(self, "signal_ids", signal_ids)


@dataclass(frozen=True, slots=True)
class InterpretationPlan:
    """A validated zero-to-three-item dynamic brief plan."""

    items: tuple[PlanItem, ...] = ()

    def __post_init__(self) -> None:
        items = tuple(self.items)
        if any(not isinstance(item, PlanItem) for item in items):
            raise TypeError("InterpretationPlan items must be PlanItem values.")
        if len(items) > 3:
            raise ValueError("InterpretationPlan cannot contain more than three items.")
        item_ids = [item.plan_item_id for item in items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("InterpretationPlan item identifiers must be unique.")
        roles = [item.role for item in items]
        if len(roles) != len(set(roles)):
            raise ValueError("InterpretationPlan cannot repeat a role.")
        selected_signal_ids = [
            signal_id for item in items for signal_id in item.signal_ids
        ]
        if len(selected_signal_ids) != len(set(selected_signal_ids)):
            raise ValueError(
                "A Signal cannot be selected by more than one PlanItem."
            )
        if (
            InterpretationRole.SECONDARY in roles
            and InterpretationRole.PRIMARY not in roles
        ):
            raise ValueError("Secondary cannot exist without Primary.")
        role_order = {
            InterpretationRole.PRIMARY: 0,
            InterpretationRole.SECONDARY: 1,
            InterpretationRole.WATCH: 2,
        }
        if roles != sorted(roles, key=role_order.__getitem__):
            raise ValueError(
                "InterpretationPlan items must be ordered Primary, Secondary, Watch."
            )
        object.__setattr__(self, "items", items)

    @property
    def selected_signal_ids(self) -> tuple[str, ...]:
        """Return only planner-selected Signal references in plan order."""
        return tuple(signal_id for item in self.items for signal_id in item.signal_ids)

    def item_for_id(self, plan_item_id: str) -> PlanItem | None:
        """Resolve one response reference without exposing planning internals."""
        return next(
            (item for item in self.items if item.plan_item_id == plan_item_id),
            None,
        )


def _require_text(field_name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
