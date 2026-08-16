import json

import pytest

from music_ai.ai import InterpretationBrief, InterpretationRequest
from music_ai.ai.interpretation_brief import MAX_INTERPRETATION_TEXT_CHARACTERS
from music_ai.localization import SupportedLocale
from music_ai.planning import (
    InterpretationPlan,
    InterpretationRole,
    PlanItem,
    SignalRelationship,
)
from music_ai.signal import (
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
)
from music_ai.visible_content import VisibleContentManifest


def _signal(
    signal_id: str,
    maturity: EvidenceMaturity,
    *,
    label: str | None = None,
) -> Signal:
    return Signal(
        signal_id=signal_id,
        signal_type=SignalType.EXPLORATION_INTENSITY,
        state=SignalState.BROADER_ARTIST_MIX,
        subject_key="listening:all_artists",
        subject_label=label,
        horizon=SignalHorizon.LONG_TERM,
        windows=(
            ObservationWindow(
                WindowLabel.CURRENT,
                __import__("datetime").date(2026, 7, 15),
                __import__("datetime").date(2026, 8, 14),
            ),
        ),
        maturity=maturity,
        supporting_dimensions=(SupportDimension("supporting_days", 8),),
        reference_values=(ReferenceValue("direction", "increase"),),
        claim_scopes=(ClaimScope.WINDOW_RELATIVE_EXPLORATION,),
        caveats=(SignalCaveat.OBSERVED_LOCAL_HISTORY_ONLY,),
        evidence_refs=(KnowledgeEvidenceRef(f"e-{signal_id}", "artist_breadth_evolution", None),),
        role_eligibility=(
            SignalRoleEligibility.WATCH_ONLY
            if maturity is EvidenceMaturity.PRELIMINARY
            else SignalRoleEligibility.PRIMARY_OR_SECONDARY
        ),
    )


def _request(
    *roles: InterpretationRole,
    locale: SupportedLocale = SupportedLocale.EN_US,
    label: str | None = None,
) -> InterpretationRequest:
    signals = tuple(
        _signal(
            f"s{index}",
            EvidenceMaturity.PRELIMINARY
            if role is InterpretationRole.WATCH
            else EvidenceMaturity.SUPPORTED,
            label=label,
        )
        for index, role in enumerate(roles, start=1)
    )
    plan = InterpretationPlan(
        tuple(
            PlanItem(
                plan_item_id=f"p{index}",
                role=role,
                signal_ids=(signal.signal_id,),
                relationship=SignalRelationship.UNRELATED,
                interpretation_key=f"key:{index}",
            )
            for index, (role, signal) in enumerate(zip(roles, signals), start=1)
        )
    )
    return InterpretationRequest.from_plan(
        plan,
        signals,
        VisibleContentManifest(),
        locale,
    )


@pytest.mark.parametrize(
    "roles",
    [
        (InterpretationRole.PRIMARY,),
        (InterpretationRole.PRIMARY, InterpretationRole.SECONDARY),
        (InterpretationRole.PRIMARY, InterpretationRole.WATCH),
        (
            InterpretationRole.PRIMARY,
            InterpretationRole.SECONDARY,
            InterpretationRole.WATCH,
        ),
        (InterpretationRole.WATCH,),
    ],
)
def test_dynamic_brief_accepts_every_valid_nonempty_plan_shape(roles) -> None:
    request = _request(*roles)
    payload = {
        "items": [
            {
                "plan_item_id": item.plan_item_id,
                "role": item.role,
                "text": f"Interpretation {index}.",
            }
            for index, item in enumerate(request.plan_items, start=1)
        ]
    }

    brief = InterpretationBrief.from_payload(payload, request)

    assert tuple(item.plan_item_id for item in brief.items) == tuple(
        item.plan_item_id for item in request.plan_items
    )


def test_dynamic_brief_reorders_provider_items_to_plan_order() -> None:
    request = _request(InterpretationRole.PRIMARY, InterpretationRole.WATCH)
    payload = {
        "items": [
            {"plan_item_id": "p2", "role": "watch", "text": "Watch."},
            {"plan_item_id": "p1", "role": "primary", "text": "Primary."},
        ]
    }

    brief = InterpretationBrief.from_payload(payload, request)

    assert tuple(item.plan_item_id for item in brief.items) == ("p1", "p2")


@pytest.mark.parametrize(
    ("locale", "label", "text"),
    [
        (
            SupportedLocale.EN_US,
            "Artist ★",
            "Artist ★ appears stable across the selected window.",
        ),
        (
            SupportedLocale.EN_US,
            "Artist *Name*",
            "Artist *Name* appears stable across the selected window.",
        ),
        (
            SupportedLocale.EN_US,
            "[Artist]",
            "[Artist] appears stable across the selected window.",
        ),
        (
            SupportedLocale.ZH_CN,
            "艺人 ★",
            "艺人 ★ 在所选时间段内的变化较为稳定。",
        ),
        (
            SupportedLocale.ZH_CN,
            "艺人 *名字*",
            "艺人 *名字* 在所选时间段内的变化较为稳定。",
        ),
    ],
)
def test_dynamic_brief_preserves_exact_selected_opaque_labels(
    locale: SupportedLocale,
    label: str,
    text: str,
) -> None:
    request = _request(InterpretationRole.PRIMARY, locale=locale, label=label)

    brief = InterpretationBrief.from_payload(
        {
            "items": [
                {"plan_item_id": "p1", "role": "primary", "text": text}
            ]
        },
        request,
    )

    assert brief.items[0].text == text


