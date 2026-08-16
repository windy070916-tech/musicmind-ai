from dataclasses import dataclass, replace
from datetime import date
import json

import pytest

from music_ai.ai import InterpretationRequest, ReportGenerator
from music_ai.ai.base import LLMProvider
from music_ai.ai.prompts import SYSTEM_PROMPT, build_system_prompt, build_user_prompt
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
from music_ai.visible_content import (
    VisibleContentManifest,
    VisibleContentReference,
    VisibleSection,
)


@dataclass
class FakeProvider(LLMProvider):
    response: str = json.dumps(
        {"items": [{"plan_item_id": "plan-1", "role": "primary", "text": "The broader mix appears sustained across the closed window."}]}
    )
    system_prompt: str | None = None
    user_prompt: str | None = None
    calls: int = 0

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        self.system_prompt = system_prompt
        self.user_prompt = user_prompt
        return self.response


def _signal(signal_id: str, *, label: str | None = None) -> Signal:
    return Signal(
        signal_id=signal_id,
        signal_type=SignalType.EXPLORATION_INTENSITY,
        state=SignalState.BROADER_ARTIST_MIX,
        subject_key="listening:all_artists",
        subject_label=label,
        horizon=SignalHorizon.LONG_TERM,
        windows=(ObservationWindow(WindowLabel.CURRENT, date(2026, 7, 15), date(2026, 8, 14)),),
        maturity=EvidenceMaturity.SUPPORTED,
        supporting_dimensions=(SupportDimension("supporting_days", 9),),
        reference_values=(ReferenceValue("previous_artist_count", 20), ReferenceValue("current_artist_count", 28)),
        claim_scopes=(ClaimScope.WINDOW_RELATIVE_EXPLORATION,),
        caveats=(SignalCaveat.OBSERVED_LOCAL_HISTORY_ONLY, SignalCaveat.NOT_FIRST_EVER_DISCOVERY),
        evidence_refs=(KnowledgeEvidenceRef(f"evidence-{signal_id}", "artist_breadth_evolution", ("2026-06-15", "2026-08-14")),),
        role_eligibility=SignalRoleEligibility.PRIMARY_OR_SECONDARY,
    )


def _request(locale: SupportedLocale = SupportedLocale.EN_US) -> InterpretationRequest:
    selected = _signal("selected", label="Artist A")
    rejected = _signal("rejected", label="Artist B")
    plan = InterpretationPlan((PlanItem("plan-1", InterpretationRole.PRIMARY, (selected.signal_id,), SignalRelationship.UNRELATED, "signal:exploration"),))
    manifest = VisibleContentManifest((VisibleContentReference("visible-1", VisibleSection.LONG_TERM, "artist_breadth", subject_key="listening:all_artists", category="artist_breadth_evolution", horizon="long_term", evidence_id="evidence-selected"),))
    return InterpretationRequest.from_plan(plan, (rejected, selected), manifest, locale)


def test_request_serialization_contains_only_selected_provider_projection() -> None:
    request = _request()
    payload = request.to_payload()
    serialized = request.to_json()

    assert payload["target_locale"] == "en-US"
    assert [value["signal_id"] for value in payload["signals"]] == ["selected"]
    assert payload["signals"][0]["maturity"] == "supported"
    assert payload["signals"][0]["claim_scopes"] == ["window_relative_exploration"]
    assert payload["signals"][0]["caveats"] == ["observed_local_history_only", "not_first_ever_discovery"]
    assert payload["visible_content"][0]["concept"] == "artist_breadth"
    assert request.approved_opaque_labels == ("Artist A",)
    assert "Artist B" not in serialized
    assert "# Daily Listening Report" not in serialized
    for forbidden in ("play_history", "repository", "memory", "KnowledgeFact", "Temporal"):
        assert forbidden not in serialized
    assert request.to_json() == request.to_json()


