"""Deterministic interpretation planning over qualified Signals."""

from importlib import import_module

from music_ai.planning.models import (
    InterpretationPlan,
    InterpretationRole,
    PlanItem,
    SignalRelationship,
)


__all__ = [
    "InterpretationPlan",
    "InterpretationPlanner",
    "InterpretationRole",
    "PlanItem",
    "SignalRelationship",
]


def __getattr__(name: str):
    if name != "InterpretationPlanner":
        raise AttributeError(name)
    value = getattr(
        import_module("music_ai.planning.planner"),
        "InterpretationPlanner",
    )
    globals()[name] = value
    return value
