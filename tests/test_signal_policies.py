"""Executable boundary tests for named Sprint 4A Signal policies."""

import pytest

from music_ai.signal import EvidenceMaturity, SignalState
from music_ai.signal import policies


def test_daily_lifecycle_policy_requires_explicit_closed_marker() -> None:
    assert policies.DAILY_LIFECYCLE_REQUIRES_EXPLICIT_CLOSED_MARKER is True
    assert not policies.daily_lifecycle_evidence_is_eligible(
        is_closed_day=None,
        contains_open_day=None,
    )
    assert not policies.daily_lifecycle_evidence_is_eligible(
        is_closed_day=True,
        contains_open_day=None,
    )
    assert not policies.daily_lifecycle_evidence_is_eligible(
        is_closed_day=True,
        contains_open_day=True,
    )
    assert policies.daily_lifecycle_evidence_is_eligible(
        is_closed_day=True,
        contains_open_day=False,
    )


def test_daily_lifecycle_policy_constant_is_part_of_executable_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        policies,
        "DAILY_LIFECYCLE_REQUIRES_EXPLICIT_CLOSED_MARKER",
        False,
    )

    assert policies.daily_lifecycle_evidence_is_eligible(
        is_closed_day=None,
        contains_open_day=None,
    )
    assert not policies.daily_lifecycle_evidence_is_eligible(
        is_closed_day=None,
        contains_open_day=True,
    )


@pytest.mark.parametrize(
    ("state", "categories", "expected"),
    (
        (
            SignalState.LOCALLY_EMERGING,
            {"artist_emergence"},
            EvidenceMaturity.PRELIMINARY,
        ),
        (
            SignalState.REPEATED_PRESENCE,
            {"stable_favorite"},
            EvidenceMaturity.PRELIMINARY,
        ),
        (
            SignalState.REPEATED_PRESENCE,
            {"artist_continuity"},
            EvidenceMaturity.SUPPORTED,
        ),
        (
            SignalState.SUSTAINED_GROWTH,
            {"artist_duration_share_evolution"},
            EvidenceMaturity.SUPPORTED,
        ),
        (
            SignalState.SUSTAINED_GROWTH,
            {"artist_duration_share_evolution", "artist_emergence"},
            EvidenceMaturity.STRONG,
        ),
        (
            SignalState.ESTABLISHED_CORE_PRESENCE,
            {"artist_consistency"},
            EvidenceMaturity.SUPPORTED,
        ),
        (
            SignalState.ESTABLISHED_CORE_PRESENCE,
            {"artist_consistency", "artist_duration_share_evolution"},
            EvidenceMaturity.STRONG,
        ),
    ),
)
def test_preference_family_maturity_policy(
    state: SignalState,
    categories: set[str],
    expected: EvidenceMaturity,
) -> None:
    assert policies.preference_maturity(state, categories) is expected


@pytest.mark.parametrize(
    ("state", "recent", "long_horizon", "expected"),
    (
        (
            SignalState.SHORT_WINDOW_MOVEMENT,
            True,
            False,
            EvidenceMaturity.PRELIMINARY,
        ),
        (
            SignalState.SUSTAINED_GROWTH,
            False,
            True,
            EvidenceMaturity.SUPPORTED,
        ),
        (
            SignalState.SUSTAINED_GROWTH,
            True,
            True,
            EvidenceMaturity.STRONG,
        ),
        (
            SignalState.CONFLICTING_HORIZONS,
            True,
            True,
            EvidenceMaturity.SUPPORTED,
        ),
    ),
)
def test_movement_family_maturity_policy(
    state: SignalState,
    recent: bool,
    long_horizon: bool,
    expected: EvidenceMaturity,
) -> None:
    assert (
        policies.movement_maturity(
            state,
            has_recent_movement=recent,
            has_long_horizon_movement=long_horizon,
        )
        is expected
    )


def test_exploration_and_core_composite_maturity_policies() -> None:
    assert (
        policies.exploration_maturity(has_compatible_state_evidence=False)
        is EvidenceMaturity.SUPPORTED
    )
    assert (
        policies.exploration_maturity(has_compatible_state_evidence=True)
        is EvidenceMaturity.STRONG
    )
    assert (
        policies.CORE_EXPLORATION_DIRECTION_RULES
        == {("increase", "increase"): "wider_mix_with_concentrated_core"}
    )
    assert (
        policies.CORE_EXPLORATION_COMPOSITE_MATURITY
        is EvidenceMaturity.STRONG
    )


@pytest.mark.parametrize(
    "policy",
    (
        policies.time_pattern_maturity,
        policies.artist_time_affinity_maturity,
        policies.time_evolution_maturity,
    ),
)
@pytest.mark.parametrize(
    ("day_count", "expected"),
    (
        (4, EvidenceMaturity.PRELIMINARY),
        (5, EvidenceMaturity.SUPPORTED),
        (7, EvidenceMaturity.SUPPORTED),
        (8, EvidenceMaturity.STRONG),
    ),
)
def test_contextual_family_maturity_boundaries(
    policy,
    day_count: int,
    expected: EvidenceMaturity,
) -> None:
    assert policy(day_count) is expected


@pytest.mark.parametrize(
    "policy",
    (
        policies.time_pattern_maturity,
        policies.artist_time_affinity_maturity,
        policies.time_evolution_maturity,
    ),
)
@pytest.mark.parametrize("invalid", (-1, True, 1.5))
def test_contextual_maturity_rejects_invalid_day_support(policy, invalid) -> None:
    with pytest.raises(ValueError, match="non-negative integer"):
        policy(invalid)