def test_provider_manifest_projection_never_leaks_a_category_matched_other_subject() -> None:
    selected = _signal("selected")
    plan = InterpretationPlan(
        (
            PlanItem(
                "plan-1",
                InterpretationRole.PRIMARY,
                (selected.signal_id,),
                SignalRelationship.UNRELATED,
                "signal:exploration",
            ),
        )
    )
    manifest = VisibleContentManifest(
        (
            VisibleContentReference(
                "visible-selected",
                VisibleSection.LONG_TERM,
                "artist_breadth",
                subject_key="listening:all_artists",
                category="artist_breadth_evolution",
                evidence_id="evidence-selected",
            ),
            VisibleContentReference(
                "visible-other-artist",
                VisibleSection.LONG_TERM,
                "artist_breadth",
                subject_key="spotify:other-artist",
                category="artist_breadth_evolution",
                evidence_id="evidence-other",
            ),
        )
    )

    request = InterpretationRequest.from_plan(
        plan,
        (selected,),
        manifest,
        SupportedLocale.EN_US,
    )

    assert [item.subject_key for item in request.visible_content] == [
        "listening:all_artists"
    ]
    assert "other-artist" not in request.to_json()


def test_provider_projection_keeps_qualification_numerators_and_denominators_internal() -> None:
    affinity = replace(
        _signal("affinity", label="Artist A"),
        signal_type=SignalType.ARTIST_TIME_OF_DAY_AFFINITY,
        state=SignalState.ARTIST_OVERREPRESENTED_IN_SEGMENT,
        subject_key="spotify:artist-a",
        supporting_dimensions=(
            SupportDimension("artist_event_count", 20),
            SupportDimension("overall_event_count", 100),
            SupportDimension("artist_segment_event_count", 12),
            SupportDimension("artist_segment_listening_day_count", 6),
            SupportDimension("overall_segment_event_count", 30),
        ),
        reference_values=(
            ReferenceValue("segment", "18:00-24:00"),
            ReferenceValue("artist_segment_share", 0.6),
            ReferenceValue("overall_segment_share", 0.3),
            ReferenceValue("share_point_lift", 0.3),
            ReferenceValue("relative_lift", 2.0),
        ),
        claim_scopes=(ClaimScope.OBSERVED_ARTIST_TIME_ASSOCIATION,),
    )
    plan = InterpretationPlan(
        (
            PlanItem(
                "plan-1",
                InterpretationRole.PRIMARY,
                (affinity.signal_id,),
                SignalRelationship.UNRELATED,
                "signal:affinity",
            ),
        )
    )

    request = InterpretationRequest.from_plan(
        plan,
        (affinity,),
        VisibleContentManifest(),
        SupportedLocale.EN_US,
    )
    projected = request.to_payload()["signals"][0]

    assert projected["supporting_dimensions"] == [
        {"name": "artist_segment_listening_day_count", "value": 6}
    ]
    assert [item["name"] for item in projected["reference_values"]] == [
        "segment",
        "artist_segment_share",
        "overall_segment_share",
        "share_point_lift",
    ]
    assert "artist_event_count" not in request.to_json()
    assert "overall_event_count" not in request.to_json()
    assert "relative_lift" not in request.to_json()


def test_report_generator_sends_only_typed_json_request_and_renders_paragraphs() -> None:
    provider = FakeProvider()
    request = _request()

    report = ReportGenerator(provider).generate_report(request)

    assert report == "The broader mix appears sustained across the closed window."
    assert provider.calls == 1
    assert provider.system_prompt == build_system_prompt(SupportedLocale.EN_US)
    assert provider.system_prompt.startswith(SYSTEM_PROMPT)
    assert "recommend" in provider.system_prompt.lower()
    assert provider.user_prompt is not None
    request_payload = provider.user_prompt.split("\n\n", 1)[1]
    assert json.loads(request_payload) == request.to_payload()
    assert "[artist_breadth_evolution]" not in provider.user_prompt