@pytest.mark.parametrize(
    "text",
    [
        "Artist *Name* looks **stable**.",
        "Artist *Name* looks stable 🎧",
        "Artist *Name* looks <b>stable</b>.",
        "[Artist](https://example.com) looks stable.",
    ],
)
def test_dynamic_brief_rejects_decoration_outside_an_approved_label(text: str) -> None:
    label = "[Artist]" if text.startswith("[Artist]") else "Artist *Name*"
    request = _request(InterpretationRole.PRIMARY, label=label)

    with pytest.raises(ValueError, match="plain-text"):
        InterpretationBrief.from_payload(
            {
                "items": [
                    {"plan_item_id": "p1", "role": "primary", "text": text}
                ]
            },
            request,
        )


def test_dynamic_brief_does_not_exempt_an_unapproved_opaque_label() -> None:
    request = _request(InterpretationRole.PRIMARY, label="Approved Artist")

    with pytest.raises(ValueError, match="plain-text"):
        InterpretationBrief.from_payload(
            {
                "items": [
                    {
                        "plan_item_id": "p1",
                        "role": "primary",
                        "text": "Artist ★ appears stable.",
                    }
                ]
            },
            request,
        )


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"items": [{"plan_item_id": "unknown", "role": "primary", "text": "x"}]}, "unknown"),
        ({"items": [{"plan_item_id": "p1", "role": "watch", "text": "x"}]}, "match"),
        ({"items": [{"plan_item_id": "p1", "role": "primary", "text": ""}]}, "non-empty"),
        ({"items": [{"plan_item_id": "p1", "role": "unexpected", "text": "x"}]}, "unexpected"),
        ({"items": [{"plan_item_id": "p1", "role": "primary", "text": "**bold**"}]}, "plain-text"),
        ({"items": [{"plan_item_id": "p1", "role": "primary", "text": "*italic*"}]}, "plain-text"),
        ({"items": [{"plan_item_id": "p1", "role": "primary", "text": "prefix*italic*"}]}, "plain-text"),
        ({"items": [{"plan_item_id": "p1", "role": "primary", "text": "_italic_"}]}, "plain-text"),
        ({"items": [{"plan_item_id": "p1", "role": "primary", "text": "~~strike~~"}]}, "plain-text"),
        ({"items": [{"plan_item_id": "p1", "role": "primary", "text": "[label][ref]"}]}, "plain-text"),
        ({"items": [{"plan_item_id": "p1", "role": "primary", "text": "<b>markup</b>"}]}, "plain-text"),
        ({"items": [{"plan_item_id": "p1", "role": "primary", "text": "---"}]}, "plain-text"),
        ({"items": [{"plan_item_id": "p1", "role": "primary", "text": "Looks stable 🎧"}]}, "plain-text"),
        ({"items": [{"plan_item_id": "p1", "role": "primary", "text": "line one\nline two"}]}, "plain-text"),
        ({"items": [{"plan_item_id": "p1", "role": "primary", "text": "x", "extra": True}]}, "exact"),
        ({"items": [], "extra": True}, "only"),
    ],
)
def test_dynamic_brief_rejects_invalid_provider_items(payload, message) -> None:
    with pytest.raises(ValueError, match=message):
        InterpretationBrief.from_payload(
            payload,
            _request(InterpretationRole.PRIMARY),
        )


def test_dynamic_brief_rejects_duplicate_id_and_duplicate_role() -> None:
    request = _request(InterpretationRole.PRIMARY, InterpretationRole.SECONDARY)
    duplicate_id = {
        "items": [
            {"plan_item_id": "p1", "role": "primary", "text": "one"},
            {"plan_item_id": "p1", "role": "primary", "text": "two"},
        ]
    }
    with pytest.raises(ValueError, match="duplicate plan"):
        InterpretationBrief.from_payload(duplicate_id, request)

    with pytest.raises(ValueError, match="duplicate role"):
        InterpretationBrief.from_payload(
            {
                "items": [
                    {"plan_item_id": "p1", "role": "primary", "text": "one"},
                    {"plan_item_id": "p2", "role": "primary", "text": "two"},
                ]
            },
            request,
        )


def test_dynamic_brief_rejects_missing_planned_item() -> None:
    request = _request(InterpretationRole.PRIMARY, InterpretationRole.WATCH)
    with pytest.raises(ValueError, match="every planned"):
        InterpretationBrief.from_payload(
            {"items": [{"plan_item_id": "p1", "role": "primary", "text": "one"}]},
            request,
        )


def test_dynamic_brief_enforces_named_text_limit() -> None:
    request = _request(InterpretationRole.PRIMARY)
    with pytest.raises(ValueError, match="500-character"):
        InterpretationBrief.from_payload(
            {
                "items": [
                    {
                        "plan_item_id": "p1",
                        "role": "primary",
                        "text": "x" * (MAX_INTERPRETATION_TEXT_CHARACTERS + 1),
                    }
                ]
            },
            request,
        )


def test_internal_empty_brief_is_valid_without_provider_payload() -> None:
    assert InterpretationBrief().items == ()
    assert json.loads('{"items":[]}') == {"items": []}
