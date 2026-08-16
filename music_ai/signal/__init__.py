"""Deterministic interpretation Signals projected from qualified Knowledge."""

from importlib import import_module

from music_ai.signal.models import (
    ClaimScope,
    EvidenceMaturity,
    KnowledgeEvidenceRef,
    ObservationWindow,
    ReferenceValue,
    Signal,
    SignalCaveat,
    SignalHorizon,
    SignalRoleEligibility,
    SignalState,
    SignalType,
    SupportDimension,
    WindowLabel,
    role_eligibility_for_maturity,
)


__all__ = [
    "ClaimScope",
    "EvidenceMaturity",
    "KnowledgeEvidenceRef",
    "ObservationWindow",
    "ReferenceValue",
    "Signal",
    "SignalCaveat",
    "SignalHorizon",
    "SignalProjector",
    "SignalRoleEligibility",
    "SignalState",
    "SignalType",
    "SupportDimension",
    "WindowLabel",
    "knowledge_evidence_id",
    "knowledge_evidence_ref",
    "role_eligibility_for_maturity",
]

_EXPORTS = {
    "SignalProjector": ("music_ai.signal.projection", "SignalProjector"),
    "knowledge_evidence_ref": ("music_ai.signal.projection", "knowledge_evidence_ref"),
    "knowledge_evidence_id": ("music_ai.knowledge.evidence_reference", "knowledge_evidence_id"),
}


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    value = getattr(import_module(target[0]), target[1])
    globals()[name] = value
    return value
