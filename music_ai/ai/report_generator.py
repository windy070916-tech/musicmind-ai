"""Generate validated prose from one typed deterministic interpretation request."""

import json

from music_ai.ai.base import LLMProvider, create_llm_provider
from music_ai.ai.interpretation_brief import InterpretationBrief
from music_ai.ai.interpretation_request import InterpretationRequest
from music_ai.ai.markdown_renderer import render_interpretation_brief
from music_ai.ai.prompts import build_system_prompt, build_user_prompt
from music_ai.localization.models import SupportedLocale


class ReportGenerator:
    """Transport a narrow approved request and validate the provider realization."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider or create_llm_provider()

    def generate_interpretation(
        self,
        request: InterpretationRequest,
    ) -> InterpretationBrief:
        """Invoke one provider for a non-empty typed request and validate its output."""
        if not isinstance(request, InterpretationRequest):
            raise TypeError("request must be InterpretationRequest.")
        if not request.plan_items:
            raise ValueError("The provider cannot be invoked for an empty plan.")
        locale = SupportedLocale(request.target_locale)
        response = self._provider.generate(
            build_system_prompt(locale),
            build_user_prompt(request.to_json()),
        )
        return _parse_interpretation_brief(response, request)

    def generate_report(self, request: InterpretationRequest) -> str:
        """Render the validated dynamic brief as one to three short paragraphs."""
        return render_interpretation_brief(self.generate_interpretation(request))


def _parse_interpretation_brief(
    response: str,
    request: InterpretationRequest,
) -> InterpretationBrief:
    """Decode strict JSON and translate all contract failures to one runtime error."""
    if not isinstance(response, str):
        raise RuntimeError("LLM provider returned an invalid interpretation response.")
    try:
        payload = json.loads(response, object_pairs_hook=_unique_object)
    except (json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(
            "LLM provider returned an invalid interpretation response."
        ) from error
    if not isinstance(payload, dict):
        raise RuntimeError("LLM provider returned an invalid interpretation response.")
    try:
        return InterpretationBrief.from_payload(payload, request)
    except ValueError as error:
        raise RuntimeError(
            "LLM provider returned an invalid interpretation response."
        ) from error


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject duplicate JSON object keys instead of accepting last-key-wins."""
    resolved: dict[str, object] = {}
    for key, value in pairs:
        if key in resolved:
            raise ValueError("Duplicate JSON object key.")
        resolved[key] = value
    return resolved