def test_prompt_freezes_visible_content_as_non_evidentiary_duplicate_context() -> None:
    selected = _signal("selected", label="Artist A")
    plan = InterpretationPlan(
        (
            PlanItem(
                "plan-1",
                InterpretationRole.PRIMARY,
                (selected.signal_id,),
                SignalRelationship.UNRELATED,
                "signal:exploration",
            ),
        )
    )
    manifest = VisibleContentManifest(
        (
            VisibleContentReference(
                "unrelated-visible-fact",
                VisibleSection.HIGHLIGHTS,
                "unrelated_fact_b",
                subject_key=None,
                category="artist_breadth_evolution",
                evidence_id="different-evidence",
            ),
        )
    )
    request = InterpretationRequest.from_plan(
        plan,
        (selected,),
        manifest,
        SupportedLocale.EN_US,
    )
    system_prompt = build_system_prompt(SupportedLocale.EN_US)
    user_prompt = build_user_prompt(request.to_json())
    normalized_system_prompt = " ".join(system_prompt.split()).lower()

    assert request.visible_content[0].concept == "unrelated_fact_b"
    assert (
        "only the objects in `signals` are factual interpretation evidence"
        in normalized_system_prompt
    )
    assert "duplicate-awareness context only" in system_prompt
    assert "never use `visible_content` to" in normalized_system_prompt
    for prohibited_use in ("support", "extend", "combine", "create"):
        assert prohibited_use in normalized_system_prompt
    assert "sole authority for relationships" in normalized_system_prompt
    assert "using only selected `signals` as factual evidence" in user_prompt
    assert "do not derive or extend claims from it" in user_prompt
    assert "# Daily Listening Report" not in request.to_json()


def test_report_generator_preserves_an_approved_symbol_label_end_to_end() -> None:
    provider = FakeProvider(
        response=json.dumps(
            {
                "items": [
                    {
                        "plan_item_id": "plan-1",
                        "role": "primary",
                        "text": "Artist ★ appears stable across the selected window.",
                    }
                ]
            },
            ensure_ascii=False,
        )
    )
    selected = _signal("selected", label="Artist ★")
    plan = InterpretationPlan(
        (
            PlanItem(
                "plan-1",
                InterpretationRole.PRIMARY,
                (selected.signal_id,),
                SignalRelationship.UNRELATED,
                "signal:exploration",
            ),
        )
    )
    request = InterpretationRequest.from_plan(
        plan,
        (selected,),
        VisibleContentManifest(),
        SupportedLocale.EN_US,
    )

    assert ReportGenerator(provider).generate_report(request) == (
        "Artist ★ appears stable across the selected window."
    )


def test_chinese_target_locale_reaches_prompt_and_wire_contract() -> None:
    provider = FakeProvider(response=json.dumps({"items": [{"plan_item_id": "plan-1", "role": "primary", "text": "最近的艺人组合显得更宽了。"}]}))
    request = _request(SupportedLocale.ZH_CN)

    report = ReportGenerator(provider).generate_report(request)

    assert report == "最近的艺人组合显得更宽了。"
    assert "natural Simplified Chinese" in (provider.system_prompt or "")
    assert json.loads((provider.user_prompt or "").split("\n\n", 1)[1])["target_locale"] == "zh-CN"


def test_report_generator_rejects_untyped_or_empty_requests_before_transport() -> None:
    provider = FakeProvider()
    with pytest.raises(TypeError, match="InterpretationRequest"):
        ReportGenerator(provider).generate_report([])  # type: ignore[arg-type]
    assert provider.calls == 0


@pytest.mark.parametrize(
    "response",
    [
        "not JSON",
        "[]",
        json.dumps({"items": []}),
        json.dumps({"items": [{"plan_item_id": "unknown", "role": "primary", "text": "x"}]}),
        json.dumps({"items": [{"plan_item_id": "plan-1", "role": "watch", "text": "x"}]}),
        '{"items":[],"items":[{"plan_item_id":"plan-1","role":"primary","text":"x"}]}',
        '{"items":[{"plan_item_id":"plan-1","role":"watch","role":"primary","text":"x"}]}',
    ],
)
def test_report_generator_rejects_invalid_or_reference_invalid_output(response: str) -> None:
    with pytest.raises(RuntimeError, match="invalid interpretation"):
        ReportGenerator(FakeProvider(response=response)).generate_report(_request())


def test_prompt_is_interpreter_policy_without_legacy_six_field_contract() -> None:
    for locale in SupportedLocale:
        prompt = build_system_prompt(locale)
        assert "deterministic code has already decided" in prompt.lower()
        assert "Do not discover" in prompt
        assert '"items"' in prompt
        for legacy in ("greeting", "listening_summary", "recommendation", "closing"):
            assert f'"{legacy}"' not in prompt
