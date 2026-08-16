"""Provider-independent contracts for MusicMind listening interpretation."""

from importlib import import_module


__all__ = [
    "GLOBAL_PROHIBITED_CLAIMS",
    "InterpretationBrief",
    "InterpretationBriefItem",
    "InterpretationRequest",
    "LLMProvider",
    "MAX_INTERPRETATION_TEXT_CHARACTERS",
    "ReportGenerator",
    "create_llm_provider",
    "render_interpretation_brief",
]

_EXPORTS = {
    "GLOBAL_PROHIBITED_CLAIMS": ("music_ai.ai.interpretation_request", "GLOBAL_PROHIBITED_CLAIMS"),
    "InterpretationBrief": ("music_ai.ai.interpretation_brief", "InterpretationBrief"),
    "InterpretationBriefItem": ("music_ai.ai.interpretation_brief", "InterpretationBriefItem"),
    "InterpretationRequest": ("music_ai.ai.interpretation_request", "InterpretationRequest"),
    "LLMProvider": ("music_ai.ai.base", "LLMProvider"),
    "MAX_INTERPRETATION_TEXT_CHARACTERS": ("music_ai.ai.interpretation_brief", "MAX_INTERPRETATION_TEXT_CHARACTERS"),
    "ReportGenerator": ("music_ai.ai.report_generator", "ReportGenerator"),
    "create_llm_provider": ("music_ai.ai.base", "create_llm_provider"),
    "render_interpretation_brief": ("music_ai.ai.markdown_renderer", "render_interpretation_brief"),
}


def __getattr__(name: str):
    """Load public contracts without coupling provider modules to product policy."""
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(name)
    value = getattr(import_module(target[0]), target[1])
    globals()[name] = value
    return value
